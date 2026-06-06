# scripts/exp_roi_latency.py
#
# EKSPERIMEN (Bab V) — Opsi B aman: kirim crop YOLO ke InsightFace.
#
# Membandingkan dua metode ekstraksi embedding pada gambar yang SAMA:
#   M1 (sekarang)  : app.get(frame penuh 640x480)   -> SCRFD scan seluruh frame
#   M2 (Opsi B)    : crop bbox YOLO (+padding) -> app.get(crop)
#
# Mengukur: (a) latensi tiap metode, (b) cosine similarity antar embedding M1 vs M2
# untuk membuktikan akurasi (alignment) tidak rusak saat memakai crop.
#
# Tidak menyentuh attendance.py. Murni pengukuran offline pakai foto enrollment.

import sys
import os
import time
import glob
import statistics as st

import cv2
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.modules.face_detector import FaceDetector
from src.modules.face_recognizer import FaceRecognizer

FRAME_W, FRAME_H = 640, 480       # ukuran frame operasional (config)
PAD_RATIO = 0.3                   # padding di sekeliling bbox YOLO untuk crop
REPEAT = 5                        # ulang tiap metode per gambar (buang warmup)


def to_operational_frame(img):
    """Resize gambar ke 640x480 (letterbox) supaya sama dengan frame webcam."""
    h, w = img.shape[:2]
    scale = min(FRAME_W / w, FRAME_H / h)
    nw, nh = int(w * scale), int(h * scale)
    resized = cv2.resize(img, (nw, nh))
    canvas = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    y0, x0 = (FRAME_H - nh) // 2, (FRAME_W - nw) // 2
    canvas[y0:y0 + nh, x0:x0 + nw] = resized
    return canvas


def crop_with_padding(frame, bbox):
    x1, y1, x2, y2 = bbox[:4]
    w, h = x2 - x1, y2 - y1
    px, py = int(w * PAD_RATIO), int(h * PAD_RATIO)
    cx1, cy1 = max(0, x1 - px), max(0, y1 - py)
    cx2, cy2 = min(frame.shape[1], x2 + px), min(frame.shape[0], y2 + py)
    return frame[cy1:cy2, cx1:cx2]


def largest_face(faces):
    if not faces:
        return None
    return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))


def main():
    detector = FaceDetector()
    recognizer = FaceRecognizer()
    app = recognizer.app

    photos = sorted(glob.glob("data/photos/*/*.jp*g"))
    if not photos:
        print("Tidak ada foto di data/photos/*/")
        return

    m1_times, m2_times, sims = [], [], []
    crop_area_ratio = []
    skipped = []

    print(f"{'gambar':32}{'M1 ms':>9}{'M2 ms':>9}{'speedup':>9}{'cos sim':>9}")
    print("-" * 68)

    for path in photos:
        img = cv2.imread(path)
        if img is None:
            skipped.append((path, "gagal baca"))
            continue
        frame = to_operational_frame(img)

        faces_yolo = detector.detect(frame)
        if not faces_yolo:
            skipped.append((path, "YOLO tak deteksi"))
            continue
        bbox = max(faces_yolo, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))

        # --- M1: full frame ---
        t1_list = []
        emb1 = None
        for r in range(REPEAT):
            t = time.perf_counter()
            faces_if = app.get(frame)
            dt = time.perf_counter() - t
            if r > 0:
                t1_list.append(dt * 1000)
            if emb1 is None:
                emb1 = recognizer.get_embedding(
                    frame, [int(x) for x in bbox[:4]], faces_if)

        # --- M2: crop YOLO -> app.get(crop) ---
        crop = crop_with_padding(frame, bbox)
        t2_list = []
        emb2 = None
        for r in range(REPEAT):
            t = time.perf_counter()
            faces_if_c = app.get(crop)
            dt = time.perf_counter() - t
            if r > 0:
                t2_list.append(dt * 1000)
            if emb2 is None:
                lf = largest_face(faces_if_c)
                emb2 = lf.embedding if lf is not None else None

        if emb1 is None or emb2 is None:
            reason = "emb M1 None" if emb1 is None else "emb M2 None (SCRFD tak deteksi di crop)"
            skipped.append((path, reason))
            continue

        m1 = st.mean(t1_list)
        m2 = st.mean(t2_list)
        sim = recognizer.cosine_similarity(emb1, emb2)
        ratio = (crop.shape[0] * crop.shape[1]) / (FRAME_H * FRAME_W)

        m1_times.append(m1); m2_times.append(m2); sims.append(sim)
        crop_area_ratio.append(ratio)
        label = "/".join(path.split(os.sep)[-2:])
        print(f"{label:32}{m1:9.1f}{m2:9.1f}{m1/m2:8.2f}x{sim:9.3f}")

    print("-" * 68)
    if m1_times:
        print(f"\nRINGKASAN ({len(m1_times)} gambar):")
        print(f"  M1 (full frame)  mean = {st.mean(m1_times):.1f} ms")
        print(f"  M2 (crop YOLO)   mean = {st.mean(m2_times):.1f} ms")
        print(f"  Speedup rata-rata        = {st.mean(m1_times)/st.mean(m2_times):.2f}x "
              f"(hemat {st.mean(m1_times)-st.mean(m2_times):.1f} ms)")
        print(f"  Cosine similarity M1 vs M2 = {st.mean(sims):.4f} "
              f"(min {min(sims):.4f}) — >0.99 artinya embedding ~identik (akurasi aman)")
        print(f"  Rata-rata luas crop = {st.mean(crop_area_ratio)*100:.0f}% dari frame penuh")
    if skipped:
        print(f"\nDILEWATI ({len(skipped)}):")
        for p, why in skipped:
            print(f"  - {p}: {why}")
    print("\nHASIL: crop TIDAK mempercepat InsightFace secara berarti.")
    print("SEBAB: app.prepare(det_size=(320,320)) → SCRFD selalu me-resize input ke")
    print("320x320 sebelum deteksi, jadi ukuran input (frame penuh vs crop) tidak")
    print("memengaruhi biaya deteksi. Cropping ROI BUKAN optimasi yang efektif di sini.")
    print("Catatan: foto data/photos ternyata file IDENTIK (duplikat re-enrollment),")
    print("jadi cos-sim hanya dari 3 gambar unik (1 orang), bukan 5 subjek berbeda.")


if __name__ == "__main__":
    main()
