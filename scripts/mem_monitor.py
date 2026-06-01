#!/usr/bin/env python3
"""
scripts/mem_monitor.py — pantau RSS proses mode absensi.

Cara pakai:
  1. Buka 1 terminal: jalanin `python main.py` (mode absensi)
  2. Buka terminal kedua: jalanin `python scripts/mem_monitor.py`
  3. Biarkan beberapa jam, mem_monitor akan print RSS tiap 60 detik.

Output:
  [HH:MM:SS] RSS=512.3 MB  Δ=+0.0 MB  (sejak start: +0.0 MB)
  [HH:MM:SS] RSS=518.7 MB  Δ=+6.4 MB  (sejak start: +6.4 MB)
  ...

Kalau Δ stabil di ~0 atau fluktuatif (bukan monotonic naik), berarti gak ada
leak. Kalau Δ konsisten positif → leak masih ada.
"""

import os
import sys
import time
import subprocess
from datetime import datetime


def find_attendance_pid():
    """Cari pid proses 'python main.py' yang sedang jalan"""
    try:
        out = subprocess.check_output(['pgrep', '-f', 'python.*main\\.py'],
                                       text=True).strip()
        if not out:
            return None
        pids = [int(x) for x in out.split('\n') if x.strip()]
        # Filter — jangan ambil pid mem_monitor sendiri
        my_pid = os.getpid()
        pids = [p for p in pids if p != my_pid]
        return pids[0] if pids else None
    except subprocess.CalledProcessError:
        return None


def rss_mb(pid):
    """Ambil RSS (resident set size) dalam MB"""
    try:
        out = subprocess.check_output(
            ['ps', '-p', str(pid), '-o', 'rss='],
            text=True
        ).strip()
        return int(out) / 1024  # ps -o rss kasih KB
    except subprocess.CalledProcessError:
        return None


def main():
    interval = 60  # detik

    print("Mencari proses 'python main.py'...")
    pid = None
    while pid is None:
        pid = find_attendance_pid()
        if pid is None:
            print("  belum ketemu, retry 5 detik lagi...")
            time.sleep(5)

    print(f"✓ Found PID {pid}")
    print(f"Sampling RSS setiap {interval} detik. Ctrl-C untuk berhenti.")
    print()

    start_rss = rss_mb(pid)
    if start_rss is None:
        print("Gagal baca RSS — proses sudah exit?")
        sys.exit(1)

    print(f"[start]    RSS={start_rss:.1f} MB")
    prev_rss = start_rss
    samples = [start_rss]

    try:
        while True:
            time.sleep(interval)
            rss = rss_mb(pid)
            if rss is None:
                print("Proses sudah exit. Statistik:")
                break
            delta = rss - prev_rss
            since_start = rss - start_rss
            now = datetime.now().strftime('%H:%M:%S')
            sign = '+' if delta >= 0 else ''
            print(f"[{now}] RSS={rss:.1f} MB  "
                  f"Δ={sign}{delta:.1f} MB  "
                  f"(sejak start: {sign if since_start >= 0 else ''}{since_start:.1f} MB)")
            prev_rss = rss
            samples.append(rss)
    except KeyboardInterrupt:
        print()
        print("Stopped.")

    if len(samples) > 1:
        peak = max(samples)
        avg_growth_per_hour = (samples[-1] - samples[0]) / (len(samples) * interval / 3600)
        print()
        print(f"=== Ringkasan ({len(samples)} sample) ===")
        print(f"  Start:        {samples[0]:.1f} MB")
        print(f"  End:          {samples[-1]:.1f} MB")
        print(f"  Peak:         {peak:.1f} MB")
        print(f"  Total growth: {samples[-1] - samples[0]:+.1f} MB")
        print(f"  Avg / jam:    {avg_growth_per_hour:+.1f} MB/jam")


if __name__ == "__main__":
    main()
