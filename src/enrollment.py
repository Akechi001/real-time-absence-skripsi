# src/enrollment.py - Enrollment karyawan baru

import cv2
import threading
import numpy as np
import sys
import os
import warnings
warnings.filterwarnings("ignore")

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.database.operations import (
    get_all_templates, save_karyawan, save_template
)
import config


class EnrollmentThread(threading.Thread):
    def __init__(self, stop_event, enrollment_event):
        super().__init__(daemon=True)
        self.stop_event = stop_event
        self.enrollment_event = enrollment_event
        self.pending_enrollment = None
        self.enrollment_done = threading.Event()

    def run(self):
        while not self.stop_event.is_set():
            print("\n" + "="*50)
            print("MENU UTAMA")
            print("1. Daftarkan karyawan baru")
            print("2. Lihat karyawan terdaftar")
            print("3. Keluar")
            print("="*50)

            try:
                choice = input("Pilih menu: ").strip()
            except EOFError:
                break

            if choice == "1":
                self.collect_enrollment_data()
            elif choice == "2":
                self.list_karyawan()
            elif choice == "3":
                self.stop_event.set()
                break

    def collect_enrollment_data(self):
        """Kumpulkan data karyawan dari terminal"""
        print("\n=== ENROLLMENT KARYAWAN BARU ===")
        nip = input("NIP: ").strip()
        nama = input("Nama: ").strip()
        jabatan = input("Jabatan: ").strip()
        print("Jenis: 1. internal  2. vendor")
        jenis = "internal" if input("Pilih (1/2): ").strip() == "1" else "vendor"

        self.pending_enrollment = {
            'nip': nip,
            'nama': nama,
            'jabatan': jabatan,
            'jenis': jenis
        }
        self.enrollment_done.clear()
        self.enrollment_event.set()

        print("Menunggu proses foto di kamera...")
        self.enrollment_done.wait(timeout=60)

    def do_enrollment(self, attendance_system):
        """Proses enrollment — dipanggil dari main thread"""
        data = self.pending_enrollment
        nama = data['nama']

        id_karyawan = save_karyawan(
            data['nip'], nama, data['jabatan'], data['jenis']
        )
        if not id_karyawan:
            print("✗ Gagal simpan data karyawan")
            self.enrollment_done.set()
            self.pending_enrollment = None
            return

        print(f"\n✓ Data tersimpan - ID: {id_karyawan}")
        print(f"Tekan SPACE untuk ambil foto (5 foto), Q untuk batal")

        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        embeddings = []
        foto_count = 0
        target = 5

        while foto_count < target and not self.stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                break

            faces = attendance_system.detector.detect(frame)
            display = attendance_system.detector.draw_faces(frame.copy(), faces)

            cv2.putText(display, f"Foto: {foto_count}/{target}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(display, f"Enrolling: {nama}", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

            if len(faces) == 1:
                cv2.putText(display, "Wajah terdeteksi - Tekan SPACE", (10, 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
            elif len(faces) == 0:
                cv2.putText(display, "Tidak ada wajah", (10, 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)
            else:
                cv2.putText(display, "Terlalu banyak wajah!", (10, 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)

            cv2.imshow(f"Enrollment - {nama}", display)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                break
            elif key == ord(' ') and len(faces) == 1:
                emb = attendance_system.recognizer.get_embedding(
                    frame, [int(x) for x in faces[0][:4]]
                )
                if emb is not None:
                    embeddings.append(emb)
                    foto_count += 1
                    print(f"✓ Foto {foto_count}/{target}")

        cap.release()
        cv2.destroyAllWindows()

        if embeddings:
            avg_embedding = np.mean(embeddings, axis=0)
            if save_template(id_karyawan, avg_embedding):
                print(f"✓ Enrollment berhasil untuk {nama}!")
                attendance_system.reload_templates()
            else:
                print("✗ Gagal simpan template")
        else:
            print("✗ Tidak ada foto yang diambil")

        self.enrollment_done.set()
        self.pending_enrollment = None

    def list_karyawan(self):
        templates = get_all_templates()
        print(f"\n=== KARYAWAN TERDAFTAR ({len(templates)}) ===")
        for t in templates:
            print(f"  - ID {t['id_karyawan']}: {t['nama']}")