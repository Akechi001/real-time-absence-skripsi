#!/bin/bash
# scripts/start.sh — startup checklist setelah laptop restart
#
# Jalankan: bash scripts/start.sh
#         atau:  ./scripts/start.sh  (kalau sudah chmod +x)

set -e

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$PROJECT_ROOT"

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
err()  { echo -e "${RED}✗${NC} $1"; }

echo "=== Startup check sistem absensi ==="
echo

# 1. Postgres
echo "[1/4] Cek PostgreSQL..."
if brew services list 2>/dev/null | grep -E "postgresql@18.*started" >/dev/null; then
    ok "Postgres sudah jalan"
else
    warn "Postgres belum jalan — starting..."
    brew services start postgresql@18
    sleep 2
    ok "Postgres started"
fi

# 2. Verifikasi koneksi DB
echo
echo "[2/4] Test koneksi database..."
source venv/bin/activate
if python src/database/db.py 2>&1 | grep -q "berhasil"; then
    ok "DB connection OK"
else
    err "Gagal konek ke DB — cek .env dan kredensial"
    exit 1
fi

# 3. launchd (resolver tengah malam)
echo
echo "[3/4] Cek launchd job (resolver tengah malam)..."
if launchctl list 2>/dev/null | grep -q "com.absensi.midnight"; then
    ok "launchd job aktif — resolver akan jalan otomatis jam 00:05"
else
    warn "launchd job belum terdaftar"
    warn "Setup ikutin: scripts/MIDNIGHT_SETUP.md"
    warn "Sementara: lazy fallback otomatis pas UI Log Absensi dibuka"
fi

# 4. Catch up resolve (kalau ada tanggal lampau yang belum di-resolve)
echo
echo "[4/4] Catch-up resolve untuk tanggal yang belum diproses..."
python scripts/midnight_resolve.py

echo
ok "Semua check selesai!"
echo
echo "Jalankan app: python ui_app.py"
