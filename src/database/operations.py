# src/database/operations.py - Operasi database

import psycopg2
import numpy as np
import pickle
import sys
import os
from datetime import datetime, date, time as dt_time, timedelta
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.database.db import get_connection
import config


def _parse_work_time(s):
    """Parse 'HH:MM' atau 'HH:MM:SS' string dari config jadi datetime.time"""
    parts = s.split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    sec = int(parts[2]) if len(parts) > 2 else 0
    return dt_time(h, m, sec)

def get_all_karyawan():
    """Ambil semua karyawan internal terdaftar (vendor di-skip).

    Vendor dihapus dari scope sistem ini — record vendor lama (kalau ada) tetap
    di DB tapi tidak ditampilkan. Lihat catatan di config.RESOLVE_ONLY_INTERNAL.
    """
    conn = get_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        cursor.execute("""
                       SELECT k.id_karyawan, k.nip, k.nama, k.jabatan,
                              k.jenis_karyawan, k.status_aktif,
                              CASE WHEN t.id_karyawan IS NOT NULL THEN TRUE ELSE FALSE END AS has_template
                       FROM karyawan k
                       LEFT JOIN template_wajah t ON k.id_karyawan = t.id_karyawan
                       WHERE k.jenis_karyawan = 'internal'
                       ORDER BY k.id_karyawan ASC
                       """)
        rows = cursor.fetchall()
        karyawan_list = []
        for row in rows:
            karyawan_list.append({
                'id_karyawan': row[0],
                'nip': row[1],
                'nama': row[2],
                'jabatan': row[3],
                'jenis_karyawan': row[4],
                'status_aktif': row[5],
                'has_template': row[6]
            })
        return karyawan_list
    except Exception as e:
        print(f"Error get_all_karyawan: {e}")
        return []
    finally:
        conn.close()


def delete_karyawan(id_karyawan):
    """Hapus karyawan beserta template wajahnya (soft delete - set status_aktif=False)"""
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        # Soft delete - tidak benar-benar hapus, hanya set status_aktif=False
        # Ini untuk preserve log_absensi yang reference ke karyawan ini
        cursor.execute("""
                       UPDATE karyawan
                       SET status_aktif = FALSE
                       WHERE id_karyawan = %s
                       """, (id_karyawan,))

        # Hapus template wajah supaya tidak terdeteksi lagi
        cursor.execute("""
                       DELETE FROM template_wajah
                       WHERE id_karyawan = %s
                       """, (id_karyawan,))

        conn.commit()
        print(f"✓ Karyawan ID {id_karyawan} dinonaktifkan dan template dihapus")
        return True
    except Exception as e:
        print(f"Error delete_karyawan: {e}")
        return False
    finally:
        conn.close()


def get_karyawan_by_id(id_karyawan):
    """Ambil detail satu karyawan by ID"""
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute("""
                       SELECT id_karyawan, nip, nama, jabatan, jenis_karyawan, status_aktif
                       FROM karyawan
                       WHERE id_karyawan = %s
                       """, (id_karyawan,))
        row = cursor.fetchone()
        if row:
            return {
                'id_karyawan': row[0],
                'nip': row[1],
                'nama': row[2],
                'jabatan': row[3],
                'jenis_karyawan': row[4],
                'status_aktif': row[5]
            }
        return None
    except Exception as e:
        print(f"Error get_karyawan_by_id: {e}")
        return None
    finally:
        conn.close()

def get_all_templates():
    """Ambil semua template wajah dari database"""
    conn = get_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        cursor.execute("""
                       SELECT k.id_karyawan, k.nama, t.embedding
                       FROM template_wajah t
                                JOIN karyawan k ON t.id_karyawan = k.id_karyawan
                       WHERE k.status_aktif = TRUE
                       """)
        rows = cursor.fetchall()
        templates = []
        for row in rows:
            embedding = pickle.loads(row[2])
            templates.append({
                'id_karyawan': row[0],
                'nama': row[1],
                'embedding': embedding
            })
        return templates
    except Exception as e:
        print(f"Error get_all_templates: {e}")
        return []
    finally:
        conn.close()

def save_karyawan_with_template(nip, nama, jabatan, jenis_karyawan, embedding,
                                versi_model="yolo26n_face+buffalo_l"):
    """
    Insert karyawan + template wajah dalam SATU transaksi.

    Mencegah orphan record: kalau template gagal, karyawan_insert juga rollback.
    Pakai ini di flow enrollment supaya tidak ada karyawan tanpa foto.

    Returns: id_karyawan kalau sukses, None kalau gagal (semua perubahan rollback).
    """
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        # 1. Insert karyawan
        cursor.execute("""
            INSERT INTO karyawan (nip, nama, jabatan, jenis_karyawan)
            VALUES (%s, %s, %s, %s)
            RETURNING id_karyawan
        """, (nip, nama, jabatan, jenis_karyawan))
        id_karyawan = cursor.fetchone()[0]

        # 2. Insert template — kalau gagal, rollback semuanya
        embedding_bytes = pickle.dumps(embedding)
        cursor.execute("""
            INSERT INTO template_wajah (id_karyawan, embedding, versi_model)
            VALUES (%s, %s, %s)
        """, (id_karyawan, psycopg2.Binary(embedding_bytes), versi_model))

        conn.commit()
        return id_karyawan
    except Exception as e:
        print(f"Error save_karyawan_with_template: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


def save_template(id_karyawan, embedding, versi_model="yolo26n_face+buffalo_l"):
    """Simpan template wajah ke database"""
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        embedding_bytes = pickle.dumps(embedding)
        cursor.execute("""
                       INSERT INTO template_wajah (id_karyawan, embedding, versi_model)
                       VALUES (%s, %s, %s)
                       """, (id_karyawan, psycopg2.Binary(embedding_bytes), versi_model))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error save_template: {e}")
        return False
    finally:
        conn.close()

def save_karyawan(nip, nama, jabatan, jenis_karyawan):
    """Simpan data karyawan baru"""
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO karyawan (nip, nama, jabatan, jenis_karyawan)
                       VALUES (%s, %s, %s, %s)
                           RETURNING id_karyawan
                       """, (nip, nama, jabatan, jenis_karyawan))
        id_karyawan = cursor.fetchone()[0]
        conn.commit()
        return id_karyawan
    except Exception as e:
        print(f"Error save_karyawan: {e}")
        return None
    finally:
        conn.close()

def save_log_absensi(id_karyawan, jenis_event, confidence_score,
                     status_liveness, keterangan="normal"):
    """Simpan log absensi"""
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO log_absensi
                       (id_karyawan, jenis_event, confidence_score, status_liveness, keterangan)
                       VALUES (%s, %s, %s, %s, %s)
                       """, (id_karyawan, jenis_event, confidence_score, status_liveness, keterangan))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error save_log_absensi: {e}")
        return False
    finally:
        conn.close()

def get_log_absensi(filter_date='all', filter_karyawan_id=None, filter_event='all', limit=500):
    """
    Ambil log absensi dengan filter

    Args:
        filter_date: 'today', 'week', 'month', 'all'
        filter_karyawan_id: ID karyawan tertentu, None = semua
        filter_event: 'check-in', 'check-out', 'all'
        limit: max baris yang di-return
    """
    conn = get_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor()

        # Build query dynamic dengan filter
        # Vendor di-skip — hanya tampilkan log karyawan internal.
        query = """
            SELECT
                l.id_log,
                l.id_karyawan,
                k.nip,
                k.nama,
                k.jabatan,
                l.jenis_event,
                l.timestamp,
                l.confidence_score,
                l.status_liveness,
                l.keterangan
            FROM log_absensi l
            JOIN karyawan k ON l.id_karyawan = k.id_karyawan
            WHERE k.jenis_karyawan = 'internal'
        """

        params = []

        # Filter date
        if filter_date == 'today':
            query += " AND DATE(l.timestamp) = CURRENT_DATE"
        elif filter_date == 'week':
            query += " AND l.timestamp >= CURRENT_DATE - INTERVAL '7 days'"
        elif filter_date == 'month':
            query += " AND l.timestamp >= CURRENT_DATE - INTERVAL '30 days'"
        # 'all' tidak ada filter date

        # Filter karyawan
        if filter_karyawan_id is not None:
            query += " AND l.id_karyawan = %s"
            params.append(filter_karyawan_id)

        # Filter event
        if filter_event in ('check-in', 'check-out'):
            query += " AND l.jenis_event = %s"
            params.append(filter_event)

        # Order & limit
        query += " ORDER BY l.timestamp DESC LIMIT %s"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        logs = []
        for row in rows:
            logs.append({
                'id_log': row[0],
                'id_karyawan': row[1],
                'nip': row[2],
                'nama': row[3],
                'jabatan': row[4],
                'jenis_event': row[5],
                'timestamp': row[6],
                'confidence_score': float(row[7]) if row[7] else 0.0,
                'status_liveness': row[8],
                'keterangan': row[9] or 'normal'
            })
        return logs
    except Exception as e:
        print(f"Error get_log_absensi: {e}")
        return []
    finally:
        conn.close()


def get_log_stats():
    """Ambil statistik log absensi"""
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) AS total_log,
                COUNT(*) FILTER (WHERE DATE(l.timestamp) = CURRENT_DATE) AS today_log,
                COUNT(*) FILTER (WHERE l.timestamp >= CURRENT_DATE - INTERVAL '7 days') AS week_log,
                COUNT(*) FILTER (WHERE l.jenis_event = 'check-in') AS total_checkin,
                COUNT(*) FILTER (WHERE l.jenis_event = 'check-out') AS total_checkout,
                COUNT(DISTINCT l.id_karyawan) AS unique_karyawan
            FROM log_absensi l
            JOIN karyawan k ON l.id_karyawan = k.id_karyawan
            WHERE k.jenis_karyawan = 'internal'
        """)

        row = cursor.fetchone()
        return {
            'total': row[0] or 0,
            'today': row[1] or 0,
            'week': row[2] or 0,
            'checkin': row[3] or 0,
            'checkout': row[4] or 0,
            'unique_karyawan': row[5] or 0
        }
    except Exception as e:
        print(f"Error get_log_stats: {e}")
        return None
    finally:
        conn.close()


def get_karyawan_dropdown_list():
    """Ambil list karyawan internal untuk dropdown filter (hanya yang punya log)"""
    conn = get_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT k.id_karyawan, k.nama
            FROM karyawan k
            JOIN log_absensi l ON k.id_karyawan = l.id_karyawan
            WHERE k.jenis_karyawan = 'internal'
            ORDER BY k.nama ASC
        """)
        rows = cursor.fetchall()
        return [{'id': row[0], 'nama': row[1]} for row in rows]
    except Exception as e:
        print(f"Error get_karyawan_dropdown_list: {e}")
        return []
    finally:
        conn.close()

# ============================================================
# ABSENSI HARIAN (resolver tengah malam + UI)
# ============================================================

def resolve_attendance_for_date(tanggal, collect_records=False):
    """
    Resolve absensi harian untuk satu tanggal.

    Untuk tiap karyawan (internal, kalau RESOLVE_ONLY_INTERNAL=True),
    ambil MIN(timestamp) = check_in, MAX(timestamp) = check_out dari log_absensi.
    - Cuma 1 lewatan: check_in & check_out NULL, keterangan='data tidak lengkap...'.
    - >= 2 lewatan: hitung status_terlambat & status_pulang_cepat dari WORK_START/END_TIME.

    Idempotent via ON CONFLICT DO NOTHING; resolve_log selalu di-upsert
    supaya tanggal yang sudah dikerjakan tidak diproses ulang.

    Args:
        collect_records: kalau True, kembalikan juga daftar baris yang BARU
            di-insert (untuk pengiriman payload anti-duplikat oleh pemanggil).

    Returns:
        - collect_records=False (default): int jumlah row baru di-insert.
        - collect_records=True: tuple (jumlah_baru, list_record_baru).
    """
    if isinstance(tanggal, str):
        tanggal = datetime.strptime(tanggal, "%Y-%m-%d").date()

    conn = get_connection()
    if not conn:
        return (0, []) if collect_records else 0

    work_start = _parse_work_time(config.WORK_START_TIME)
    work_end = _parse_work_time(config.WORK_END_TIME)
    only_internal = getattr(config, 'RESOLVE_ONLY_INTERNAL', True)

    try:
        cursor = conn.cursor()

        query = """
            SELECT l.id_karyawan,
                   k.nama,
                   MIN(l.timestamp) AS earliest,
                   MAX(l.timestamp) AS latest,
                   COUNT(*)         AS cnt
            FROM log_absensi l
            JOIN karyawan k ON l.id_karyawan = k.id_karyawan
            WHERE DATE(l.timestamp) = %s
              AND k.status_aktif = TRUE
        """
        params = [tanggal]
        if only_internal:
            query += " AND k.jenis_karyawan = 'internal'"
        query += " GROUP BY l.id_karyawan, k.nama"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        inserted = 0
        new_records = []
        for id_karyawan, nama, earliest, latest, cnt in rows:
            if cnt < 2:
                check_in = None
                check_out = None
                status_terlambat = None
                status_pulang_cepat = None
                jam_str = earliest.strftime("%H:%M") if earliest else "-"
                keterangan = f"data tidak lengkap (cuma 1 lewatan jam {jam_str})"
            else:
                check_in = earliest
                check_out = latest
                status_terlambat = earliest.time() > work_start
                status_pulang_cepat = latest.time() < work_end
                bits = []
                if status_terlambat:
                    bits.append("terlambat")
                if status_pulang_cepat:
                    bits.append("pulang cepat")
                keterangan = ", ".join(bits) if bits else "normal"

            cursor.execute("""
                INSERT INTO absensi_harian
                    (id_karyawan, tanggal, check_in_time, check_out_time,
                     status_terlambat, status_pulang_cepat, keterangan)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id_karyawan, tanggal) DO NOTHING
            """, (id_karyawan, tanggal, check_in, check_out,
                  status_terlambat, status_pulang_cepat, keterangan))
            if cursor.rowcount > 0:
                inserted += 1
                new_records.append({
                    'id_karyawan': id_karyawan,
                    'nama': nama,
                    'tanggal': tanggal,
                    'check_in': check_in,
                    'check_out': check_out,
                    'status_terlambat': status_terlambat,
                    'status_pulang_cepat': status_pulang_cepat,
                    'keterangan': keterangan,
                })

        cursor.execute("""
            INSERT INTO resolve_log (tanggal, karyawan_count)
            VALUES (%s, %s)
            ON CONFLICT (tanggal)
            DO UPDATE SET resolved_at = CURRENT_TIMESTAMP,
                          karyawan_count = EXCLUDED.karyawan_count
        """, (tanggal, len(rows)))

        conn.commit()
        return (inserted, new_records) if collect_records else inserted
    except Exception as e:
        print(f"Error resolve_attendance_for_date({tanggal}): {e}")
        conn.rollback()
        return (0, []) if collect_records else 0
    finally:
        conn.close()


def get_unresolved_dates(until_date=None):
    """
    Tanggal yang punya log_absensi tapi belum ada di resolve_log.
    Default: sampai hari kemarin (today tidak ikut, karena hari berjalan).
    Returns: list of date, ascending.
    """
    if until_date is None:
        until_date = date.today() - timedelta(days=1)
    elif isinstance(until_date, str):
        until_date = datetime.strptime(until_date, "%Y-%m-%d").date()

    conn = get_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT DATE(l.timestamp) AS tanggal
            FROM log_absensi l
            WHERE DATE(l.timestamp) <= %s
              AND DATE(l.timestamp) NOT IN (SELECT tanggal FROM resolve_log)
            ORDER BY tanggal ASC
        """, (until_date,))
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error get_unresolved_dates: {e}")
        return []
    finally:
        conn.close()


def resolve_pending(until_date=None):
    """
    Lazy fallback: resolve semua tanggal yang belum di-proses (sampai kemarin).
    Returns: dict {tanggal: count_inserted}.
    """
    dates = get_unresolved_dates(until_date)
    result = {}
    for d in dates:
        result[d] = resolve_attendance_for_date(d)
    return result


def get_absensi_harian(filter_date='all', filter_karyawan_id=None,
                      filter_status='all', limit=500):
    """
    Ambil absensi harian dengan filter.

    Args:
        filter_date: 'today', 'week', 'month', 'all'
        filter_karyawan_id: ID karyawan tertentu, None = semua
        filter_status: 'all', 'terlambat', 'pulang_cepat',
                       'terlambat_atau_cepat', 'normal', 'tidak_lengkap'
        limit: max row
    """
    conn = get_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        query = """
            SELECT a.id_absensi, a.id_karyawan, k.nip, k.nama, k.jabatan,
                   a.tanggal, a.check_in_time, a.check_out_time,
                   a.status_terlambat, a.status_pulang_cepat,
                   a.keterangan, a.resolved_at
            FROM absensi_harian a
            JOIN karyawan k ON a.id_karyawan = k.id_karyawan
            WHERE 1=1
        """
        params = []

        if filter_date == 'today':
            query += " AND a.tanggal = CURRENT_DATE"
        elif filter_date == 'week':
            query += " AND a.tanggal >= CURRENT_DATE - INTERVAL '7 days'"
        elif filter_date == 'month':
            query += " AND a.tanggal >= CURRENT_DATE - INTERVAL '30 days'"

        if filter_karyawan_id is not None:
            query += " AND a.id_karyawan = %s"
            params.append(filter_karyawan_id)

        if filter_status == 'terlambat':
            query += " AND a.status_terlambat = TRUE"
        elif filter_status == 'pulang_cepat':
            query += " AND a.status_pulang_cepat = TRUE"
        elif filter_status == 'terlambat_atau_cepat':
            query += " AND (a.status_terlambat = TRUE OR a.status_pulang_cepat = TRUE)"
        elif filter_status == 'normal':
            query += " AND a.status_terlambat = FALSE AND a.status_pulang_cepat = FALSE"
        elif filter_status == 'tidak_lengkap':
            query += " AND (a.check_in_time IS NULL OR a.check_out_time IS NULL)"

        query += " ORDER BY a.tanggal DESC, k.nama ASC LIMIT %s"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [{
            'id_absensi': r[0],
            'id_karyawan': r[1],
            'nip': r[2],
            'nama': r[3],
            'jabatan': r[4],
            'tanggal': r[5],
            'check_in_time': r[6],
            'check_out_time': r[7],
            'status_terlambat': r[8],
            'status_pulang_cepat': r[9],
            'keterangan': r[10] or '',
            'resolved_at': r[11],
        } for r in rows]
    except Exception as e:
        print(f"Error get_absensi_harian: {e}")
        return []
    finally:
        conn.close()


def predict_today_absensi(now=None):
    """
    Prediksi absensi_harian untuk **hari ini** — live, tidak disimpan ke DB.

    Berbeda dari resolve_attendance_for_date():
    - Selama jam kerja belum berakhir (now < WORK_END_TIME), last_passage
      hanya merepresentasikan "terakhir terlihat di kamera", bukan check-out
      asli. Status 'pulang_cepat' tidak diprediksi (karyawan mungkin masih
      di kantor). Semua karyawan ditandai belum_pulang=True.
    - Setelah WORK_END_TIME lewat, baru pakai logika midnight resolver:
      last_passage dianggap check-out, status pulang_cepat dihitung.

    Args:
        now: datetime sekarang (default: datetime.now()) — buat testable.
    """
    if now is None:
        now = datetime.now()

    conn = get_connection()
    if not conn:
        return []

    work_start = _parse_work_time(config.WORK_START_TIME)
    work_end = _parse_work_time(config.WORK_END_TIME)
    only_internal = getattr(config, 'RESOLVE_ONLY_INTERNAL', True)

    # Apakah jam kerja sudah berakhir? Pakai untuk memutuskan
    # apakah last_passage sudah representatif sebagai check-out.
    day_ended = now.time() >= work_end

    try:
        cursor = conn.cursor()
        query = """
            SELECT l.id_karyawan, k.nip, k.nama, k.jabatan,
                   MIN(l.timestamp) AS earliest,
                   MAX(l.timestamp) AS latest,
                   COUNT(*)         AS cnt
            FROM log_absensi l
            JOIN karyawan k ON l.id_karyawan = k.id_karyawan
            WHERE DATE(l.timestamp) = CURRENT_DATE
              AND k.status_aktif = TRUE
        """
        if only_internal:
            query += " AND k.jenis_karyawan = 'internal'"
        query += " GROUP BY l.id_karyawan, k.nip, k.nama, k.jabatan"
        query += " ORDER BY MIN(l.timestamp) ASC"

        cursor.execute(query)
        rows = cursor.fetchall()

        result = []
        for id_k, nip, nama, jabatan, earliest, latest, cnt in rows:
            terlambat = earliest.time() > work_start

            if not day_ended:
                # Hari belum berakhir — semua karyawan masih dianggap di kantor.
                # last_passage cuma "last seen", bukan check-out.
                result.append({
                    'id_karyawan': id_k,
                    'nip': nip,
                    'nama': nama,
                    'jabatan': jabatan,
                    'check_in_time': earliest,
                    'check_out_time': None,        # belum pasti
                    'last_seen': latest,           # info terakhir terlihat
                    'status_terlambat': terlambat,
                    'status_pulang_cepat': None,
                    'belum_pulang': True,
                })
            elif cnt < 2:
                # Hari sudah berakhir tapi cuma 1 lewatan → data tidak lengkap
                # (akan disebut "Tidak Lengkap" di midnight resolver).
                result.append({
                    'id_karyawan': id_k,
                    'nip': nip,
                    'nama': nama,
                    'jabatan': jabatan,
                    'check_in_time': earliest,
                    'check_out_time': None,
                    'last_seen': latest,
                    'status_terlambat': terlambat,
                    'status_pulang_cepat': None,
                    'belum_pulang': True,
                })
            else:
                # Hari sudah berakhir & ada >=2 lewatan → pakai logika
                # midnight resolver. last_passage = check-out beneran.
                result.append({
                    'id_karyawan': id_k,
                    'nip': nip,
                    'nama': nama,
                    'jabatan': jabatan,
                    'check_in_time': earliest,
                    'check_out_time': latest,
                    'last_seen': latest,
                    'status_terlambat': terlambat,
                    'status_pulang_cepat': latest.time() < work_end,
                    'belum_pulang': False,
                })
        return result
    except Exception as e:
        print(f"Error predict_today_absensi: {e}")
        return []
    finally:
        conn.close()


def get_absensi_harian_stats(filter_date='month'):
    """Stat ringkasan untuk card di UI."""
    conn = get_connection()
    if not conn:
        return None

    range_clause = {
        'today':  "tanggal = CURRENT_DATE",
        'week':   "tanggal >= CURRENT_DATE - INTERVAL '7 days'",
        'month':  "tanggal >= CURRENT_DATE - INTERVAL '30 days'",
        'all':    "TRUE",
    }.get(filter_date, "TRUE")

    try:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT
                COUNT(*)                                            AS total,
                COUNT(*) FILTER (WHERE status_terlambat = TRUE)     AS terlambat,
                COUNT(*) FILTER (WHERE status_pulang_cepat = TRUE)  AS pulang_cepat,
                COUNT(*) FILTER (WHERE check_in_time IS NULL
                                    OR check_out_time IS NULL)      AS tidak_lengkap
            FROM absensi_harian
            WHERE {range_clause}
        """)
        row = cursor.fetchone()
        return {
            'total':         row[0] or 0,
            'terlambat':     row[1] or 0,
            'pulang_cepat':  row[2] or 0,
            'tidak_lengkap': row[3] or 0,
        }
    except Exception as e:
        print(f"Error get_absensi_harian_stats: {e}")
        return None
    finally:
        conn.close()


if __name__ == "__main__":
    templates = get_all_templates()
    print(f"✓ Total template wajah: {len(templates)}")