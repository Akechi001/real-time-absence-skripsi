# src/database/operations.py - Operasi database

import psycopg2
import numpy as np
import pickle
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.database.db import get_connection

def get_all_karyawan():
    """Ambil semua karyawan terdaftar (termasuk yang belum ada template)"""
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

def get_last_event(id_karyawan):
    """Ambil event absensi terakhir karyawan"""
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute("""
                       SELECT jenis_event, timestamp
                       FROM log_absensi
                       WHERE id_karyawan = %s
                       ORDER BY timestamp DESC
                           LIMIT 1
                       """, (id_karyawan,))
        row = cursor.fetchone()
        if row:
            return {'jenis_event': row[0], 'timestamp': row[1]}
        return None
    except Exception as e:
        print(f"Error get_last_event: {e}")
        return None
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
            WHERE 1=1
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
                COUNT(*) FILTER (WHERE DATE(timestamp) = CURRENT_DATE) AS today_log,
                COUNT(*) FILTER (WHERE timestamp >= CURRENT_DATE - INTERVAL '7 days') AS week_log,
                COUNT(*) FILTER (WHERE jenis_event = 'check-in') AS total_checkin,
                COUNT(*) FILTER (WHERE jenis_event = 'check-out') AS total_checkout,
                COUNT(DISTINCT id_karyawan) AS unique_karyawan
            FROM log_absensi
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
    """Ambil list karyawan untuk dropdown filter (hanya yang punya log)"""
    conn = get_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT k.id_karyawan, k.nama
            FROM karyawan k
            JOIN log_absensi l ON k.id_karyawan = l.id_karyawan
            ORDER BY k.nama ASC
        """)
        rows = cursor.fetchall()
        return [{'id': row[0], 'nama': row[1]} for row in rows]
    except Exception as e:
        print(f"Error get_karyawan_dropdown_list: {e}")
        return []
    finally:
        conn.close()

if __name__ == "__main__":
    templates = get_all_templates()
    print(f"✓ Total template wajah: {len(templates)}")