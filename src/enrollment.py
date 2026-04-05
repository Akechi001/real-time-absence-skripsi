# src/enrollment.py - Pendaftaran wajah karyawan (Sprint 1)

import cv2
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.modules.face_detector import FaceDetector
from src.modules.face_recognizer import FaceRecognizer
from src.database.operations import save_karyawan, save_template, get_all_templates
import config

def enroll_karyawan():
    """Proses pendaftaran wajah karyawan baru"""
    print("=== SISTEM ENROLLMENT WAJAH ===\n")

    # Input data karyawan
    nip = input("NIP: ")
    nama = input("Nama: ")
    jabatan = input("Jabatan: ")
    print("Jenis karyawan: 1. internal  2. vendor")
    jenis_input = input("Pilih (1/2): ")
    jenis_karyawan = "internal" if jenis_input == "1" else "vendor"

    # Simpan data karyawan
    id_karyawan = save_karyawan(nip, nama, jabatan, jenis_karyawan)
    if not id_karyawan:
        print("✗ Gagal menyimpan data karyawan")
        return

    print(f"\n✓ Data karyawan tersimpan - ID: {id_karyawan}")
    print("\nSiapkan kamera untuk pengambilan foto wajah")
    print("Tekan SPACE untuk ambil foto, Q untuk keluar\n")

    # Inisialisasi detector dan recognizer
    detector = FaceDetector()
    recognizer = FaceRecognizer()

    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    embeddings = []
    foto_count = 0
    target_foto = 5  # Ambil 5 foto untuk averaging

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        faces = detector.detect(frame)
        frame = detector.draw_faces(frame, faces)

        # Info di layar
        cv2.putText(frame, f"Foto: {foto_count}/{target_foto}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, "SPACE=Ambil Foto  Q=Keluar", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)

        if len(faces) == 1:
            cv2.putText(frame, "Wajah terdeteksi - Tekan SPACE", (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
        elif len(faces) == 0:
            cv2.putText(frame, "Tidak ada wajah terdeteksi", (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)
        else:
            cv2.putText(frame, "Terlalu banyak wajah!", (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)

        cv2.imshow("Enrollment - " + nama, frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            break
        elif key == ord(' ') and len(faces) == 1:
            # Ambil embedding
            bbox = faces[0][:4]
            embedding = recognizer.get_embedding(frame, [int(x) for x in bbox])

            if embedding is not None:
                embeddings.append(embedding)
                foto_count += 1
                print(f"✓ Foto {foto_count}/{target_foto} berhasil diambil")

                if foto_count >= target_foto:
                    break
            else:
                print("✗ Gagal ekstrak embedding, coba lagi")

    cap.release()
    cv2.destroyAllWindows()

    if len(embeddings) == 0:
        print("✗ Tidak ada embedding yang berhasil diambil")
        return

    # Average embedding dari beberapa foto
    import numpy as np
    avg_embedding = np.mean(embeddings, axis=0)

    # Simpan ke database
    if save_template(id_karyawan, avg_embedding):
        print(f"\n✓ Enrollment berhasil untuk {nama}!")
        print(f"  - ID Karyawan: {id_karyawan}")
        print(f"  - Jumlah foto: {len(embeddings)}")
    else:
        print("✗ Gagal menyimpan template wajah")


if __name__ == "__main__":
    enroll_karyawan()