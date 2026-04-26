# main.py - Entry point sistem absensi otomatis

import threading
import time
import sys
import os
import warnings
warnings.filterwarnings("ignore")

sys.path.append(os.path.dirname(__file__))

from src.attendance import AttendanceSystem
from src.enrollment import EnrollmentThread

# Shared events
stop_event = threading.Event()
enrollment_event = threading.Event()

if __name__ == "__main__":
    print("=== SISTEM ABSENSI OTOMATIS ===")
    print("Face Recognition + Liveness Detection")
    print("="*40)

    # Inisialisasi sistem
    system = AttendanceSystem()

    # Jalankan enrollment thread
    enrollment_thread = EnrollmentThread(stop_event, enrollment_event)
    enrollment_thread.start()

    try:
        # Jalankan attendance di main thread
        system.run(enrollment_thread, stop_event, enrollment_event)
    except KeyboardInterrupt:
        print("\nSistem dihentikan")
        stop_event.set()