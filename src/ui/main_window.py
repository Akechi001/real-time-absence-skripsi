# src/ui/main_window.py - Dashboard SaaS dengan CustomTkinter (rounded modern)

import os
import sys
import subprocess

import customtkinter as ctk
from tkinter import messagebox

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


# ---- Global ctk config ----
ctk.set_appearance_mode("system")        # follow macOS light/dark
ctk.set_default_color_theme("blue")      # accent


SIDEBAR_WIDTH = 240
WINDOW_W, WINDOW_H = 1280, 760

# Interval auto-refresh page aktif (ms).
# 30 detik dipilih untuk reduce churn — auto-refresh tiap 5 detik bikin
# DB query + Treeview redraw yang gak perlu kalau user gak aktif melihat.
AUTO_REFRESH_INTERVAL_MS = 30000


# Warna sidebar — selalu navy gelap tanpa peduli mode
SIDEBAR_BG       = "#1f2937"
SIDEBAR_HOVER    = "#374151"
SIDEBAR_ACTIVE   = "#3b82f6"
SIDEBAR_TEXT     = "#9ca3af"
SIDEBAR_TEXT_ACT = "#ffffff"
SIDEBAR_MUTED    = "#6b7280"
SIDEBAR_LOGO_FG  = "#ffffff"

NAV_ITEMS = [
    ('home',     '📊', 'Dashboard'),
    ('karyawan', '👥', 'Karyawan'),
    ('log',      '📋', 'Log Absensi'),
]


class DashboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistem Absensi Wajah — STIE Ciputra Makassar")
        self.root.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.root.minsize(1100, 660)
        self._center_window()

        # Grid: sidebar | content
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self.pages = {}
        self.current_name = None
        self.nav_buttons = {}
        self._auto_refresh_job = None
        self._auto_refresh_paused = False  # paused saat subprocess attendance jalan

        # Remember pilihan kamera terakhir antar Mulai Absensi (in-memory)
        self._last_camera_index = None

        self._build_sidebar()
        self._build_content_area()
        self.show_page('home')
        self._tick_auto_refresh()

    def _center_window(self):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (WINDOW_W // 2)
        y = (self.root.winfo_screenheight() // 2) - (WINDOW_H // 2)
        self.root.geometry(f'{WINDOW_W}x{WINDOW_H}+{x}+{y}')

    # ============================================================
    # SIDEBAR
    # ============================================================

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(
            self.root,
            width=SIDEBAR_WIDTH,
            corner_radius=0,
            fg_color=SIDEBAR_BG,
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)  # nav button isi full lebar
        sidebar.grid_rowconfigure(99, weight=1)    # footer dorong ke bawah

        # ----- Logo -----
        logo_box = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_box.grid(row=0, column=0, sticky="ew", padx=24, pady=(30, 28))

        ctk.CTkLabel(
            logo_box, text="🎓",
            font=ctk.CTkFont(size=32),
            text_color=SIDEBAR_LOGO_FG,
        ).pack(anchor='w')

        ctk.CTkLabel(
            logo_box, text="Absensi Wajah",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=SIDEBAR_LOGO_FG,
        ).pack(anchor='w', pady=(10, 0))

        ctk.CTkLabel(
            logo_box, text="STIE Ciputra Makassar",
            font=ctk.CTkFont(size=10),
            text_color=SIDEBAR_MUTED,
        ).pack(anchor='w')

        # ----- Section: MENU -----
        ctk.CTkLabel(
            sidebar, text="MENU",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=SIDEBAR_MUTED,
            anchor='w',
        ).grid(row=1, column=0, sticky="ew", padx=28, pady=(0, 6))

        # ----- Nav buttons -----
        for idx, (name, icon, label) in enumerate(NAV_ITEMS):
            btn = ctk.CTkButton(
                sidebar,
                text=f"  {icon}    {label}",
                anchor="w",
                fg_color="transparent",
                text_color=SIDEBAR_TEXT,
                hover_color=SIDEBAR_HOVER,
                corner_radius=10,
                height=44,
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda n=name: self.show_page(n),
            )
            btn.grid(row=2 + idx, column=0, sticky="ew", padx=14, pady=3)
            self.nav_buttons[name] = btn

        # ----- Footer -----
        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.grid(row=100, column=0, sticky="sew", padx=24, pady=20)

        ctk.CTkLabel(
            footer, text="© 2026 Enrico K. A.",
            font=ctk.CTkFont(size=9),
            text_color=SIDEBAR_MUTED,
        ).pack(anchor='w')

        ctk.CTkLabel(
            footer, text="Skripsi v1.0",
            font=ctk.CTkFont(size=9),
            text_color=SIDEBAR_MUTED,
        ).pack(anchor='w')

    def _build_content_area(self):
        self.content_area = ctk.CTkFrame(self.root, corner_radius=0)
        self.content_area.grid(row=0, column=1, sticky="nsew")

    # ============================================================
    # PAGE ROUTING
    # ============================================================

    def show_page(self, name):
        if self.current_name and self.current_name in self.pages:
            self.pages[self.current_name].pack_forget()

        if name not in self.pages:
            self.pages[name] = self._create_page(name)

        self.pages[name].pack(fill="both", expand=True)
        self.current_name = name
        self._update_active_nav()

        page = self.pages[name]
        if hasattr(page, 'on_show'):
            page.on_show()

    def _create_page(self, name):
        if name == 'home':
            from src.ui.home_page import HomePage
            return HomePage(self.content_area, app=self)
        if name == 'karyawan':
            from src.ui.karyawan_list import KaryawanListFrame
            return KaryawanListFrame(self.content_area, app=self)
        if name == 'log':
            from src.ui.log_absensi import LogAbsensiFrame
            return LogAbsensiFrame(self.content_area, app=self)
        raise ValueError(f"Unknown page: {name}")

    def _tick_auto_refresh(self):
        """Refresh page aktif tiap AUTO_REFRESH_INTERVAL_MS, self-rescheduling.

        Berhenti re-schedule kalau flag _auto_refresh_paused True (mis. saat
        subprocess attendance jalan, mencegah Tkinter redraw issue di macOS
        ketika window iconified).
        """
        if self._auto_refresh_paused:
            self._auto_refresh_job = None
            return

        page = self.pages.get(self.current_name)
        if page is not None and hasattr(page, 'refresh'):
            try:
                page.refresh()
            except Exception as e:
                # Jangan biarkan exception putus loop scheduling
                print(f"[auto-refresh] {self.current_name}: {e}")

        self._auto_refresh_job = self.root.after(
            AUTO_REFRESH_INTERVAL_MS, self._tick_auto_refresh
        )

    def _pause_auto_refresh(self):
        self._auto_refresh_paused = True
        if self._auto_refresh_job is not None:
            try:
                self.root.after_cancel(self._auto_refresh_job)
            except Exception:
                pass
            self._auto_refresh_job = None

    def _resume_auto_refresh(self):
        if not self._auto_refresh_paused:
            return
        self._auto_refresh_paused = False
        # Mulai chain baru
        self._tick_auto_refresh()

    def _update_active_nav(self):
        for n, btn in self.nav_buttons.items():
            if n == self.current_name:
                btn.configure(fg_color=SIDEBAR_ACTIVE, text_color=SIDEBAR_TEXT_ACT)
            else:
                btn.configure(fg_color="transparent", text_color=SIDEBAR_TEXT)

    # ============================================================
    # APP-LEVEL ACTIONS (DAEMON)
    # ============================================================

    def start_daemon(self):
        """Spawn attendance_daemon.py sebagai detached subprocess.

        Daemon punya logic auto-restart sendiri. UI gak track PID-nya —
        daemon mengelola lifecycle sendiri, stop via STOP file (lihat
        scripts/attendance_daemon.py).
        """
        # GUARD: cegah double-start. Tiap instance daemon ~500MB (InsightFace
        # + YOLO + MiniFASNet di-load fresh per process), jadi double-start
        # bisa langsung lonjak RAM ~1GB plus konflik cv2.VideoCapture.
        if self._is_daemon_running():
            messagebox.showwarning(
                "Mode Absensi Sudah Jalan",
                "Daemon attendance sudah berjalan di background.\n\n"
                "Untuk berhenti dulu, klik tombol \"Stop Absensi\"."
            )
            return

        from src.ui.camera_picker import CameraPickerDialog
        import config

        default_idx = self._last_camera_index
        if default_idx is None:
            default_idx = getattr(config, 'CAMERA_INDEX', 0)

        chosen_idx = CameraPickerDialog.ask(self.root, default_index=default_idx)
        if chosen_idx is None:
            return

        self._last_camera_index = chosen_idx

        confirm = messagebox.askyesno(
            "Mulai Absensi",
            "Mode absensi akan jalan di background (24 jam).\n\n"
            "📌 Cara kerja:\n"
            "  • Kamera terbuka, log absensi terus aktif\n"
            "  • Auto-restart kalau crash\n"
            "  • Log file: logs/attendance.log\n"
            "  • Untuk berhenti: klik tombol \"Stop Absensi\"\n\n"
            "Lanjutkan?"
        )
        if not confirm:
            return

        project_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        )))
        daemon_script = os.path.join(project_root, 'scripts', 'attendance_daemon.py')

        if not os.path.exists(daemon_script):
            messagebox.showerror(
                "Error", f"Script daemon tidak ditemukan:\n{daemon_script}"
            )
            return

        env = os.environ.copy()
        env['CAMERA_INDEX_OVERRIDE'] = str(chosen_idx)

        try:
            # Detached subprocess — fully independent dari UI process
            subprocess.Popen(
                [sys.executable, daemon_script],
                cwd=project_root, env=env,
                start_new_session=True,   # detach dari proses UI
            )
            messagebox.showinfo(
                "Absensi Dimulai",
                "Mode absensi jalan di background.\n\n"
                "Kamera index: " + str(chosen_idx) + "\n"
                "Log file: logs/attendance.log\n\n"
                "Untuk berhenti: klik \"Stop Absensi\"."
            )
        except Exception as e:
            messagebox.showerror(
                "Gagal Start Daemon", f"Error: {e}"
            )

    def stop_daemon(self):
        """Stop daemon dengan bikin file STOP."""
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        )))
        stop_file = os.path.join(project_root, 'logs', 'STOP')

        if not self._is_daemon_running():
            messagebox.showinfo(
                "Absensi Tidak Aktif",
                "Tidak ada mode absensi yang sedang jalan."
            )
            return

        try:
            os.makedirs(os.path.dirname(stop_file), exist_ok=True)
            open(stop_file, 'w').close()
            messagebox.showinfo(
                "Stop Sinyal Dikirim",
                "Daemon akan stop di iterasi berikutnya.\n"
                "Kalau attendance sedang jalan, tekan Q di window kamera dulu."
            )
        except Exception as e:
            messagebox.showerror("Gagal Kirim Stop", f"Error: {e}")

    def _is_daemon_running(self):
        """Cek apakah daemon jalan via pgrep nama script-nya."""
        try:
            out = subprocess.check_output(
                ['pgrep', '-f', 'attendance_daemon.py'],
                stderr=subprocess.DEVNULL,
            )
            pids = [int(x) for x in out.decode().strip().split('\n') if x.strip()]
            return len(pids) > 0
        except subprocess.CalledProcessError:
            return False
        except Exception:
            return False


def main():
    root = ctk.CTk()
    DashboardApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
