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
from src.payload import send_payload


def _send_daily_payloads(records):
    """
    Kirim payload rekap harian ke backend kampus.

    SAFETY (versi paling aman):
      - Dipanggil SETELAH resolve (DB sudah commit), di luar transaksi DB →
        kegagalan kirim TIDAK bisa membatalkan penyimpanan rekap.
      - Tiap pengiriman dibungkus try/except sendiri → satu gagal tidak
        menghentikan yang lain, dan tidak pernah meng-crash job.
      - Hanya baris yang BARU di-insert yang diproses (anti-duplikat saat
        job di-run ulang / catch-up).
      - Baris 'data tidak lengkap' (cuma 1 lewatan, tanpa jam masuk/pulang
        valid) dilewati — tidak dikirim sebagai absensi sah.

    CATATAN: format payload di bawah masih DRAFT, menunggu konfirmasi
    5 pertanyaan ICT. send_payload saat ini hanya print (simulasi),
    belum POST ke endpoint nyata.
    """
    if not records:
        return

    print(f"--- Kirim payload rekap harian ({len(records)} baris baru) ---")
    sent = skipped = failed = 0

    for r in records:
        if r['check_in'] is None or r['check_out'] is None:
            skipped += 1
            continue

        payload = {
            'id_karyawan': r['id_karyawan'],
            'nama': r['nama'],
            'tanggal': r['tanggal'].isoformat(),
            'jam_masuk': r['check_in'].strftime('%H:%M:%S'),
            'jam_pulang': r['check_out'].strftime('%H:%M:%S'),
            'status_terlambat': bool(r['status_terlambat']),
            'status_pulang_cepat': bool(r['status_pulang_cepat']),
            'keterangan': r['keterangan'],
            'source': 'face_recognition_system',
            'jenis_payload': 'rekap_harian',
        }

        try:
            send_payload(payload)
            sent += 1
        except Exception as e:
            failed += 1
            print(f"  ⚠ Gagal kirim payload {r['id_karyawan']} "
                  f"{r['tanggal']}: {e}")

    print(f"--- Payload: {sent} terkirim, {skipped} dilewati (tidak lengkap), "
          f"{failed} gagal ---")


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
    all_new_records = []
    for d in pending:
        n, new_records = resolve_attendance_for_date(d, collect_records=True)
        total_inserted += n
        all_new_records.extend(new_records)
        print(f"  • {d}: {n} karyawan diproses")

    # Kirim payload rekap harian SETELAH semua resolve selesai (DB sudah commit).
    _send_daily_payloads(all_new_records)

    elapsed = (datetime.now() - started).total_seconds()
    print(f"=== selesai @ {datetime.now().isoformat()} "
          f"(total insert: {total_inserted}, durasi: {elapsed:.2f}s) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
