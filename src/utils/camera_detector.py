# src/utils/camera_detector.py - Enumerate available cameras
#
# Pakai nama generic "Kamera 1, Kamera 2, ..." biar gak misleading.
# Identifikasi kamera mana yang fisik = via tombol Preview di picker
# (yang panggil cv2.VideoCapture(idx) sama dengan attendance subprocess).

import cv2


def list_cameras(max_index: int = 6):
    """
    Enumerate kamera yang available + return list of dict:
        {'index': int, 'name': str, 'resolution': str, 'label': str}

    `index` = cv2.VideoCapture index (0-based).
    `name`  = display name 1-based ("Kamera 1" untuk cv2[0]).

    Args:
        max_index: scan index 0..max_index-1
    """
    cameras = []
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            cap.release()
            continue

        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            continue

        h, w = frame.shape[:2]
        resolution = f"{w}×{h}"
        name = f"Kamera {idx + 1}"
        label = f"{name}  ·  {resolution}"

        cameras.append({
            'index': idx,
            'name': name,
            'resolution': resolution,
            'label': label,
        })

    return cameras


if __name__ == "__main__":
    cams = list_cameras()
    if not cams:
        print("Tidak ada kamera terdeteksi")
    else:
        print(f"Ditemukan {len(cams)} kamera:")
        for c in cams:
            print(f"  [{c['index']}] {c['label']}")
