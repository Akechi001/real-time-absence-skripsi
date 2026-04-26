# src/ui/karyawan_list.py - Window Daftar Karyawan dengan CRUD

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.database.operations import get_all_karyawan, delete_karyawan, get_karyawan_by_id
from src.ui.theme import get_colors, get_button_colors, hover_color


class KaryawanListWindow:
    def __init__(self, parent):
        self.parent = parent
        self.colors = get_colors()

        self.window = tk.Toplevel(parent)
        self.window.title("Daftar Karyawan")
        self.window.geometry("950x600")
        self.window.resizable(True, True)
        self.window.configure(bg=self.colors['bg_primary'])

        self._center_window()
        self.window.transient(parent)
        self.window.grab_set()

        self._create_widgets()
        self._load_data()

    def _center_window(self):
        self.window.update_idletasks()
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_w = self.parent.winfo_width()
        parent_h = self.parent.winfo_height()

        win_w = self.window.winfo_width()
        win_h = self.window.winfo_height()

        x = parent_x + (parent_w // 2) - (win_w // 2)
        y = parent_y + (parent_h // 2) - (win_h // 2)
        self.window.geometry(f'+{x}+{y}')

    def _create_widgets(self):
        main_frame = tk.Frame(
            self.window,
            bg=self.colors['bg_primary'],
            padx=20,
            pady=20
        )
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ========== HEADER ==========
        header_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        header_frame.pack(fill=tk.X, pady=(0, 15))

        title_label = tk.Label(
            header_frame,
            text="📋 Daftar Karyawan Terdaftar",
            font=("Helvetica", 18, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_primary']
        )
        title_label.pack(side=tk.LEFT)

        btn_refresh = self._create_button(
            header_frame,
            text="🔄 Refresh",
            button_type='blue',
            command=self._load_data,
            small=True
        )
        btn_refresh.pack(side=tk.RIGHT)

        # ========== STATS ==========
        stats_frame = tk.Frame(
            main_frame,
            bg=self.colors['bg_secondary'],
            relief=tk.FLAT,
            bd=0,
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        stats_frame.pack(fill=tk.X, pady=(0, 15))

        self.stats_label = tk.Label(
            stats_frame,
            text="",
            font=("Helvetica", 11),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_secondary'],
            padx=15,
            pady=10,
            anchor="w"
        )
        self.stats_label.pack(fill=tk.X)

        # ========== LEGEND ==========
        legend_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        legend_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            legend_frame,
            text="Keterangan: ",
            font=("Helvetica", 9, "bold"),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_primary']
        ).pack(side=tk.LEFT)

        self._create_legend_item(legend_frame, self.colors['row_active'], "Aktif & Punya Foto")
        self._create_legend_item(legend_frame, self.colors['row_no_template'], "Belum Ada Foto")
        self._create_legend_item(legend_frame, self.colors['row_inactive'], "Nonaktif")

        # ========== TABLE ==========
        table_frame = tk.Frame(
            main_frame,
            bg=self.colors['bg_secondary'],
            relief=tk.FLAT,
            bd=1,
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        table_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(table_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        style = ttk.Style()
        style.theme_use('default')

        style.configure(
            "Custom.Treeview",
            background=self.colors['bg_secondary'],
            foreground=self.colors['text_primary'],
            fieldbackground=self.colors['bg_secondary'],
            rowheight=32,
            font=("Helvetica", 10),
            borderwidth=0
        )
        style.configure(
            "Custom.Treeview.Heading",
            background=self.colors['header_bg'],
            foreground=self.colors['header_fg'],
            font=("Helvetica", 10, "bold"),
            relief=tk.FLAT,
            padding=8
        )
        style.map(
            "Custom.Treeview",
            background=[('selected', self.colors['row_selected'])],
            foreground=[('selected', self.colors['text_light'])]
        )
        style.map(
            "Custom.Treeview.Heading",
            background=[('active', self.colors['header_bg'])]
        )

        columns = ("id", "nip", "nama", "jabatan", "jenis", "template", "status")
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            yscrollcommand=scrollbar.set,
            selectmode="browse",
            style="Custom.Treeview"
        )

        self.tree.heading("id", text="ID")
        self.tree.heading("nip", text="NIP")
        self.tree.heading("nama", text="Nama Karyawan")
        self.tree.heading("jabatan", text="Jabatan")
        self.tree.heading("jenis", text="Jenis")
        self.tree.heading("template", text="Foto?")
        self.tree.heading("status", text="Status")

        self.tree.column("id", width=50, anchor="center")
        self.tree.column("nip", width=110, anchor="center")
        self.tree.column("nama", width=220, anchor="w")
        self.tree.column("jabatan", width=140, anchor="w")
        self.tree.column("jenis", width=90, anchor="center")
        self.tree.column("template", width=70, anchor="center")
        self.tree.column("status", width=90, anchor="center")

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1, pady=1)
        scrollbar.config(command=self.tree.yview)

        self.tree.tag_configure(
            "active",
            background=self.colors['row_active'],
            foreground=self.colors['text_primary']
        )
        self.tree.tag_configure(
            "inactive",
            background=self.colors['row_inactive'],
            foreground=self.colors['text_secondary']
        )
        self.tree.tag_configure(
            "no_template",
            background=self.colors['row_no_template'],
            foreground=self.colors['text_primary']
        )

        # ========== ACTION BUTTONS ==========
        action_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        action_frame.pack(fill=tk.X, pady=(15, 0))

        btn_delete = self._create_button(
            action_frame,
            text="🗑️  Hapus Karyawan Terpilih",
            button_type='red',
            command=self._on_delete
        )
        btn_delete.pack(side=tk.LEFT, padx=(0, 10))

        btn_close = self._create_button(
            action_frame,
            text="Tutup",
            button_type='gray',
            command=self.window.destroy
        )
        btn_close.pack(side=tk.RIGHT)

    def _create_button(self, parent, text, button_type, command, small=False):
        btn_colors = get_button_colors(button_type)
        bg_color = btn_colors['bg']
        fg_color = btn_colors['fg']

        font_size = 10 if small else 11
        padx = 12 if small else 18
        pady = 8 if small else 12

        # macOS workaround: pakai Label dalam Frame sebagai tombol
        btn_container = tk.Frame(
            parent,
            bg=bg_color,
            highlightthickness=0,
            bd=0,
            cursor='hand2'
        )

        btn = tk.Label(
            btn_container,
            text=text,
            font=("Helvetica", font_size, "bold"),
            bg=bg_color,
            fg=fg_color,
            cursor='hand2',
            padx=padx,
            pady=pady
        )
        btn.pack(fill=tk.BOTH, expand=True)

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

    def _create_legend_item(self, parent, color, text):
        item_frame = tk.Frame(parent, bg=self.colors['bg_primary'])
        item_frame.pack(side=tk.LEFT, padx=(10, 0))

        color_box = tk.Frame(
            item_frame,
            bg=color,
            width=15,
            height=15,
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        color_box.pack(side=tk.LEFT, padx=(0, 5))
        color_box.pack_propagate(False)

        tk.Label(
            item_frame,
            text=text,
            font=("Helvetica", 9),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_primary']
        ).pack(side=tk.LEFT)

    def _load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        karyawan_list = get_all_karyawan()

        for k in karyawan_list:
            template_status = "✓" if k['has_template'] else "✗"
            status_text = "Aktif" if k['status_aktif'] else "Nonaktif"

            if not k['status_aktif']:
                tag = "inactive"
            elif not k['has_template']:
                tag = "no_template"
            else:
                tag = "active"

            self.tree.insert(
                "",
                tk.END,
                values=(
                    k['id_karyawan'],
                    k['nip'],
                    k['nama'],
                    k['jabatan'],
                    k['jenis_karyawan'],
                    template_status,
                    status_text
                ),
                tags=(tag,)
            )

        total = len(karyawan_list)
        active = sum(1 for k in karyawan_list if k['status_aktif'])
        with_template = sum(1 for k in karyawan_list if k['has_template'])

        self.stats_label.config(
            text=f"📊 Total: {total} karyawan   |   ✓ Aktif: {active}   |   📷 Punya Foto: {with_template}"
        )

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
        status = values[6]

        if status == "Nonaktif":
            messagebox.showinfo(
                "Sudah Nonaktif",
                f"Karyawan '{nama}' sudah dalam status nonaktif."
            )
            return

        confirm = messagebox.askyesno(
            "Konfirmasi Hapus",
            f"Yakin ingin menghapus karyawan berikut?\n\n"
            f"ID: {id_karyawan}\n"
            f"Nama: {nama}\n\n"
            f"Karyawan akan dinonaktifkan dan template foto dihapus.\n"
            f"Log absensi historis tetap dipertahankan.\n\n"
            f"Tindakan ini tidak dapat dibatalkan."
        )

        if not confirm:
            return

        success = delete_karyawan(id_karyawan)

        if success:
            messagebox.showinfo(
                "Berhasil",
                f"Karyawan '{nama}' berhasil dinonaktifkan."
            )
            self._load_data()
        else:
            messagebox.showerror(
                "Gagal",
                f"Gagal menghapus karyawan '{nama}'.\n"
                f"Cek konsol untuk detail error."
            )

def is_macos():
    """Check apakah running di macOS"""
    return platform.system() == "Darwin"

def open_karyawan_list(parent):
    KaryawanListWindow(parent)