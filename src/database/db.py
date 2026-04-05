# src/database/db.py - Koneksi dan operasi database

import psycopg2
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config

def get_connection():
    """Membuat koneksi ke database PostgreSQL"""
    try:
        conn = psycopg2.connect(**config.DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Error koneksi database: {e}")
        return None

def test_connection():
    """Test koneksi database"""
    conn = get_connection()
    if conn:
        print("✓ Koneksi database berhasil")
        conn.close()
        return True
    else:
        print("✗ Koneksi database gagal")
        return False

if __name__ == "__main__":
    test_connection()