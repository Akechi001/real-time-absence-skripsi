# src/database/operations.py - Operasi database

import psycopg2
import numpy as np
import pickle
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.database.db import get_connection

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

if __name__ == "__main__":
    templates = get_all_templates()
    print(f"✓ Total template wajah: {len(templates)}")