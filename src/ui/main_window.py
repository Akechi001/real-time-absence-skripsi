# src/ui/main_window.py - Main Window Dashboard

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.ui.theme import get_colors, get_button_colors, hover_color


class MainWindow:
    def __init__(self, root):
        self.root = root
        self.colors = get_colors()

        self.root.title("Sistem Absensi Wajah - Universitas Ciputra Makassar")
        self.root.geometry("650x600")
        self.root.resizable(False, False)
        self.root.configure(bg=self.colors['bg_primary'])

        self._center_window()

        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after_idle(self.root.attributes, '-topmost', False)

        self._create_widgets()

    def _center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def _create_widgets(self):
        main_frame = tk.Frame(
            self.root,
            bg=self.colors['bg_primary'],
            padx=40,
            pady=30
        )
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ========== HEADER ==========
        header_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        header_frame.pack(fill=tk.X, pady=(0, 20))

        header_label = tk.Label(
            header_frame,
            text="SISTEM ABSENSI WAJAH",
            font=("Helvetica", 22, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_primary']
        )
        header_label.pack()

        subtitle_label = tk.Label(
            header_frame,
            text="Universitas Ciputra Surabaya - Kampus Makassar",
            font=("Helvetica", 11),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_primary']
        )
        subtitle_label.pack(pady=(5, 0))

        # ========== SEPARATOR ==========
        separator = tk.Frame(
            main_frame,
            bg=self.colors['border'],
            height=2
        )
        separator.pack(fill='x', pady=(0, 25))

        # ========== BUTTONS ==========
        button_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        button_frame.pack(fill=tk.BOTH, expand=True)

        self._create_button(
            button_frame,
            text="➕  Tambah Karyawan Baru",
            button_type='green',
            command=self._on_add_karyawan
        )

        self._create_button(
            button_frame,
            text="📋  Daftar Karyawan",
            button_type='blue',
            command=self._on_list_karyawan
        )

        self._create_button(
            button_frame,
            text="🎥  Mulai Mode Absensi",
            button_type='orange',
            command=self._on_start_attendance
        )

        self._create_button(
            button_frame,
            text="📊  Lihat Log Absensi",
            button_type='purple',
            command=self._on_view_logs
        )

        # ========== FOOTER ==========
        footer_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(20, 0))

        footer_label = tk.Label(
            footer_frame,
            text="© 2026 - Skripsi Enrico Kevin Ariantho",
            font=("Helvetica", 9),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_primary']
        )
        footer_label.pack()

    def _create_button(self, parent, text, button_type, command):
        btn_colors = get_button_colors(button_type)
        bg_color = btn_colors['bg']
        fg_color = btn_colors['fg']

        # macOS workaround: tk.Button bg di-ignore, pakai Frame sebagai container
        btn_container = tk.Frame(
            parent,
            bg=bg_color,
            highlightthickness=0,
            bd=0
        )
        btn_container.pack(fill=tk.X, pady=8)

        btn = tk.Label(
            btn_container,
            text=text,
            font=("Helvetica", 13, "bold"),
            bg=bg_color,
            fg=fg_color,
            cursor='hand2',
            padx=20,
            pady=18
        )
        btn.pack(fill=tk.BOTH, expand=True)

        # Bind click event
        def on_click(e):
            command()

        def on_enter(e):
            new_color = hover_color(bg_color)
            btn_container.config(bg=new_color)
            btn.config(bg=new_color)

        def on_leave(e):
            btn_container.config(bg=bg_color)
            btn.config(bg=bg_color)

        btn.bind("<Button-1>", on_click)
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        btn_container.bind("<Button-1>", on_click)
        btn_container.bind("<Enter>", on_enter)
        btn_container.bind("<Leave>", on_leave)

        return btn_container

    # ========== Event Handlers ==========

    def _on_add_karyawan(self):
        """Buka window enrollment"""
        from src.ui.enrollment_window import open_enrollment_window
        open_enrollment_window(self.root)

    def _on_list_karyawan(self):
        from src.ui.karyawan_list import open_karyawan_list
        open_karyawan_list(self.root)

    def _on_start_attendance(self):
        """Mulai mode attendance dengan subprocess (di thread terpisah)"""
        import subprocess
        import sys
        import threading

        # Konfirmasi
        confirm = messagebox.askyesno(
            "Mulai Mode Absensi",
            "Sistem akan menjalankan mode absensi.\n\n"
            "📌 Cara kerja:\n"
            "  • Window UI akan di-minimize\n"
            "  • Kamera akan terbuka untuk attendance\n"
            "  • Tekan Q (atau tutup window kamera) untuk berhenti\n"
            "  • UI akan muncul lagi setelah mode absensi ditutup\n\n"
            "Lanjutkan?"
        )

        if not confirm:
            return

        # Path ke main.py
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        main_script = os.path.join(project_root, 'main.py')

        if not os.path.exists(main_script):
            messagebox.showerror(
                "Error",
                f"File main.py tidak ditemukan di:\n{main_script}"
            )
            return

        # Minimize UI window
        self.root.iconify()

        # Run subprocess di thread terpisah supaya UI tidak freeze
        def run_attendance():
            try:
                result = subprocess.run(
                    [sys.executable, main_script],
                    cwd=project_root
                )
                return_code = result.returncode
            except Exception as e:
                return_code = -1
                print(f"Error running attendance: {e}")

            # Kembali ke main thread untuk update UI
            self.root.after(0, lambda: self._on_attendance_finished(return_code))

        # Jalankan thread
        thread = threading.Thread(target=run_attendance, daemon=True)
        thread.start()


    def _on_attendance_finished(self, return_code):
        """Callback saat attendance selesai - dipanggil di main thread"""
        # Restore UI window
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

        if return_code == 0:
            messagebox.showinfo(
                "Mode Absensi Selesai",
                "Mode absensi telah ditutup."
            )
        elif return_code == -1:
            messagebox.showerror(
                "Error",
                "Gagal menjalankan mode absensi.\nCek terminal untuk detail error."
            )
        else:
            messagebox.showwarning(
                "Mode Absensi Selesai",
                f"Mode absensi ditutup dengan kode: {return_code}\n"
                f"Cek terminal untuk detail error (jika ada)."
            )

    def _on_view_logs(self):
        """Buka window log absensi"""
        from src.ui.log_absensi import open_log_absensi
        open_log_absensi(self.root)


def main():
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()