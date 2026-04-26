# src/attendance.py - Sistem absensi otomatis dengan anti-spoofing

import cv2
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
    get_all_templates, save_log_absensi, get_last_event
)
from src.payload import build_payload, send_payload
import config

templates_lock = threading.Lock()
shared_templates = []


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

    def determine_event(self, id_karyawan):
        last = get_last_event(id_karyawan)
        if last is None:
            return "check-in"
        return "check-out" if last['jenis_event'] == "check-in" else "check-in"

    def process_frame(self, frame, faces):
        """
        Sequential pipeline:
        YOLO → ArcFace → Liveness Stage 1 (EAR/head) → Liveness Stage 2 (CNN) → Log
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

        for i, face_bbox in enumerate(faces):
            # 1. Ekstraksi embedding ArcFace
            t1 = time.time()
            embedding = self.recognizer.get_embedding(
                frame, [int(x) for x in face_bbox[:4]], faces_insightface
            )
            t_embedding = time.time() - t1

            if embedding is None:
                continue

            # 2. Pencocokan identitas
            result = self.recognizer.identify(embedding, current_templates)
            if result is None:
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
                print(f"✗ LIVENESS STAGE 1: GAGAL - tidak ada gerakan kepala/kedipan ({nama})")
                t_total = time.time() - t_start
                print(f"⏱️ TIMING: insightface={t_insightface*1000:.0f}ms embed={t_embedding*1000:.0f}ms liveness={t_liveness*1000:.0f}ms total={t_total*1000:.0f}ms")
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
                if not is_real:
                    reason = "TERDETEKSI FOTO/SCREEN/SPOOF"
                else:
                    reason = f"CONFIDENCE RENDAH ({spoof_conf:.3f})"
                print(f"✗ ANTI-SPOOF: SPOOFING - {reason} ({nama})")
                t_total = time.time() - t_start
                print(f"⏱️ TIMING: insightface={t_insightface*1000:.0f}ms embed={t_embedding*1000:.0f}ms liveness={t_liveness*1000:.0f}ms antispoof={t_antispoof*1000:.0f}ms total={t_total*1000:.0f}ms")

                results.append({
                    'status': 'spoofing',
                    'nama': nama,
                    'message': f'Spoofing terdeteksi (conf: {spoof_conf:.2f})'
                })
                continue

            # 6. Tentukan jenis event
            jenis_event = self.determine_event(id_karyawan)

            # 7. Simpan log absensi
            save_log_absensi(
                id_karyawan=id_karyawan,
                jenis_event=jenis_event,
                confidence_score=confidence,
                status_liveness=is_live
            )

            # 8. Kirim payload
            payload = build_payload(
                id_karyawan, nama, jenis_event, confidence, is_live
            )
            send_payload(payload)

            # 9. Set cooldown dan reset liveness
            self.cooldown[id_karyawan] = time.time()
            self.liveness.reset_state(i)

            t_total = time.time() - t_start
            print(f"⏱️ TIMING: insightface={t_insightface*1000:.0f}ms embed={t_embedding*1000:.0f}ms liveness={t_liveness*1000:.0f}ms antispoof={t_antispoof*1000:.0f}ms total={t_total*1000:.0f}ms")

            results.append({
                'status': 'success',
                'id_karyawan': id_karyawan,
                'nama': nama,
                'confidence': confidence,
                'jenis_event': jenis_event,
            })

        return results

    def run(self, enrollment_thread, stop_event, enrollment_event):
        print(f"\n=== SISTEM ABSENSI BERJALAN ===")
        print("Tekan Q di jendela kamera untuk keluar\n")

        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)

        display_state = {
            'last_faces': [],
            'last_results': [],
            'last_result_time': 0,
            'current_results': [],
        }
        display_lock = threading.Lock()

        bg_state = {
            'frame': None,
            'ready': True,
        }
        bg_lock = threading.Lock()
        bg_trigger = threading.Event()

        def background_worker():
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

                results = self.process_frame(frame, faces)

                with display_lock:
                    display_state['last_faces'] = faces
                    display_state['current_results'] = results
                    if any(r['status'] == 'success' for r in results):
                        display_state['last_results'] = results
                        display_state['last_result_time'] = time.time()

                with bg_lock:
                    bg_state['ready'] = True

        worker = threading.Thread(target=background_worker, daemon=True)
        worker.start()

        frame_interval = 1.0 / config.FPS_SAMPLING
        last_send_time = 0

        while not stop_event.is_set():

            if enrollment_event.is_set() and enrollment_thread.pending_enrollment:
                enrollment_event.clear()
                cap.release()
                cv2.destroyAllWindows()
                enrollment_thread.do_enrollment(self)
                cap = cv2.VideoCapture(config.CAMERA_INDEX)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
                continue

            ret, frame = cap.read()
            if not ret:
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
                        text = f"{r['jenis_event'].upper()}: {r['nama']} ({r['confidence']:.2f})"
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