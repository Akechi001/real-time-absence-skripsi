-- Migration 001 — Tabel absensi_harian + resolve_log
--
-- Tujuan: pisahkan pencatatan mentah (log_absensi → 'passage') dari
-- keputusan harian (check-in/check-out + status terlambat/pulang cepat).
--
-- Jalankan: psql -U postgres -d absensi_face -f scripts/migrations/001_absensi_harian.sql

BEGIN;

CREATE TABLE IF NOT EXISTS absensi_harian (
    id_absensi          SERIAL PRIMARY KEY,
    id_karyawan         INTEGER NOT NULL REFERENCES karyawan(id_karyawan),
    tanggal             DATE NOT NULL,
    check_in_time       TIMESTAMP,
    check_out_time      TIMESTAMP,
    status_terlambat    BOOLEAN,
    status_pulang_cepat BOOLEAN,
    keterangan          TEXT,
    resolved_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id_karyawan, tanggal)
);

CREATE INDEX IF NOT EXISTS idx_absensi_harian_tanggal
    ON absensi_harian(tanggal DESC);

CREATE INDEX IF NOT EXISTS idx_absensi_harian_karyawan_tanggal
    ON absensi_harian(id_karyawan, tanggal DESC);

CREATE TABLE IF NOT EXISTS resolve_log (
    tanggal         DATE PRIMARY KEY,
    resolved_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    karyawan_count  INTEGER NOT NULL DEFAULT 0
);

COMMIT;
