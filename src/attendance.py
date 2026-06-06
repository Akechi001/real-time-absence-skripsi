# src/attendance.py - Sistem absensi otomatis dengan anti-spoofing

import cv2
import csv
import gc
import time
import threading
import sys
import os
import warnings
warnings.filterwarnings("ignore")

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.modules.face_detector import FaceDetector
from src.modules.face_recognizer import FaceRecognizer
from src.modules.liveness import LivenessDetector
from src.modules.anti_spoofing.detector import AntiSpoofingDetector
from src.database.operations import (
    get_all_templates, save_log_absensi
)
from src.payload import build_payload, send_payload
import config

templates_lock = threading.Lock()
shared_templates = []

# Kolom CSV pengujian latensi per-modul (Bab V). Satu baris per wajah
# yang diproses; kolom tahap yang tidak tercapai dibiarkan kosong.
LATENCY_CSV_FIELDS = [
    'timestamp', 'num_faces', 'exit_stage',
    'yolo_ms', 'insightface_ms', 'embedding_ms', 'identify_ms',
    'liveness_ms', 'antispoof_ms', 'total_ms',
]


class AttendanceSystem:
    def __init__(self):
        self.detector = FaceDetector()
        self.recognizer = FaceRecognizer()
        self.liveness = LivenessDetector()
        self.anti_spoofing = AntiSpoofingDetector()
        self.cooldown = {}

        global shared_templates
        with templates_lock:
            shared_templates = get_all_templates()
        print(f"✓ Loaded {len(shared_templates)} template wajah")

    def reload_templates(self):
        global shared_templates
        with templates_lock:
            shared_templates = get_all_templates()
        print(f"✓ Templates reloaded: {len(shared_templates)}")

    def is_cooldown(self, id_karyawan):
        if id_karyawan not in self.cooldown:
            return False
        return time.time() - self.cooldown[id_karyawan] < config.COOLDOWN_SECONDS

    def _write_latency_row(self, row):
        """Tulis satu baris breakdown latensi per-modul ke CSV (pengujian Bab V)."""
        path = getattr(config, 'LATENCY_CSV_PATH', 'logs/latency_per_module.csv')
        try:
            dirname = os.path.dirname(path)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
            write_header = (not os.path.exists(path)) or os.path.getsize(path) == 0
            with open(path, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=LATENCY_CSV_FIELDS)
                if write_header:
                    writer.writeheader()
                writer.writerow(row)
        except Exception as e:
            print(f"⚠️ gagal tulis latency CSV: {e}")

    def process_frame(self, frame, faces, t_yolo=0.0):
        """
        Sequential pipeline:
        YOLO → ArcFace → Liveness Stage 1 (EAR/head) → Liveness Stage 2 (CNN) → Log

        t_yolo: durasi deteksi YOLO (detik) dari pemanggil, supaya bisa ikut
        dicatat di CSV latensi per-modul.
        """
        t_start = time.time()

        if not faces:
            return []

        results = []

        t1 = time.time()
        faces_insightface = self.recognizer.app.get(frame)
        t_insightface = time.time() - t1

        with templates_lock:
            current_templates = list(shared_templates)

        latency_log = getattr(config, 'LATENCY_CSV_LOG', False)

        for i, face_bbox in enumerate(faces):
            # Timer per tahap; None artinya tahap tak tercapai untuk wajah ini.
            t_embedding = t_identify = t_liveness = t_antispoof = None
            exit_stage = 'error'
            try:
                # 1. Ekstraksi embedding ArcFace
                t1 = time.time()
                embedding = self.recognizer.get_embedding(
                    frame, [int(x) for x in face_bbox[:4]], faces_insightface
                )
                t_embedding = time.time() - t1

                if embedding is None:
                    exit_stage = 'no_embedding'
                    continue

                # 2. Pencocokan identitas
                t1 = time.time()
                result = self.recognizer.identify(embedding, current_templates)
                t_identify = time.time() - t1
                if result is None:
                    exit_stage = 'unknown'
                    results.append({
                        'status': 'unknown',
                        'message': 'Wajah tidak dikenali'
                    })
                    continue

                id_karyawan = result['id_karyawan']
                nama = result['nama']
                confidence = result['confidence']

                # 3. Cek cooldown
                if self.is_cooldown(id_karyawan):
                    exit_stage = 'cooldown'
                    results.append({
                        'status': 'cooldown',
                        'nama': nama,
                        'message': f'Cooldown: {nama}'
                    })
                    continue

                # 4. Liveness Stage 1 — EAR + head movement
                t1 = time.time()
                face_obj = faces_insightface[i] if i < len(faces_insightface) else None
                is_live, _ = self.liveness.check_liveness(i, face_obj)
                t_liveness = time.time() - t1

                if not is_live:
                    exit_stage = 'liveness_fail'
                    print(f"✗ LIVENESS STAGE 1: GAGAL - tidak ada gerakan kepala/kedipan ({nama})")
                    t_total = time.time() - t_start
                    print(f"⏱️ TIMING: insightface={t_insightface*1000:.0f}ms embed={t_embedding*1000:.0f}ms identify={t_identify*1000:.0f}ms liveness={t_liveness*1000:.0f}ms total={t_total*1000:.0f}ms")
                    results.append({
                        'status': 'spoofing',
                        'nama': nama,
                        'message': 'Liveness gagal — gerakkan kepala'
                    })
                    continue

                print(f"✓ LIVENESS STAGE 1: LOLOS ({nama})")

                # 5. Liveness Stage 2 — Anti-spoofing CNN
                t1 = time.time()
                is_real, spoof_conf = self.anti_spoofing.predict(frame, face_bbox)
                t_antispoof = time.time() - t1

                if is_real and spoof_conf >= config.ANTI_SPOOFING_THRESHOLD:
                    print(f"✓ ANTI-SPOOF: WAJAH ASLI - confidence={spoof_conf:.3f} ({nama})")
                else:
                    exit_stage = 'spoof'
                    if not is_real:
                        reason = "TERDETEKSI FOTO/SCREEN/SPOOF"
                    else:
                        reason = f"CONFIDENCE RENDAH ({spoof_conf:.3f})"
                    print(f"✗ ANTI-SPOOF: SPOOFING - {reason} ({nama})")
                    t_total = time.time() - t_start
                    print(f"⏱️ TIMING: insightface={t_insightface*1000:.0f}ms embed={t_embedding*1000:.0f}ms identify={t_identify*1000:.0f}ms liveness={t_liveness*1000:.0f}ms antispoof={t_antispoof*1000:.0f}ms total={t_total*1000:.0f}ms")

                    results.append({
                        'status': 'spoofing',
                        'nama': nama,
                        'message': f'Spoofing terdeteksi (conf: {spoof_conf:.2f})'
                    })
                    continue

                # 6. Simpan log absensi sebagai 'passage' (raw lewatan).
                #    Keputusan check-in/check-out + status terlambat/pulang cepat
                #    dilakukan batch tengah malam oleh resolve_attendance_for_date().
                save_log_absensi(
                    id_karyawan=id_karyawan,
                    jenis_event='passage',
                    confidence_score=confidence,
                    status_liveness=is_live
                )

                # 7. Kirim payload
                passage_time = time.strftime('%H:%M:%S')
                payload = build_payload(
                    id_karyawan, nama, 'passage', confidence, is_live
                )
                send_payload(payload)

                # 8. Set cooldown dan reset liveness
                self.cooldown[id_karyawan] = time.time()
                self.liveness.reset_state(i)

                t_total = time.time() - t_start
                print(f"⏱️ TIMING: insightface={t_insightface*1000:.0f}ms embed={t_embedding*1000:.0f}ms identify={t_identify*1000:.0f}ms liveness={t_liveness*1000:.0f}ms antispoof={t_antispoof*1000:.0f}ms total={t_total*1000:.0f}ms")

                exit_stage = 'success'
                results.append({
                    'status': 'success',
                    'id_karyawan': id_karyawan,
                    'nama': nama,
                    'confidence': confidence,
                    'passage_time': passage_time,
                })
            finally:
                if latency_log:
                    def _ms(v):
                        return round(v * 1000, 2) if v is not None else ''
                    self._write_latency_row({
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'num_faces': len(faces),
                        'exit_stage': exit_stage,
                        'yolo_ms': round(t_yolo * 1000, 2),
                        'insightface_ms': round(t_insightface * 1000, 2),
                        'embedding_ms': _ms(t_embedding),
                        'identify_ms': _ms(t_identify),
                        'liveness_ms': _ms(t_liveness),
                        'antispoof_ms': _ms(t_antispoof),
                        'total_ms': round((time.time() - t_start) * 1000, 2),
                    })

        # Lepas list Face object InsightFace — tiap Face simpan embedding +
        # landmark 2D/3D + bbox + kps (~15-20KB). Tanpa ini ref bisa tertahan
        # via closure di anti_spoofing/liveness sampai GC siklus berikutnya.
        del faces_insightface
        return results

    def run(self, stop_event):
        """Returns True kalau pre-emptive restart (uptime lewat batas),
        False kalau intentional stop (Q key).
        """
        print(f"\n=== SISTEM ABSENSI BERJALAN ===")
        print("Tekan Q di jendela kamera untuk keluar\n")

        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
        # Set internal buffer ke 1 frame supaya gak akumulasi queue
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        start_time = time.time()
        max_uptime = getattr(config, 'MAX_UPTIME_SECONDS', 0)
        preemptive_restart = False

        display_state = {
            'last_faces': [],
            'last_results': [],
            'last_result_time': 0,
            'current_results': [],
        }
        display_lock = threading.Lock()

        bg_state = {'frame': None, 'ready': True}
        bg_lock = threading.Lock()
        bg_trigger = threading.Event()

        last_gc_time = time.time()
        GC_INTERVAL = 60  # 1 menit

        def background_worker():
            nonlocal last_gc_time
            while not stop_event.is_set():
                bg_trigger.wait(timeout=0.5)
                bg_trigger.clear()

                with bg_lock:
                    frame = bg_state['frame']
                    if frame is None:
                        bg_state['ready'] = True
                        continue

                t_yolo_start = time.time()
                faces = self.detector.detect(frame)
                t_yolo = time.time() - t_yolo_start

                if faces:
                    print(f"⏱️ YOLO detect: {t_yolo*1000:.0f}ms")

                results = self.process_frame(frame, faces, t_yolo=t_yolo)

                with display_lock:
                    display_state['last_faces'] = faces
                    display_state['current_results'] = results
                    if any(r['status'] == 'success' for r in results):
                        display_state['last_results'] = results
                        display_state['last_result_time'] = time.time()

                with bg_lock:
                    bg_state['ready'] = True

                # gc.collect() tiap 1 menit — Python GC lazy, paksa
                # reclaim Python ref cycles secara periodic.
                if time.time() - last_gc_time > GC_INTERVAL:
                    collected = gc.collect()
                    last_gc_time = time.time()
                    print(f"🧹 gc.collect() → {collected} objects released")

        worker = threading.Thread(target=background_worker, daemon=True)
        worker.start()

        frame_interval = 1.0 / config.FPS_SAMPLING
        last_send_time = 0

        while not stop_event.is_set():
            # Pre-emptive restart untuk mitigasi memory leak ONNX/PyTorch
            # arena pool yang tidak shrink di CPU backend.
            if max_uptime > 0 and time.time() - start_time > max_uptime:
                print(f"\n♻️  Pre-emptive restart: uptime > {max_uptime}s, "
                      f"daemon akan spawn proses baru.\n")
                preemptive_restart = True
                stop_event.set()
                break

            ret, frame = cap.read()
            if not ret:
                # Camera read failed — bisa karena buffer hiccup atau
                # disconnect sementara. Retry beberapa kali dulu sebelum
                # give up. Kalau tetap gagal, treat sebagai restart-worthy
                # (bukan intentional stop) supaya daemon spawn proses baru
                # dengan kamera fresh.
                read_failed = True
                for retry in range(10):
                    time.sleep(0.1)
                    ret, frame = cap.read()
                    if ret:
                        read_failed = False
                        print(f"📷 Camera recovered setelah {retry+1} retry")
                        break
                if read_failed:
                    print("⚠ Camera read failed setelah 10x retry — request restart")
                    preemptive_restart = True
                    stop_event.set()
                    break

            current_time = time.time()

            with bg_lock:
                is_ready = bg_state['ready']

            if current_time - last_send_time >= frame_interval and is_ready:
                with bg_lock:
                    bg_state['frame'] = frame.copy()
                    bg_state['ready'] = False
                bg_trigger.set()
                last_send_time = current_time

            display_frame = frame.copy()

            with display_lock:
                faces = display_state['last_faces']
                last_results = display_state['last_results']
                last_result_time = display_state['last_result_time']
                current_results = display_state['current_results']

            if faces:
                display_frame = self.detector.draw_faces(display_frame, faces)

            y_offset = 30

            if last_results and time.time() - last_result_time < 3:
                for r in last_results:
                    if r['status'] == 'success':
                        text = f"Terdeteksi: {r['nama']} ({r['passage_time']})"
                        cv2.putText(display_frame, text, (10, y_offset),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        y_offset += 30

            for r in current_results:
                if r['status'] == 'unknown':
                    cv2.putText(display_frame, "Wajah tidak dikenali",
                                (10, y_offset),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    y_offset += 30
                elif r['status'] == 'spoofing':
                    cv2.putText(display_frame, r['message'],
                                (10, y_offset),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
                    y_offset += 30
                elif r['status'] == 'cooldown':
                    cv2.putText(display_frame, r['message'],
                                (10, y_offset),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2)
                    y_offset += 30

            cv2.putText(
                display_frame,
                f"Kamera: masuk | Wajah: {len(faces)} | FPS: {config.FPS_SAMPLING}",
                (10, display_frame.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
            )

            cv2.imshow("Absensi - masuk", display_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                stop_event.set()
                break

        cap.release()
        cv2.destroyAllWindows()
        return preemptive_restart