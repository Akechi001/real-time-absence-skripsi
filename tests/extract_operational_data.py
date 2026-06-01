"""
extract_operational_data.py — Export data operasional aktual dari DB
ke CSV untuk analisis akurasi recognition (Form A / Form B di skripsi).

Output:
- tests/data_lewatan_existing.csv     — semua lewatan log_absensi
- tests/statistik_per_karyawan.csv    — agregat per karyawan
- tests/hasil_resolver_existing.csv   — hasil resolver absensi_harian
- tests/summary_existing_data.txt     — ringkasan global metrik
"""

import sys
import os
import csv
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db import get_connection


def run_query_to_csv(conn, query, csv_path):
    """Jalankan query, simpan hasil ke CSV (header pakai column name dari cursor)."""
    cur = conn.cursor()
    cur.execute(query)
    rows = cur.fetchall()
    headers = [desc[0] for desc in cur.description]

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)

    return len(rows), headers


def main():
    tests_dir = os.path.dirname(os.path.abspath(__file__))

    conn = get_connection()
    if conn is None:
        print("✗ Tidak bisa connect database. Stop.")
        sys.exit(1)

    print("=" * 70)
    print("EXTRACT OPERATIONAL DATA — Sistem Absensi Wajah")
    print("STIE Ciputra Makassar — Skripsi Enrico Kevin Ariantho")
    print(f"Dijalankan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    # ─── Query 1: detail semua lewatan ───
    query_1 = """
        SELECT
          ROW_NUMBER() OVER (ORDER BY l.timestamp) AS "No",
          k.nama         AS "Nama_Karyawan",
          k.nip          AS "NIP",
          k.jabatan      AS "Jabatan",
          l.confidence_score AS "Confidence",
          l.status_liveness  AS "Liveness_Passed",
          l.timestamp    AS "Waktu_Deteksi",
          l.jenis_event  AS "Jenis_Event"
        FROM log_absensi l
        JOIN karyawan k ON l.id_karyawan = k.id_karyawan
        WHERE k.status_aktif = TRUE
        ORDER BY l.timestamp
    """
    path_1 = os.path.join(tests_dir, "data_lewatan_existing.csv")
    n1, _ = run_query_to_csv(conn, query_1, path_1)
    print(f"✓ Query 1 (detail lewatan)     : {n1:>5} rows → {os.path.basename(path_1)}")

    # ─── Query 2: statistik per karyawan ───
    query_2 = """
        SELECT
          k.nama AS "Nama_Karyawan",
          k.jabatan AS "Jabatan",
          COUNT(*) AS "Total_Lewatan",
          ROUND(AVG(l.confidence_score)::numeric, 4) AS "Avg_Confidence",
          ROUND(MIN(l.confidence_score)::numeric, 4) AS "Min_Confidence",
          ROUND(MAX(l.confidence_score)::numeric, 4) AS "Max_Confidence",
          SUM(CASE WHEN l.status_liveness = TRUE THEN 1 ELSE 0 END) AS "Liveness_Passed",
          ROUND(100.0 * SUM(CASE WHEN l.status_liveness = TRUE THEN 1 ELSE 0 END)
                / COUNT(*), 2) AS "Liveness_Rate_Pct"
        FROM log_absensi l
        JOIN karyawan k ON l.id_karyawan = k.id_karyawan
        WHERE k.status_aktif = TRUE
        GROUP BY k.id_karyawan, k.nama, k.jabatan
        ORDER BY "Total_Lewatan" DESC
    """
    path_2 = os.path.join(tests_dir, "statistik_per_karyawan.csv")
    n2, _ = run_query_to_csv(conn, query_2, path_2)
    print(f"✓ Query 2 (stats per karyawan) : {n2:>5} rows → {os.path.basename(path_2)}")

    # ─── Query 3: hasil resolver ───
    query_3 = """
        SELECT
          k.nama AS "Nama_Karyawan",
          ah.tanggal AS "Tanggal",
          ah.check_in_time AS "Check_In",
          ah.check_out_time AS "Check_Out",
          ah.status_terlambat AS "Terlambat",
          ah.status_pulang_cepat AS "Pulang_Cepat",
          ah.keterangan AS "Keterangan",
          ah.resolved_at AS "Waktu_Resolve"
        FROM absensi_harian ah
        JOIN karyawan k ON ah.id_karyawan = k.id_karyawan
        ORDER BY ah.tanggal DESC, k.nama
    """
    path_3 = os.path.join(tests_dir, "hasil_resolver_existing.csv")
    n3, _ = run_query_to_csv(conn, query_3, path_3)
    print(f"✓ Query 3 (hasil resolver)     : {n3:>5} rows → {os.path.basename(path_3)}")

    # ─── Aggregate stats untuk summary ───
    print()
    cur = conn.cursor()
    cur.execute("""
        SELECT
          COUNT(*) AS total_log,
          COUNT(DISTINCT l.id_karyawan) AS unique_karyawan,
          ROUND(AVG(l.confidence_score)::numeric, 4) AS avg_conf,
          ROUND(MIN(l.confidence_score)::numeric, 4) AS min_conf,
          ROUND(MAX(l.confidence_score)::numeric, 4) AS max_conf,
          SUM(CASE WHEN l.status_liveness = TRUE THEN 1 ELSE 0 END) AS liveness_pass_n,
          ROUND(100.0 * SUM(CASE WHEN l.status_liveness = TRUE THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0), 2) AS liveness_rate
        FROM log_absensi l
        JOIN karyawan k ON l.id_karyawan = k.id_karyawan
        WHERE k.status_aktif = TRUE
    """)
    row = cur.fetchone()
    if row is None:
        total_log, unique_kar, avg_conf, min_conf, max_conf = 0, 0, 0, 0, 0
        liv_pass, liv_rate = 0, 0
    else:
        total_log, unique_kar, avg_conf, min_conf, max_conf, liv_pass, liv_rate = row

    cur.execute("SELECT COUNT(DISTINCT tanggal) FROM absensi_harian")
    days_resolved = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM absensi_harian")
    total_harian = cur.fetchone()[0]

    cur.execute("SELECT MIN(tanggal), MAX(tanggal) FROM absensi_harian")
    date_range = cur.fetchone()
    earliest_date, latest_date = (date_range or (None, None))

    cur.execute("""
        SELECT
          COUNT(*) FILTER (WHERE status_terlambat = TRUE) AS terlambat,
          COUNT(*) FILTER (WHERE status_pulang_cepat = TRUE) AS pulang_cepat,
          COUNT(*) FILTER (WHERE check_in_time IS NULL OR check_out_time IS NULL)
              AS tidak_lengkap
        FROM absensi_harian
    """)
    ah_row = cur.fetchone()
    terlambat_n, pulang_cepat_n, tidak_lengkap_n = (ah_row or (0, 0, 0))

    conn.close()

    # ─── Tulis summary ───
    summary_path = os.path.join(tests_dir, "summary_existing_data.txt")
    lines = [
        "=" * 70,
        "RINGKASAN DATA OPERASIONAL — Sistem Absensi Wajah",
        "STIE Ciputra Makassar — Skripsi Enrico Kevin Ariantho (0806022210012)",
        f"Diekstrak pada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 70,
        "",
        "LOG ABSENSI (raw lewatan dari kamera)",
        "-" * 70,
        f"Total entri log_absensi            : {total_log}",
        f"Jumlah karyawan unik terdeteksi    : {unique_kar}",
        f"Average confidence score           : "
        f"{avg_conf if avg_conf is not None else 'N/A'}",
        f"Confidence score range             : "
        f"{min_conf} – {max_conf}",
        f"Liveness pass count                : "
        f"{liv_pass} / {total_log}",
        f"Liveness pass rate                 : "
        f"{liv_rate if liv_rate is not None else 0.0}%",
        "",
        "ABSENSI HARIAN (hasil resolver tengah malam)",
        "-" * 70,
        f"Jumlah hari ter-resolve            : {days_resolved}",
        f"Total entri absensi_harian         : {total_harian}",
        f"Rentang tanggal di absensi_harian  : "
        f"{earliest_date or 'N/A'} – {latest_date or 'N/A'}",
        f"Terlambat                          : {terlambat_n}",
        f"Pulang cepat                       : {pulang_cepat_n}",
        f"Data tidak lengkap                 : {tidak_lengkap_n}",
        "",
        "FILE OUTPUT",
        "-" * 70,
        f"  - data_lewatan_existing.csv      ({n1} rows)",
        f"  - statistik_per_karyawan.csv     ({n2} rows)",
        f"  - hasil_resolver_existing.csv    ({n3} rows)",
        "",
        "=" * 70,
    ]

    summary_text = "\n".join(lines)
    print(summary_text)

    with open(summary_path, "w") as f:
        f.write(summary_text)
        f.write("\n")
    print(f"\n✓ Summary saved: {summary_path}")


if __name__ == "__main__":
    main()
