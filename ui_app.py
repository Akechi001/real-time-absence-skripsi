# ui_app.py - Entry point untuk UI Tkinter
#
# Ini adalah aplikasi UI utama untuk admin/ICT.
# Fungsi:
# - Tambah karyawan baru (dengan webcam enrollment)
# - Daftar karyawan terdaftar (CRUD)
# - Mulai mode absensi
# - Lihat log absensi
#
# Cara jalanin:
#   python ui_app.py

from src.ui.main_window import main

if __name__ == "__main__":
    main()