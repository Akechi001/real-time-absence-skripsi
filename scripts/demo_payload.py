#!/usr/bin/env python3
"""
scripts/demo_payload.py — demo tampilan payload untuk presentasi/sidang.

Menampilkan dua jenis payload yang dihasilkan sistem, memakai fungsi ASLI
(build_payload + _send_daily_payloads) dengan data contoh — tanpa kamera
dan tanpa database, jadi aman dijalankan kapan saja.

  1. Payload PASSAGE  — dikirim real-time tiap lewatan terverifikasi.
  2. Payload REKAP    — dikirim setelah resolve tengah malam (check-in/out).

Cara pakai:
  source venv/bin/activate
  python3 scripts/demo_payload.py
"""

import os
import sys
from datetime import datetime, date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from src.payload import build_payload, send_payload
from scripts.midnight_resolve import _send_daily_payloads


def demo_passage():
    print("\n" + "=" * 60)
    print(" 1. PAYLOAD PASSAGE (real-time, tiap lewatan terverifikasi)")
    print("=" * 60)
    payload = build_payload(
        id_karyawan=1,
        nama="Reza Fabian",
        jenis_event="passage",
        confidence=0.8123,
        status_liveness=True,
    )
    send_payload(payload)


def demo_rekap():
    print("\n" + "=" * 60)
    print(" 2. PAYLOAD REKAP HARIAN (setelah resolve tengah malam)")
    print("=" * 60)
    records = [
        {'id_karyawan': 1, 'nama': 'Reza Fabian', 'tanggal': date(2026, 5, 31),
         'check_in': datetime(2026, 5, 31, 7, 42, 10),
         'check_out': datetime(2026, 5, 31, 16, 25, 3),
         'status_terlambat': True, 'status_pulang_cepat': True,
         'keterangan': 'terlambat, pulang cepat'},
        {'id_karyawan': 2, 'nama': 'Budi Santoso', 'tanggal': date(2026, 5, 31),
         'check_in': datetime(2026, 5, 31, 7, 10, 0),
         'check_out': datetime(2026, 5, 31, 17, 5, 0),
         'status_terlambat': False, 'status_pulang_cepat': False,
         'keterangan': 'normal'},
        {'id_karyawan': 3, 'nama': 'Citra Dewi', 'tanggal': date(2026, 5, 31),
         'check_in': None, 'check_out': None,
         'status_terlambat': None, 'status_pulang_cepat': None,
         'keterangan': 'data tidak lengkap (cuma 1 lewatan jam 08:00)'},
    ]
    _send_daily_payloads(records)


if __name__ == "__main__":
    print("\n### DEMO PAYLOAD SISTEM ABSENSI (data contoh) ###")
    demo_passage()
    demo_rekap()
    print("\n### selesai — payload di atas memakai fungsi asli sistem ###\n")
