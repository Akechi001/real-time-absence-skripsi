# main.py - Entry point sistem absensi (CLI/subprocess)
#
# Mode absensi langsung tanpa UI dashboard.
# Untuk admin/ICT operations (enrollment, daftar karyawan, log), pakai ui_app.py.

import threading
import sys
import os
import warnings
warnings.filterwarnings("ignore")

sys.path.append(os.path.dirname(__file__))

# CRITICAL: apply ONNX SessionOptions patch SEBELUM import library apapun
# yang trigger insightface (face_recognizer, attendance, dll). Patch ini
# disable CPU arena memory pool yang penyebab utama leak.
from src.utils import onnx_patch  # noqa: F401

import config

# Limit PyTorch CPU thread cache (mitigasi memory leak ringan).
# Harus diset sebelum import torch atau model loaders.
try:
    import torch
    torch.set_num_threads(1)
except Exception:
    pass

# Env override dari UI camera picker — diset sebelum import AttendanceSystem
# supaya saat run() pakai config.CAMERA_INDEX, value-nya sudah ter-update.
_cam_override = os.environ.get('CAMERA_INDEX_OVERRIDE')
if _cam_override is not None:
    try:
        config.CAMERA_INDEX = int(_cam_override)
        print(f"📷 CAMERA_INDEX override dari UI: {config.CAMERA_INDEX}")
    except ValueError:
        print(f"⚠ CAMERA_INDEX_OVERRIDE bukan int: {_cam_override!r}, pakai default")

from src.attendance import AttendanceSystem

stop_event = threading.Event()

# Exit codes:
#   0 = intentional stop (user tekan Q) → daemon stop
#   2 = pre-emptive restart (uptime lewat MAX_UPTIME_SECONDS) → daemon spawn ulang
#   non-zero lain = crash → daemon spawn ulang (dengan throttle)

if __name__ == "__main__":
    print("=== SISTEM ABSENSI OTOMATIS ===")
    print("Face Recognition + Liveness Detection")
    print("Tekan Q di jendela kamera untuk keluar")
    print("=" * 40)

    system = AttendanceSystem()
    preemptive = False
    try:
        preemptive = system.run(stop_event) or False
    except KeyboardInterrupt:
        print("\nSistem dihentikan")
        stop_event.set()

    sys.exit(2 if preemptive else 0)
