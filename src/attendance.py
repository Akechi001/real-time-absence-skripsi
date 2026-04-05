# src/attendance.py - Sistem absensi otomatis (Sprint 2 & 3)

import cv2
import numpy as np
import time
import sys
import os
import warnings
warnings.filterwarnings("ignore")

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.modules.face_detector import FaceDetector
from src.modules.face_recognizer import FaceRecognizer
from src.modules.liveness import LivenessDetector
from src.database.operations import (
    get_all_templates, save_log_absensi, get_last_event
)
import config

class AttendanceSystem:
    def __init__(self, camera_index=0, camera_type="masuk"):
        self.camera_index = camera_index
        self.camera_type = camera_type

        self.detector = FaceDetector()
        self.recognizer = FaceRecognizer()
        self.liveness = LivenessDetector()

        self.templates = get_all_templates()
        print(f"✓ Loaded {len(self.templates)} template wajah")

        self.cooldown = {}

    def determine_event(self, id_karyawan):
        last = get_last_event(id_karyawan)
        if last is None:
            return "check-in"
        if last['jenis_event'] == "check-in":
            return "check-out"
        else:
            return "check-in"

    def is_cooldown(self, id_karyawan):
        if id_karyawan not in self.cooldown:
            return False
        elapsed = time.time() - self.cooldown[id_karyawan]
        return elapsed < config.COOLDOWN_SECONDS

    def process_frame(self, frame):
        faces = self.detector.detect(frame)
        if not faces:
            return []

        results = []
        faces_insightface = self.recognizer.app.get(frame)

        for i, face_bbox in enumerate(faces):
            track_id = i

            # 1. Kenali identitas
            embedding = self.recognizer.get_embedding(
                frame, [int(x) for x in face_bbox[:4]]
            )

            if embedding is None:
                print(f"DEBUG [{i}]: embedding None")
                continue

            result = self.recognizer.identify(embedding, self.templates)

            if result is None:
                print(f"DEBUG [{i}]: wajah tidak dikenali")
                results.append({'status': 'unknown', 'message': 'Wajah tidak dikenali'})
                continue

            id_karyawan = result['id_karyawan']
            nama = result['nama']
            confidence = result['confidence']
            print(f"DEBUG [{i}]: Dikenali → {nama} (confidence={confidence:.3f})")

            # 2. Cek cooldown
            if self.is_cooldown(id_karyawan):
                print(f"DEBUG [{i}]: {nama} masih cooldown")
                results.append({
                    'status': 'cooldown',
                    'nama': nama,
                    'message': 'Absensi sudah tercatat'
                })
                continue

            # 3. Verifikasi liveness
            face_obj = faces_insightface[i] if i < len(faces_insightface) else None
            is_live, reason = self.liveness.check_liveness(track_id, face_obj)
            print(f"DEBUG [{i}]: is_live={is_live} reason={reason}")

            if not is_live:
                results.append({
                    'status': 'spoofing',
                    'nama': nama,
                    'message': 'Verifikasi liveness gagal — gerakkan kepala'
                })
                continue

            # 4. Tentukan jenis event
            jenis_event = self.determine_event(id_karyawan)
            print(f"DEBUG [{i}]: {nama} → {jenis_event}")

            # 5. Simpan log absensi
            saved = save_log_absensi(
                id_karyawan=id_karyawan,
                jenis_event=jenis_event,
                confidence_score=confidence,
                status_liveness=is_live
            )
            print(f"DEBUG [{i}]: Log tersimpan={saved} → {nama} {jenis_event}")

            # 6. Set cooldown dan reset liveness
            self.cooldown[id_karyawan] = time.time()
            self.liveness.reset_state(track_id)

            results.append({
                'status': 'success',
                'id_karyawan': id_karyawan,
                'nama': nama,
                'confidence': confidence,
                'jenis_event': jenis_event,
                'message': f'{jenis_event.upper()} berhasil!'
            })

        return results

    def run(self):
        print(f"\n=== SISTEM ABSENSI - Kamera {self.camera_type.upper()} ===")
        print("Tekan Q untuk keluar\n")

        cap = cv2.VideoCapture(self.camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)

        last_results = []
        last_result_time = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            results = self.process_frame(frame)

            if any(r['status'] == 'success' for r in results):
                last_results = results
                last_result_time = time.time()

            display_frame = frame.copy()
            faces = self.detector.detect(frame)
            display_frame = self.detector.draw_faces(display_frame, faces)

            y_offset = 30

            # Tampilkan hasil sukses terakhir selama 3 detik
            if last_results and time.time() - last_result_time < 3:
                for r in last_results:
                    if r['status'] == 'success':
                        text = f"{r['jenis_event'].upper()}: {r['nama']} ({r['confidence']:.2f})"
                        cv2.putText(display_frame, text, (10, y_offset),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        y_offset += 30

            # Tampilkan status real-time
            for r in results:
                if r['status'] == 'unknown':
                    cv2.putText(display_frame, "Wajah tidak dikenali", (10, y_offset),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    y_offset += 30
                elif r['status'] == 'spoofing':
                    cv2.putText(display_frame, r['message'], (10, y_offset),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
                    y_offset += 30
                elif r['status'] == 'cooldown':
                    cv2.putText(display_frame, f"Cooldown: {r['nama']}", (10, y_offset),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2)
                    y_offset += 30

            cv2.putText(display_frame,
                        f"Kamera: {self.camera_type} | Wajah: {len(faces)}",
                        (10, display_frame.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            cv2.imshow(f"Absensi - {self.camera_type}", display_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    system = AttendanceSystem(
        camera_index=config.CAMERA_INDEX,
        camera_type="masuk"
    )
    system.run()