-- Migration 002 — allow jenis_event='passage' di log_absensi
--
-- Konteks: setelah refactor passage-based (mei 2026), setiap deteksi
-- kamera disimpan sebagai 'passage' (lewatan mentah). Keputusan
-- check-in / check-out final dilakukan tengah malam ke tabel
-- absensi_harian.
--
-- Data lama tetap dipertahankan ('check-in' / 'check-out') — tidak
-- mengganggu midnight job yang query pakai timestamp, bukan label.
--
-- Jalankan: psql -U postgres -d absensi_face -f scripts/migrations/002_allow_passage_event.sql

BEGIN;

ALTER TABLE log_absensi
    DROP CONSTRAINT IF EXISTS log_absensi_jenis_event_check;

ALTER TABLE log_absensi
    ADD CONSTRAINT log_absensi_jenis_event_check
    CHECK (jenis_event IN ('passage', 'check-in', 'check-out'));

COMMIT;
