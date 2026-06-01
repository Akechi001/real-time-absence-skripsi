# src/ui/log_absensi.py - Page Log Absensi (CustomTkinter, 2 tab)

import csv
import os
import sys
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, filedialog

import customtkinter as ctk

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.database.operations import (
    get_log_absensi, get_karyawan_dropdown_list,
    get_absensi_harian, resolve_pending,
)


CARD_RADIUS = 14
ACCENT_BLUE = "#3b82f6"
ACCENT_GREEN = "#10b981"
ACCENT_RED = "#ef4444"
ACCENT_ORANGE = "#f59e0b"
ACCENT_PURPLE = "#8b5cf6"
ACCENT_GRAY = "#6b7280"


class LogAbsensiFrame(ctk.CTkFrame):
    def __init__(self, parent, app=None):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self.app = app

        # Tab Absensi Harian state
        self.h_filter_date = tk.StringVar(value='month')
        self.h_filter_karyawan = tk.StringVar(value='Semua Karyawan')
        self.h_filter_status = tk.StringVar(value='all')
        # Tab Raw Lewatan state
        self.l_filter_date = tk.StringVar(value='today')
        self.l_filter_karyawan = tk.StringVar(value='Semua Karyawan')
        self.l_filter_event = tk.StringVar(value='all')

        self.karyawan_list = []

        self._build_widgets()
        self._load_karyawan_dropdown()
        self._run_lazy_resolve()
        self._load_harian_data()
        self._load_lewatan_data()

    def on_show(self):
        # Selalu cek tanggal yang belum di-resolve setiap visit page.
        # Idempotent (resolve_log skip tanggal yang sudah jalan), jadi cheap.
        # Penting buat skenario "midnight passes while app open" — supaya
        # tanggal baru yang lewat dari today bisa auto-resolve.
        self._run_lazy_resolve()
        self._load_harian_data()
        self._load_lewatan_data()

    def refresh(self):
        """Auto-refresh hook (dipanggil DashboardApp tiap ~5 detik)."""
        self._run_lazy_resolve()
        self._load_harian_data()
        self._load_lewatan_data()

    # ============================================================
    # LAYOUT
    # ============================================================

    def _build_widgets(self):
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=36, pady=30)

        # ---- HEADER ----
        header = ctk.CTkFrame(wrap, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box, text="Log Absensi",
            font=ctk.CTkFont(size=26, weight="bold"),
            anchor='w',
        ).pack(anchor='w')

        ctk.CTkLabel(
            title_box,
            text="Riwayat absensi harian dan lewatan kamera.",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            anchor='w',
        ).pack(anchor='w', pady=(4, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")

        ctk.CTkButton(
            actions, text="🔄  Refresh",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="gray", hover_color="#6b7280",
            corner_radius=10, height=38,
            command=self._refresh_all,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions, text="📥  Export CSV",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=ACCENT_PURPLE, hover_color="#7c3aed",
            corner_radius=10, height=38,
            command=self._on_export_csv,
        ).pack(side="left")

        # ---- TABVIEW ----
        self.tabview = ctk.CTkTabview(
            wrap, corner_radius=CARD_RADIUS,
            segmented_button_selected_color=ACCENT_BLUE,
        )
        self.tabview.pack(fill="both", expand=True)

        self.tabview.add("Absensi Harian")
        self.tabview.add("Raw Lewatan")

        self._build_harian_tab(self.tabview.tab("Absensi Harian"))
        self._build_lewatan_tab(self.tabview.tab("Raw Lewatan"))

    # ============================================================
    # TAB ABSENSI HARIAN
    # ============================================================

    def _build_harian_tab(self, parent):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=4, pady=8)

        # Filter slim
        filter_card = ctk.CTkFrame(wrap, corner_radius=10, height=56)
        filter_card.pack(fill="x", pady=(0, 12))
        filter_card.pack_propagate(False)

        inner = ctk.CTkFrame(filter_card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14, pady=8)

        ctk.CTkLabel(
            inner, text="🔍",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        ).pack(side="left", padx=(2, 10))

        self._inline_combo(inner, self.h_filter_date,
                           ['today', 'week', 'month', 'all'],
                           self._load_harian_data, width=110)

        self.h_karyawan_combo = self._inline_combo(
            inner, self.h_filter_karyawan,
            ['Semua Karyawan'], self._load_harian_data, width=200,
        )

        self._inline_combo(inner, self.h_filter_status,
                           ['all', 'terlambat', 'pulang_cepat',
                            'terlambat_atau_cepat', 'normal', 'tidak_lengkap'],
                           self._load_harian_data, width=170)

        ctk.CTkButton(
            inner, text="↺",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="transparent", hover_color=("#e5e7eb", "#374151"),
            text_color="gray",
            corner_radius=8, height=38, width=38,
            command=self._on_reset_harian_filter,
        ).pack(side="right")

        # Table
        table_card = ctk.CTkFrame(wrap, corner_radius=CARD_RADIUS)
        table_card.pack(fill="both", expand=True)

        table_inner = ctk.CTkFrame(table_card, fg_color="transparent")
        table_inner.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = ttk.Scrollbar(table_inner)
        scrollbar.pack(side="right", fill="y")

        self._configure_tree_style("Harian.Treeview")
        cols = ("tanggal", "nip", "nama", "jabatan", "check_in", "check_out", "status", "keterangan")
        self.h_tree = ttk.Treeview(
            table_inner, columns=cols, show="headings",
            yscrollcommand=scrollbar.set, selectmode="browse",
            style="Harian.Treeview",
        )
        for c, h in zip(cols, ["Tanggal", "NIP", "Nama", "Jabatan",
                               "Check-In", "Check-Out", "Status", "Keterangan"]):
            self.h_tree.heading(c, text=h)
        widths = [100, 90, 180, 130, 90, 90, 130, 220]
        anchors = ["center", "center", "w", "w", "center", "center", "center", "w"]
        for c, w, a in zip(cols, widths, anchors):
            self.h_tree.column(c, width=w, anchor=a)
        self.h_tree.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.h_tree.yview)

        self.h_tree.tag_configure("row_even", background=self._row_even_bg)
        self.h_tree.tag_configure("row_odd", background=self._row_odd_bg)
        self.h_tree.tag_configure("normal", foreground=ACCENT_GREEN)
        self.h_tree.tag_configure("terlambat", foreground=ACCENT_RED)
        self.h_tree.tag_configure("cepat", foreground=ACCENT_ORANGE)
        self.h_tree.tag_configure("tidak_lengkap", foreground=ACCENT_GRAY)

        self.h_info_label = ctk.CTkLabel(
            wrap, text="", font=ctk.CTkFont(size=10), text_color="gray", anchor='w',
        )
        self.h_info_label.pack(fill="x", pady=(8, 0))

    def _load_harian_data(self):
        for item in self.h_tree.get_children():
            self.h_tree.delete(item)

        karyawan_id = self._parse_karyawan_id(self.h_filter_karyawan.get())
        rows = get_absensi_harian(
            filter_date=self.h_filter_date.get(),
            filter_karyawan_id=karyawan_id,
            filter_status=self.h_filter_status.get(),
            limit=500,
        )

        for i, r in enumerate(rows):
            ci = r['check_in_time'].strftime('%H:%M:%S') if r['check_in_time'] else '—'
            co = r['check_out_time'].strftime('%H:%M:%S') if r['check_out_time'] else '—'

            if r['check_in_time'] is None or r['check_out_time'] is None:
                status, status_tag = "⚠  Tidak Lengkap", "tidak_lengkap"
            elif r['status_terlambat'] and r['status_pulang_cepat']:
                status, status_tag = "⏰  Terlambat + Cepat", "terlambat"
            elif r['status_terlambat']:
                status, status_tag = "⏰  Terlambat", "terlambat"
            elif r['status_pulang_cepat']:
                status, status_tag = "🏃  Pulang Cepat", "cepat"
            else:
                status, status_tag = "✓  Normal", "normal"

            zebra = "row_even" if i % 2 == 0 else "row_odd"
            self.h_tree.insert("", "end",
                values=(r['tanggal'].strftime('%Y-%m-%d'),
                        r['nip'], r['nama'], r['jabatan'] or '-',
                        ci, co, status, r['keterangan']),
                tags=(zebra, status_tag))

        self.h_info_label.configure(
            text=f"Menampilkan {len(rows)} hari absensi (max 500)  ·  "
                 f"periode: {self.h_filter_date.get()}  ·  "
                 f"status: {self.h_filter_status.get()}"
        )

    def _on_reset_harian_filter(self):
        self.h_filter_date.set('month')
        self.h_filter_karyawan.set('Semua Karyawan')
        self.h_filter_status.set('all')
        self._load_harian_data()

    # ============================================================
    # TAB RAW LEWATAN
    # ============================================================

    def _build_lewatan_tab(self, parent):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=4, pady=8)

        ctk.CTkLabel(
            wrap,
            text="Setiap deteksi kamera = 1 baris lewatan. "
                 "Belum jadi keputusan absensi — lihat tab Absensi Harian.",
            font=ctk.CTkFont(size=10, slant="italic"),
            text_color="gray", anchor="w",
        ).pack(fill="x", pady=(0, 10))

        # Filter slim
        filter_card = ctk.CTkFrame(wrap, corner_radius=10, height=56)
        filter_card.pack(fill="x", pady=(0, 12))
        filter_card.pack_propagate(False)

        inner = ctk.CTkFrame(filter_card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14, pady=8)

        ctk.CTkLabel(
            inner, text="🔍",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        ).pack(side="left", padx=(2, 10))

        self._inline_combo(inner, self.l_filter_date,
                           ['today', 'week', 'month', 'all'],
                           self._load_lewatan_data, width=110)

        self.l_karyawan_combo = self._inline_combo(
            inner, self.l_filter_karyawan,
            ['Semua Karyawan'], self._load_lewatan_data, width=200,
        )

        self._inline_combo(inner, self.l_filter_event,
                           ['all', 'passage', 'check-in', 'check-out'],
                           self._load_lewatan_data, width=130)

        ctk.CTkButton(
            inner, text="↺",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="transparent", hover_color=("#e5e7eb", "#374151"),
            text_color="gray",
            corner_radius=8, height=38, width=38,
            command=self._on_reset_lewatan_filter,
        ).pack(side="right")

        # Table
        table_card = ctk.CTkFrame(wrap, corner_radius=CARD_RADIUS)
        table_card.pack(fill="both", expand=True)

        table_inner = ctk.CTkFrame(table_card, fg_color="transparent")
        table_inner.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = ttk.Scrollbar(table_inner)
        scrollbar.pack(side="right", fill="y")

        self._configure_tree_style("Lewatan.Treeview")
        cols = ("timestamp", "nip", "nama", "jabatan", "event", "confidence", "liveness")
        self.l_tree = ttk.Treeview(
            table_inner, columns=cols, show="headings",
            yscrollcommand=scrollbar.set, selectmode="browse",
            style="Lewatan.Treeview",
        )
        for c, h in zip(cols, ["Waktu", "NIP", "Nama", "Jabatan",
                               "Event", "Confidence", "Liveness"]):
            self.l_tree.heading(c, text=h)
        widths = [160, 90, 200, 140, 100, 100, 80]
        anchors = ["center", "center", "w", "w", "center", "center", "center"]
        for c, w, a in zip(cols, widths, anchors):
            self.l_tree.column(c, width=w, anchor=a)
        self.l_tree.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.l_tree.yview)

        self.l_tree.tag_configure("row_even", background=self._row_even_bg)
        self.l_tree.tag_configure("row_odd", background=self._row_odd_bg)
        self.l_tree.tag_configure("passage", foreground=ACCENT_BLUE)
        self.l_tree.tag_configure("checkin", foreground=ACCENT_GREEN)
        self.l_tree.tag_configure("checkout", foreground=ACCENT_ORANGE)

        self.l_info_label = ctk.CTkLabel(
            wrap, text="", font=ctk.CTkFont(size=10), text_color="gray", anchor='w',
        )
        self.l_info_label.pack(fill="x", pady=(8, 0))

    def _load_lewatan_data(self):
        for item in self.l_tree.get_children():
            self.l_tree.delete(item)

        karyawan_id = self._parse_karyawan_id(self.l_filter_karyawan.get())
        logs = get_log_absensi(
            filter_date=self.l_filter_date.get(),
            filter_karyawan_id=karyawan_id,
            filter_event=self.l_filter_event.get(),
            limit=500,
        )

        for i, log in enumerate(logs):
            evt = log['jenis_event']
            evt_tag = ("checkin" if evt == 'check-in'
                       else "checkout" if evt == 'check-out'
                       else "passage")
            zebra = "row_even" if i % 2 == 0 else "row_odd"

            self.l_tree.insert("", "end",
                values=(log['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                        log['nip'], log['nama'], log['jabatan'] or '-',
                        evt.upper(), f"{log['confidence_score']:.4f}",
                        "Live" if log['status_liveness'] else "Spoof"),
                tags=(zebra, evt_tag))

        self.l_info_label.configure(
            text=f"Menampilkan {len(logs)} lewatan (max 500)  ·  "
                 f"tanggal: {self.l_filter_date.get()}  ·  "
                 f"event: {self.l_filter_event.get()}"
        )

    def _on_reset_lewatan_filter(self):
        self.l_filter_date.set('today')
        self.l_filter_karyawan.set('Semua Karyawan')
        self.l_filter_event.set('all')
        self._load_lewatan_data()

    # ============================================================
    # SHARED
    # ============================================================

    def _run_lazy_resolve(self):
        try:
            result = resolve_pending()
            if result:
                total = sum(result.values())
                print(f"[lazy_resolve] {len(result)} tanggal di-resolve "
                      f"(total {total} karyawan)")
        except Exception as e:
            print(f"[lazy_resolve] error: {e}")

    def _load_karyawan_dropdown(self):
        self.karyawan_list = get_karyawan_dropdown_list()
        options = ['Semua Karyawan'] + [
            f"{k['nama']} (ID: {k['id']})" for k in self.karyawan_list
        ]
        self.h_karyawan_combo.configure(values=options)
        self.l_karyawan_combo.configure(values=options)

    def _parse_karyawan_id(self, selection):
        if selection == 'Semua Karyawan':
            return None
        try:
            return int(selection.split('ID: ')[1].rstrip(')'))
        except (IndexError, ValueError):
            return None

    def _refresh_all(self):
        # Refresh manual → ikut catch-up resolve_pending kalau ada tanggal lampau
        self._run_lazy_resolve()
        self._load_karyawan_dropdown()
        self._load_harian_data()
        self._load_lewatan_data()

    def _on_export_csv(self):
        if self.tabview.get() == "Absensi Harian":
            self._export_tree_to_csv(self.h_tree, "absensi_harian",
                                     ['Tanggal', 'NIP', 'Nama', 'Jabatan',
                                      'Check-In', 'Check-Out', 'Status', 'Keterangan'])
        else:
            self._export_tree_to_csv(self.l_tree, "log_lewatan",
                                     ['Timestamp', 'NIP', 'Nama', 'Jabatan',
                                      'Event', 'Confidence', 'Liveness'])

    def _export_tree_to_csv(self, tree, prefix, headers):
        items = tree.get_children()
        if not items:
            messagebox.showwarning("Tidak Ada Data", "Tidak ada data untuk di-export.")
            return

        default_filename = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile=default_filename,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not filepath:
            return

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for item in items:
                    writer.writerow(tree.item(item)['values'])
            messagebox.showinfo("Export Berhasil",
                f"Data berhasil diexport ke:\n{filepath}\n\nTotal: {len(items)} baris")
        except Exception as e:
            messagebox.showerror("Export Gagal", f"Gagal export CSV:\n{e}")

    # ============================================================
    # STYLE / WIDGETS
    # ============================================================

    def _inline_combo(self, parent, variable, values, on_change, width=140):
        """Combo box inline (tanpa label di atas) — versi slim filter bar"""
        combo = ctk.CTkComboBox(
            parent, variable=variable, values=values,
            width=width, height=38, corner_radius=8,
            font=ctk.CTkFont(size=11),
            dropdown_font=ctk.CTkFont(size=11),
            state="readonly",
            border_width=1,
            command=lambda _v: on_change(),
        )
        combo.pack(side="left", padx=(0, 8))
        return combo

    def _configure_tree_style(self, style_name):
        style = ttk.Style()
        is_dark = ctk.get_appearance_mode() == "Dark"

        bg          = "#1f1f2e" if is_dark else "#ffffff"
        row_even_bg = "#1f1f2e" if is_dark else "#ffffff"
        row_odd_bg  = "#252535" if is_dark else "#f9fafb"  # zebra stripe
        fg          = "#e5e7eb" if is_dark else "#111827"
        head_bg     = "#2a2a3e" if is_dark else "#f3f4f6"
        head_fg     = "#e5e7eb" if is_dark else "#374151"

        style.theme_use('default')
        style.configure(
            style_name,
            background=bg, foreground=fg, fieldbackground=bg,
            rowheight=40, font=("Helvetica", 11), borderwidth=0,
        )
        style.configure(
            f"{style_name}.Heading",
            background=head_bg, foreground=head_fg,
            font=("Helvetica", 10, "bold"),
            relief="flat", padding=(12, 14),
            borderwidth=0,
        )
        style.map(
            style_name,
            background=[('selected', ACCENT_BLUE)],
            foreground=[('selected', '#ffffff')],
        )
        # Zebra row colors — pakai store untuk dipakai saat tag_configure
        self._row_even_bg = row_even_bg
        self._row_odd_bg = row_odd_bg
