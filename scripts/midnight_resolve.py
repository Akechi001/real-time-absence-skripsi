#!/usr/bin/env python3
"""
scripts/midnight_resolve.py — entry point untuk cron/launchd.

Tugas:
  1. Resolve absensi harian untuk semua tanggal yang belum diproses
     (sampai hari kemarin).
  2. Log hasil ke stdout (di-capture launchd → file log).

Cara pakai manual:
  source venv/bin/activate
  python scripts/midnight_resolve.py

Cara setup otomatis di macOS:
  Lihat scripts/MIDNIGHT_SETUP.md
"""

import os
import sys
from datetime import datetime, date, timedelta

# Tambahkan project root ke path supaya import config + src.* jalan
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from src.database.operations import (
    get_unresolved_dates,
    resolve_attendance_for_date,
)


def main():
    started = datetime.now()
    print(f"=== midnight_resolve mulai @ {started.isoformat()} ===")

    yesterday = date.today() - timedelta(days=1)
    pending = get_unresolved_dates(until_date=yesterday)

    if not pending:
        print(f"Tidak ada tanggal yang butuh di-resolve (cek sampai {yesterday}).")
        print(f"=== selesai @ {datetime.now().isoformat()} ===")
        return 0

    print(f"Ditemukan {len(pending)} tanggal yang perlu di-resolve:")
    total_inserted = 0
    for d in pending:
        n = resolve_attendance_for_date(d)
        total_inserted += n
        print(f"  • {d}: {n} karyawan diproses")

    elapsed = (datetime.now() - started).total_seconds()
    print(f"=== selesai @ {datetime.now().isoformat()} "
          f"(total insert: {total_inserted}, durasi: {elapsed:.2f}s) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
