# src/ui/home_page.py - Dashboard home page (CustomTkinter)

import os
import sys
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.database.operations import (
    get_all_karyawan, get_log_stats, get_absensi_harian_stats,
    predict_today_absensi, resolve_pending,
)


CARD_RADIUS = 14
ACCENT_BLUE = "#3b82f6"
ACCENT_GREEN = "#10b981"
ACCENT_RED = "#ef4444"
ACCENT_ORANGE = "#f59e0b"


class HomePage(ctk.CTkFrame):
    def __init__(self, parent, app=None):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self.app = app
        self._build_widgets()

    def _build_widgets(self):
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=36, pady=30)

        # ---- HEADER ----
        header = ctk.CTkFrame(wrap, fg_color="transparent")
        header.pack(fill="x", pady=(0, 24))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box, text="Dashboard",
            font=ctk.CTkFont(size=26, weight="bold"),
            anchor='w',
        ).pack(anchor='w')

        ctk.CTkLabel(
            title_box,
            text="Selamat datang! Mulai absensi atau kelola data karyawan.",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            anchor='w',
        ).pack(anchor='w', pady=(4, 0))

        # Tombol Mulai Absensi (daemon mode dengan auto-restart)
        self.btn_attendance = ctk.CTkButton(
            header, text="🎥   Mulai Absensi",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=ACCENT_GREEN, hover_color="#0ea271",
            corner_radius=12, height=44,
            command=self._on_toggle_attendance,
        )
        self.btn_attendance.pack(side="right")

        # ---- STAT CARDS ----
        stats_row = ctk.CTkFrame(wrap, fg_color="transparent")
        stats_row.pack(fill="x", pady=(0, 28))
        for i in range(4):
            stats_row.grid_columnconfigure(i, weight=1, uniform="card")

        self.card_karyawan = self._create_stat_card(
            stats_row, 0, "Total Karyawan Aktif", "👥", ACCENT_BLUE
        )
        self.card_today = self._create_stat_card(
            stats_row, 1, "Lewatan Hari Ini", "📍", ACCENT_GREEN
        )
        self.card_terlambat = self._create_stat_card(
            stats_row, 2, "Terlambat Hari Ini", "⏰", ACCENT_RED
        )
        self.card_cepat = self._create_stat_card(
            stats_row, 3, "Pulang Cepat Hari Ini", "🏃", ACCENT_ORANGE
        )

        # ---- ABSENSI HARIAN RINGKASAN ----
        activity_card = ctk.CTkFrame(wrap, corner_radius=CARD_RADIUS)
        activity_card.pack(fill="both", expand=True)

        activity_inner = ctk.CTkFrame(activity_card, fg_color="transparent")
        activity_inner.pack(fill="both", expand=True, padx=22, pady=20)

        # Header dengan judul + subtitle + link ke detail
        header_act = ctk.CTkFrame(activity_inner, fg_color="transparent")
        header_act.pack(fill="x", pady=(0, 4))

        title_left = ctk.CTkFrame(header_act, fg_color="transparent")
        title_left.pack(side="left")

        ctk.CTkLabel(
            title_left, text="🔮  Prediksi Absensi Hari Ini",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor='w',
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_left,
            text="Berdasarkan lewatan kamera sampai sekarang. "
                 "Hasil final di-finalize tengah malam.",
            font=ctk.CTkFont(size=10),
            text_color="gray",
            anchor='w',
        ).pack(anchor="w", pady=(2, 0))

        ctk.CTkButton(
            header_act, text="Lihat Riwayat  →",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="transparent", hover_color=("#e5e7eb", "#374151"),
            text_color=ACCENT_BLUE,
            corner_radius=8, height=30,
            command=self._on_view_full_log,
        ).pack(side="right")

        # spacer
        ctk.CTkFrame(activity_inner, fg_color="transparent", height=12).pack(fill="x")

        self._configure_tree_style()
        columns = ("nama", "jabatan", "check_in", "check_out", "status")
        self.tree = ttk.Treeview(
            activity_inner, columns=columns, show="headings",
            height=10, style="Home.Treeview",
        )
        self.tree.heading("nama", text="Nama")
        self.tree.heading("jabatan", text="Jabatan")
        self.tree.heading("check_in", text="Check-In")
        self.tree.heading("check_out", text="Check-Out")
        self.tree.heading("status", text="Prediksi Status")
        self.tree.column("nama", width=240, anchor="w")
        self.tree.column("jabatan", width=160, anchor="w")
        self.tree.column("check_in", width=100, anchor="center")
        self.tree.column("check_out", width=100, anchor="center")
        self.tree.column("status", width=200, anchor="center")
        self.tree.pack(fill="both", expand=True)

        self.tree.tag_configure("normal", foreground=ACCENT_GREEN)
        self.tree.tag_configure("terlambat", foreground=ACCENT_RED)
        self.tree.tag_configure("cepat", foreground=ACCENT_ORANGE)
        self.tree.tag_configure("belum_pulang", foreground="#eab308")  # kuning

    # ============================================================
    # DATA
    # ============================================================

    def refresh(self):
        # Catch-up: kalau tengah malam lewat sementara app jalan dan launchd
        # gak fire (mis. laptop sleep), resolve_pending akan handle in-process.
        # Idempotent + cheap (resolve_log skip tanggal yang sudah jalan).
        try:
            resolve_pending()
        except Exception as e:
            print(f"[home refresh] resolve_pending error: {e}")

        karyawan = get_all_karyawan()
        total_aktif = sum(1 for k in karyawan if k['status_aktif'])
        self.card_karyawan['value'].configure(text=str(total_aktif))

        log_stats = get_log_stats()
        if log_stats:
            self.card_today['value'].configure(text=str(log_stats['today']))

        harian_today = get_absensi_harian_stats('today')
        if harian_today:
            self.card_terlambat['value'].configure(text=str(harian_today['terlambat']))
            self.card_cepat['value'].configure(text=str(harian_today['pulang_cepat']))

        # Sync attendance button (daemon state bisa berubah dari luar app)
        self._update_attendance_button()

        for item in self.tree.get_children():
            self.tree.delete(item)

        predictions = predict_today_absensi()
        for r in predictions:
            ci = r['check_in_time'].strftime('%H:%M:%S') if r['check_in_time'] else '—'
            co = r['check_out_time'].strftime('%H:%M:%S') if r['check_out_time'] else '—'

            if r['belum_pulang']:
                if r['status_terlambat']:
                    status, tag = "⏰  Terlambat · 🟡 Belum Pulang", "belum_pulang"
                else:
                    status, tag = "🟡  Belum Pulang", "belum_pulang"
            elif r['status_terlambat'] and r['status_pulang_cepat']:
                status, tag = "⏰  Terlambat + Cepat", "terlambat"
            elif r['status_terlambat']:
                status, tag = "⏰  Terlambat", "terlambat"
            elif r['status_pulang_cepat']:
                status, tag = "🏃  Pulang Cepat", "cepat"
            else:
                status, tag = "✓  Normal", "normal"

            self.tree.insert("", "end", values=(
                r['nama'], r['jabatan'] or '-', ci, co, status,
            ), tags=(tag,))

    def on_show(self):
        self.refresh()

    def _on_toggle_attendance(self):
        """Tombol Mulai Absensi — toggle start/stop daemon."""
        if not self.app:
            return
        if self.app._is_daemon_running():
            self.app.stop_daemon()
        else:
            self.app.start_daemon()
        self._update_attendance_button()

    def _update_attendance_button(self):
        if not self.app:
            return
        if self.app._is_daemon_running():
            self.btn_attendance.configure(
                text="⏹   Stop Absensi",
                fg_color=ACCENT_RED, hover_color="#dc2626",
            )
        else:
            self.btn_attendance.configure(
                text="🎥   Mulai Absensi",
                fg_color=ACCENT_GREEN, hover_color="#0ea271",
            )

    def _on_view_full_log(self):
        if self.app:
            self.app.show_page('log')

    # ============================================================
    # WIDGETS
    # ============================================================

    def _create_stat_card(self, parent, col, title, icon, accent):
        card = ctk.CTkFrame(parent, corner_radius=CARD_RADIUS)
        card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 10, 10 if col < 3 else 0))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=18)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")

        ctk.CTkLabel(
            top, text=icon,
            font=ctk.CTkFont(size=20),
            text_color=accent,
        ).pack(side="left")

        ctk.CTkLabel(
            top, text=title,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="gray",
            anchor='w',
        ).pack(side="left", padx=(10, 0))

        value_lbl = ctk.CTkLabel(
            inner, text="—",
            font=ctk.CTkFont(size=28, weight="bold"),
            anchor='w',
        )
        value_lbl.pack(fill="x", pady=(10, 0))

        return {'card': card, 'value': value_lbl}

    def _configure_tree_style(self):
        style = ttk.Style()
        is_dark = ctk.get_appearance_mode() == "Dark"

        bg      = "#1f1f2e" if is_dark else "#ffffff"
        fg      = "#e5e7eb" if is_dark else "#111827"
        head_bg = "#2a2a3e" if is_dark else "#f3f4f6"
        head_fg = "#e5e7eb" if is_dark else "#374151"

        style.theme_use('default')
        style.configure(
            "Home.Treeview",
            background=bg, foreground=fg, fieldbackground=bg,
            rowheight=38, font=("Helvetica", 11), borderwidth=0,
        )
        style.configure(
            "Home.Treeview.Heading",
            background=head_bg, foreground=head_fg,
            font=("Helvetica", 10, "bold"),
            relief="flat", padding=(12, 14), borderwidth=0,
        )
        style.map(
            "Home.Treeview",
            background=[('selected', ACCENT_BLUE)],
            foreground=[('selected', '#ffffff')],
        )
