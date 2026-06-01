#!/usr/bin/env python3
"""
scripts/preview_camera.py - Preview kamera by index (subprocess utility).

Dipanggil dari src/ui/camera_picker.py via subprocess karena cv2.imshow
di macOS harus jalan di main thread proses (gak boleh dari thread Tkinter).

Cara pakai:
    python scripts/preview_camera.py <index> [label]

Tekan Q di window OpenCV untuk tutup.
"""

import sys
import cv2


def main():
    if len(sys.argv) < 2:
        print("Usage: preview_camera.py <index> [label]")
        return 1

    try:
        idx = int(sys.argv[1])
    except ValueError:
        print(f"Index harus integer, dapat: {sys.argv[1]!r}")
        return 1

    label = sys.argv[2] if len(sys.argv) >= 3 else f"Kamera {idx}"

    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        print(f"Gagal buka kamera index {idx}")
        return 1

    window = f"Preview Kamera #{idx}"
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Frame read failed")
                break

            overlay = f"PREVIEW: {label}   (tekan Q untuk tutup)"
            cv2.putText(
                frame, overlay, (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
            )
            cv2.imshow(window, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # Q atau ESC
                break

            # Detect window di-close manual (X button)
            try:
                if cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                    break
            except cv2.error:
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(main())
