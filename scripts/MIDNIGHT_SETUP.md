# Setup Job Tengah Malam (Resolve Absensi Harian)

Sistem ini mencatat setiap deteksi kamera sebagai **lewatan (passage)** di `log_absensi`. Keputusan harian (check-in, check-out, terlambat, pulang cepat) dihitung **batch tengah malam** dan disimpan ke tabel `absensi_harian`.

Ada 3 cara untuk menjalankan resolver — bisa dipakai bareng.

---

## 1. Jalankan manual (test / catch-up)

```bash
cd ~/IdeaProjects/real-time-absence-skripsi
source venv/bin/activate
python scripts/midnight_resolve.py
```

Output:
```
=== midnight_resolve mulai @ 2026-05-13T00:05:00 ===
Ditemukan 2 tanggal yang perlu di-resolve:
  • 2026-05-11: 5 karyawan diproses
  • 2026-05-12: 4 karyawan diproses
=== selesai @ 2026-05-13T00:05:00.4 (total insert: 9, durasi: 0.30s) ===
```

Idempotent: aman dijalankan berkali-kali (tanggal yang sudah di-resolve di-skip via `resolve_log`).

---

## 2. Otomatis di macOS pakai launchd

1. **Bikin folder log:**
   ```bash
   mkdir -p ~/IdeaProjects/real-time-absence-skripsi/logs
   ```

2. **Salin plist dengan path yang diisi otomatis:**
   ```bash
   PROJECT_ROOT=~/IdeaProjects/real-time-absence-skripsi
   sed "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" \
       "$PROJECT_ROOT/scripts/com.absensi.midnight.plist" \
       > ~/Library/LaunchAgents/com.absensi.midnight.plist
   ```

3. **Daftarkan ke launchd:**
   ```bash
   launchctl load ~/Library/LaunchAgents/com.absensi.midnight.plist
   ```

4. **Verifikasi terdaftar:**
   ```bash
   launchctl list | grep absensi
   ```

5. **Test trigger sekarang (gak perlu nunggu tengah malam):**
   ```bash
   launchctl start com.absensi.midnight
   cat ~/IdeaProjects/real-time-absence-skripsi/logs/midnight_resolve.log
   ```

6. **Untuk uninstall:**
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.absensi.midnight.plist
   rm ~/Library/LaunchAgents/com.absensi.midnight.plist
   ```

**Catatan**: kalau laptop dalam keadaan sleep tepat jam 00:05, launchd akan jalankan job begitu laptop bangun. Tidak akan miss.

---

## 3. Lazy fallback di UI (otomatis tanpa setup)

Window "Log Absensi" akan otomatis memanggil `resolve_pending()` setiap kali dibuka — semua tanggal lampau yang belum di-resolve akan di-proses on-the-fly. Jadi walaupun launchd belum di-setup, data tetap konsisten begitu user buka UI.

---

## Linux / server (cron)

Tambahkan ke crontab user (`crontab -e`):

```
5 0 * * * cd /path/to/real-time-absence-skripsi && /path/to/venv/bin/python scripts/midnight_resolve.py >> logs/midnight_resolve.log 2>&1
```
