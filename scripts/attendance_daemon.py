#!/usr/bin/env python3
"""
scripts/attendance_daemon.py - Mode kamera 24 jam dengan auto-restart.

Loop spawn `main.py` sebagai subprocess. Kalau exit code:
  0       → intentional stop (user tekan Q), daemon berhenti
  != 0    → crash / unexpected exit, daemon restart subprocess

Crash throttle: kalau crash 3x dalam 60 detik, tunggu 30 detik
sebelum restart lagi (cegah infinite tight loop kalau bug fatal).

Stop graceful:
  - Bikin file `logs/STOP` → daemon detect & exit di iterasi berikutnya
  - Atau kirim SIGTERM/SIGINT → propagate ke child subprocess
  - Atau hapus file aja udah cukup (daemon polling)

Pakai env CAMERA_INDEX_OVERRIDE untuk pilih kamera (sama dengan
mode normal dari UI camera picker).

Cara pakai:
    python scripts/attendance_daemon.py             # kamera default
    CAMERA_INDEX_OVERRIDE=1 python scripts/attendance_daemon.py
"""

import logging
import os
import resource
import signal
import subprocess
import sys
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler


# Project paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_SCRIPT = os.path.join(PROJECT_ROOT, 'main.py')
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs')
STOP_FILE = os.path.join(LOGS_DIR, 'STOP')
LOG_FILE = os.path.join(LOGS_DIR, 'attendance.log')

# Crash throttling
CRASH_WINDOW_SEC = 60
CRASH_LIMIT = 3
CRASH_BACKOFF_SEC = 30


def setup_logging():
    """Set up logger dengan TimedRotatingFileHandler (rotate jam 00:00 setiap hari).

    Output: logs/attendance.log (current), logs/attendance.log.YYYY-MM-DD (rotated).
    """
    os.makedirs(LOGS_DIR, exist_ok=True)

    handler = TimedRotatingFileHandler(
        LOG_FILE, when='midnight', backupCount=30, encoding='utf-8',
    )
    handler.suffix = "%Y-%m-%d"

    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [handler, stream_handler]


def run_daemon():
    log = logging.getLogger('daemon')

    # Guard double-instance via pidfile.
    # Tiap daemon load model ~500MB — kalau dua instance jalan = ~1GB
    # plus konflik cv2.VideoCapture pada kamera yang sama.
    pidfile = os.path.join(LOGS_DIR, 'daemon.pid')
    if os.path.exists(pidfile):
        try:
            with open(pidfile) as f:
                old_pid = int(f.read().strip())
            try:
                os.kill(old_pid, 0)  # check if alive
                log.error(f"Daemon sudah jalan (PID {old_pid}). Refuse start.")
                print(f"ERROR: daemon sudah jalan di PID {old_pid}", file=sys.stderr)
                sys.exit(3)
            except OSError:
                # PID lama sudah mati, file stale → lanjut
                log.info(f"Pidfile stale (PID {old_pid} sudah mati), dihapus.")
        except (ValueError, IOError):
            pass

    try:
        with open(pidfile, 'w') as f:
            f.write(str(os.getpid()))
    except OSError as e:
        log.warning(f"Gagal tulis pidfile: {e}")

    log.info("=" * 60)
    log.info(f"Daemon mulai (PID {os.getpid()})")
    log.info(f"Logs: {LOG_FILE}")
    log.info(f"Stop file: {STOP_FILE} (buat file ini untuk stop graceful)")
    cam = os.environ.get('CAMERA_INDEX_OVERRIDE')
    if cam:
        log.info(f"Kamera override: index {cam}")

    # Bersih dulu file STOP kalau ada (residual dari run sebelumnya)
    if os.path.exists(STOP_FILE):
        try:
            os.remove(STOP_FILE)
            log.info("File STOP residual dihapus.")
        except OSError:
            pass

    crash_times = []
    iteration = 0

    # Handle SIGTERM/SIGINT supaya daemon bisa di-stop dengan kill / Ctrl-C.
    # Saat sinyal datang, taruh STOP file biar loop exit at iterasi berikutnya.
    def _on_signal(signum, _frame):
        log.warning(f"Sinyal {signum} diterima — minta stop graceful.")
        try:
            open(STOP_FILE, 'w').close()
        except OSError:
            pass

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    while True:
        if os.path.exists(STOP_FILE):
            log.info("STOP file terdeteksi — daemon berhenti.")
            try:
                os.remove(STOP_FILE)
            except OSError:
                pass
            break

        iteration += 1
        # Log RSS daemon process — bantu post-mortem kalau RAM bocor.
        # Di macOS, ru_maxrss dalam bytes; di Linux, dalam KB.
        try:
            rss_raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            rss_mb = rss_raw / (1024 * 1024) if sys.platform == 'darwin' else rss_raw / 1024
            log.info(f"[Iter {iteration}] Spawning attendance subprocess... "
                     f"(daemon peak RSS: {rss_mb:.1f} MB)")
        except Exception:
            log.info(f"[Iter {iteration}] Spawning attendance subprocess...")
        started = datetime.now()

        try:
            result = subprocess.run(
                [sys.executable, MAIN_SCRIPT],
                cwd=PROJECT_ROOT,
                env=os.environ.copy(),
            )
            rc = result.returncode
        except KeyboardInterrupt:
            # Re-raise bukan crash — propagate
            log.info("KeyboardInterrupt di daemon level, exit.")
            break
        except Exception as e:
            log.exception(f"Gagal spawn subprocess: {e}")
            rc = -999

        elapsed = (datetime.now() - started).total_seconds()
        log.info(f"[Iter {iteration}] Subprocess exit code {rc} setelah {elapsed:.1f}s")

        if rc == 0:
            log.info("Exit code 0 (intentional stop). Daemon berhenti.")
            break

        # Exit code 2 = pre-emptive restart (uptime lewat batas).
        # Bukan crash — gak perlu di-throttle.
        if rc == 2:
            log.info("Exit code 2 (pre-emptive restart untuk mitigasi memory). "
                     "Spawn proses baru dalam 3s...")
            time.sleep(3)
            continue

        # Crash detected — track timing untuk throttle
        now = time.time()
        crash_times.append(now)
        crash_times = [t for t in crash_times if now - t <= CRASH_WINDOW_SEC]

        if len(crash_times) >= CRASH_LIMIT:
            log.warning(
                f"Crash {len(crash_times)}x dalam {CRASH_WINDOW_SEC}s — "
                f"backoff {CRASH_BACKOFF_SEC}s sebelum restart..."
            )
            time.sleep(CRASH_BACKOFF_SEC)
            crash_times.clear()
        else:
            log.info(f"Crash counter: {len(crash_times)}/{CRASH_LIMIT}. Restart 3s lagi.")
            time.sleep(3)

    log.info(f"Daemon selesai (total iterasi: {iteration})")
    log.info("=" * 60)

    # Cleanup pidfile
    try:
        if os.path.exists(pidfile):
            os.remove(pidfile)
    except OSError:
        pass


if __name__ == "__main__":
    setup_logging()
    try:
        run_daemon()
    except Exception:
        logging.getLogger('daemon').exception("Daemon fatal error")
        sys.exit(2)
