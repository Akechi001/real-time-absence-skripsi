# src/ui/karyawan_list.py - Page Karyawan (CustomTkinter)

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

import customtkinter as ctk

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.database.operations import get_all_karyawan, delete_karyawan


CARD_RADIUS = 14
ACCENT_RED    = "#ef4444"
ACCENT_GREEN  = "#10b981"
ACCENT_BLUE   = "#3b82f6"
ACCENT_ORANGE = "#f59e0b"
ACCENT_GRAY   = "#6b7280"


class KaryawanListFrame(ctk.CTkFrame):
    def __init__(self, parent, app=None):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self.app = app
        self._build_widgets()

    def _build_widgets(self):
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=36, pady=30)

        # ---- HEADER ----
        header = ctk.CTkFrame(wrap, fg_color="transparent")
        header.pack(fill="x", pady=(0, 18))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box, text="Karyawan",
            font=ctk.CTkFont(size=26, weight="bold"),
            anchor='w',
        ).pack(anchor='w')

        ctk.CTkLabel(
            title_box,
            text="Kelola data karyawan internal & template wajah.",
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
            command=self._load_data,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            actions, text="➕  Tambah Karyawan",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ACCENT_GREEN, hover_color="#0ea271",
            corner_radius=12, height=42,
            command=self._on_add_karyawan,
        ).pack(side="left")

        # ---- STATS LABEL ----
        self.stats_label = ctk.CTkLabel(
            wrap, text="",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor='w',
        )
        self.stats_label.pack(fill="x", pady=(0, 10))

        # ---- LEGEND ----
        legend = ctk.CTkFrame(wrap, fg_color="transparent")
        legend.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(
            legend, text="Keterangan:",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="gray",
        ).pack(side="left")

        self._legend_item(legend, ACCENT_GREEN, "Aktif")
        self._legend_item(legend, ACCENT_RED,   "Nonaktif")

        # ---- TABLE CARD ----
        table_card = ctk.CTkFrame(wrap, corner_radius=CARD_RADIUS)
        table_card.pack(fill="both", expand=True)

        table_inner = ctk.CTkFrame(table_card, fg_color="transparent")
        table_inner.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = ttk.Scrollbar(table_inner)
        scrollbar.pack(side="right", fill="y")

        self._configure_tree_style()

        columns = ("id", "nip", "nama", "jabatan", "status")
        self.tree = ttk.Treeview(
            table_inner, columns=columns, show="headings",
            yscrollcommand=scrollbar.set, selectmode="browse",
            style="Karyawan.Treeview",
        )
        self.tree.heading("id", text="ID")
        self.tree.heading("nip", text="NIP")
        self.tree.heading("nama", text="Nama Karyawan")
        self.tree.heading("jabatan", text="Jabatan")
        self.tree.heading("status", text="Status")

        self.tree.column("id", width=60, anchor="center")
        self.tree.column("nip", width=140, anchor="center")
        self.tree.column("nama", width=300, anchor="w")
        self.tree.column("jabatan", width=200, anchor="w")
        self.tree.column("status", width=120, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.tree.yview)

        # Zebra row backgrounds + status foreground (warna sesuai legend)
        self.tree.tag_configure("row_even", background=self._row_even_bg)
        self.tree.tag_configure("row_odd",  background=self._row_odd_bg)
        self.tree.tag_configure("active",   foreground=ACCENT_GREEN)
        self.tree.tag_configure("inactive", foreground=ACCENT_RED)

        # ---- ACTION FOOTER ----
        footer = ctk.CTkFrame(wrap, fg_color="transparent")
        footer.pack(fill="x", pady=(16, 0))

        ctk.CTkButton(
            footer, text="🗑️  Hapus Karyawan Terpilih",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=ACCENT_RED, hover_color="#dc2626",
            corner_radius=10, height=40,
            command=self._on_delete,
        ).pack(side="left")

        self._load_data()

    def on_show(self):
        self._load_data()

    def refresh(self):
        """Auto-refresh hook — reload tabel tapi pertahankan baris yang user
        sedang pilih (kalau ada), supaya tombol Hapus tidak kehilangan target.
        """
        selected_id = None
        sel = self.tree.selection()
        if sel:
            vals = self.tree.item(sel[0]).get('values')
            if vals:
                selected_id = vals[0]

        self._load_data()

        if selected_id is not None:
            for item in self.tree.get_children():
                vals = self.tree.item(item).get('values')
                if vals and vals[0] == selected_id:
                    self.tree.selection_set(item)
                    break

    # ============================================================
    # DATA
    # ============================================================

    def _load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        karyawan_list = get_all_karyawan()

        for i, k in enumerate(karyawan_list):
            if k['status_aktif']:
                status_badge = "●  Aktif"
                status_tag = "active"
            else:
                status_badge = "●  Nonaktif"
                status_tag = "inactive"

            zebra = "row_even" if i % 2 == 0 else "row_odd"

            self.tree.insert(
                "", "end",
                values=(k['id_karyawan'], k['nip'], k['nama'],
                        k['jabatan'], status_badge),
                tags=(zebra, status_tag),
            )

        total = len(karyawan_list)
        active = sum(1 for k in karyawan_list if k['status_aktif'])

        self.stats_label.configure(
            text=f"📊 Total: {total} karyawan   ·   "
                 f"✓ Aktif: {active}   ·   "
                 f"✗ Nonaktif: {total - active}"
        )

    # ============================================================
    # ACTIONS
    # ============================================================

    def _on_add_karyawan(self):
        from src.ui.enrollment_window import open_enrollment_window
        open_enrollment_window(self.winfo_toplevel())

    def _on_delete(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning(
                "Tidak Ada Pilihan",
                "Silakan pilih karyawan yang ingin dihapus terlebih dahulu."
            )
            return

        item = self.tree.item(selected[0])
        values = item['values']
        id_karyawan = values[0]
        nama = values[2]
        status = values[4]

        if "Nonaktif" in str(status):
            messagebox.showinfo(
                "Sudah Nonaktif",
                f"Karyawan '{nama}' sudah nonaktif."
            )
            return

        confirm = messagebox.askyesno(
            "Konfirmasi Hapus",
            f"Yakin hapus karyawan berikut?\n\n"
            f"ID: {id_karyawan}\n"
            f"Nama: {nama}\n\n"
            f"Karyawan akan dinonaktifkan dan template foto dihapus.\n"
            f"Log absensi historis tetap dipertahankan."
        )
        if not confirm:
            return

        if delete_karyawan(id_karyawan):
            messagebox.showinfo("Berhasil", f"Karyawan '{nama}' dinonaktifkan.")
            self._load_data()
        else:
            messagebox.showerror("Gagal", f"Gagal menghapus '{nama}'.")

    # ============================================================
    # STYLE / WIDGETS
    # ============================================================

    def _legend_item(self, parent, color, text):
        item = ctk.CTkFrame(parent, fg_color="transparent")
        item.pack(side="left", padx=(14, 0))

        dot = ctk.CTkFrame(item, width=12, height=12, corner_radius=6, fg_color=color)
        dot.pack(side="left", padx=(0, 8))
        dot.pack_propagate(False)

        ctk.CTkLabel(
            item, text=text,
            font=ctk.CTkFont(size=11),
            text_color=color,
        ).pack(side="left")

    def _configure_tree_style(self):
        style = ttk.Style()
        is_dark = ctk.get_appearance_mode() == "Dark"

        bg          = "#1f1f2e" if is_dark else "#ffffff"
        row_even_bg = "#1f1f2e" if is_dark else "#ffffff"
        row_odd_bg  = "#252535" if is_dark else "#f9fafb"
        fg          = "#e5e7eb" if is_dark else "#111827"
        head_bg     = "#2a2a3e" if is_dark else "#f3f4f6"
        head_fg     = "#e5e7eb" if is_dark else "#374151"

        style.theme_use('default')
        style.configure(
            "Karyawan.Treeview",
            background=bg, foreground=fg, fieldbackground=bg,
            rowheight=40, font=("Helvetica", 11), borderwidth=0,
        )
        style.configure(
            "Karyawan.Treeview.Heading",
            background=head_bg, foreground=head_fg,
            font=("Helvetica", 10, "bold"),
            relief="flat", padding=(12, 14), borderwidth=0,
        )
        style.map(
            "Karyawan.Treeview",
            background=[('selected', ACCENT_BLUE)],
            foreground=[('selected', '#ffffff')],
        )
        self._row_even_bg = row_even_bg
        self._row_odd_bg = row_odd_bg
