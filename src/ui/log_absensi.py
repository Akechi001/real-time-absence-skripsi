# src/ui/log_absensi.py - Window Log Absensi dengan Filter

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.database.operations import get_log_absensi, get_log_stats, get_karyawan_dropdown_list
from src.ui.theme import get_colors, get_button_colors, hover_color


class LogAbsensiWindow:
    def __init__(self, parent):
        self.parent = parent
        self.colors = get_colors()

        self.window = tk.Toplevel(parent)
        self.window.title("Log Absensi")
        self.window.geometry("1100x700")
        self.window.resizable(True, True)
        self.window.minsize(900, 600)
        self.window.configure(bg=self.colors['bg_primary'])

        self._center_window()
        self.window.transient(parent)
        self.window.grab_set()

        self.filter_date = tk.StringVar(value='today')
        self.filter_karyawan = tk.StringVar(value='Semua Karyawan')
        self.filter_event = tk.StringVar(value='all')

        self.karyawan_list = []

        self._create_widgets()
        self._load_karyawan_dropdown()
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
            text="Log Absensi",
            font=("Helvetica", 18, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_primary']
        )
        title_label.pack(side=tk.LEFT)

        right_btn_frame = tk.Frame(header_frame, bg=self.colors['bg_primary'])
        right_btn_frame.pack(side=tk.RIGHT)

        btn_export = self._create_button(
            right_btn_frame,
            text="Export CSV",
            button_type='purple',
            command=self._on_export_csv,
            small=True
        )
        btn_export.pack(side=tk.LEFT, padx=(0, 5))

        btn_refresh = self._create_button(
            right_btn_frame,
            text="Refresh",
            button_type='blue',
            command=self._load_data,
            small=True
        )
        btn_refresh.pack(side=tk.LEFT)

        # ========== STATS CARDS ==========
        stats_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        stats_frame.pack(fill=tk.X, pady=(0, 15))

        self.stats_total_label = self._create_stat_card(stats_frame, "Total Log", "0", self.colors['btn_blue'])
        self.stats_today_label = self._create_stat_card(stats_frame, "Hari Ini", "0", self.colors['btn_green'])
        self.stats_checkin_label = self._create_stat_card(stats_frame, "Check-In", "0", self.colors['btn_orange'])
        self.stats_checkout_label = self._create_stat_card(stats_frame, "Check-Out", "0", self.colors['btn_purple'])

        # ========== FILTER BAR ==========
        filter_frame = tk.Frame(
            main_frame,
            bg=self.colors['bg_secondary'],
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        filter_frame.pack(fill=tk.X, pady=(0, 15))

        filter_inner = tk.Frame(
            filter_frame,
            bg=self.colors['bg_secondary'],
            padx=15,
            pady=12
        )
        filter_inner.pack(fill=tk.X)

        tk.Label(
            filter_inner,
            text="Filter:",
            font=("Helvetica", 10, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_secondary']
        ).pack(side=tk.LEFT, padx=(0, 15))

        tk.Label(
            filter_inner,
            text="Tanggal:",
            font=("Helvetica", 10),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_secondary']
        ).pack(side=tk.LEFT, padx=(0, 5))

        date_combo = ttk.Combobox(
            filter_inner,
            textvariable=self.filter_date,
            values=['today', 'week', 'month', 'all'],
            state='readonly',
            width=10,
            font=("Helvetica", 10)
        )
        date_combo.pack(side=tk.LEFT, padx=(0, 15))
        date_combo.bind('<<ComboboxSelected>>', lambda e: self._load_data())

        tk.Label(
            filter_inner,
            text="Karyawan:",
            font=("Helvetica", 10),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_secondary']
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.karyawan_combo = ttk.Combobox(
            filter_inner,
            textvariable=self.filter_karyawan,
            state='readonly',
            width=25,
            font=("Helvetica", 10)
        )
        self.karyawan_combo.pack(side=tk.LEFT, padx=(0, 15))
        self.karyawan_combo.bind('<<ComboboxSelected>>', lambda e: self._load_data())

        tk.Label(
            filter_inner,
            text="Event:",
            font=("Helvetica", 10),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_secondary']
        ).pack(side=tk.LEFT, padx=(0, 5))

        event_combo = ttk.Combobox(
            filter_inner,
            textvariable=self.filter_event,
            values=['all', 'check-in', 'check-out'],
            state='readonly',
            width=12,
            font=("Helvetica", 10)
        )
        event_combo.pack(side=tk.LEFT, padx=(0, 15))
        event_combo.bind('<<ComboboxSelected>>', lambda e: self._load_data())

        btn_reset = self._create_button(
            filter_inner,
            text="Reset",
            button_type='gray',
            command=self._on_reset_filter,
            small=True
        )
        btn_reset.pack(side=tk.LEFT)

        # ========== TABLE ==========
        table_frame = tk.Frame(
            main_frame,
            bg=self.colors['bg_secondary'],
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        table_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(table_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        style = ttk.Style()
        style.theme_use('default')

        style.configure(
            "Log.Treeview",
            background=self.colors['bg_secondary'],
            foreground=self.colors['text_primary'],
            fieldbackground=self.colors['bg_secondary'],
            rowheight=30,
            font=("Helvetica", 10),
            borderwidth=0
        )
        style.configure(
            "Log.Treeview.Heading",
            background=self.colors['header_bg'],
            foreground=self.colors['header_fg'],
            font=("Helvetica", 10, "bold"),
            relief=tk.FLAT,
            padding=8
        )
        style.map(
            "Log.Treeview",
            background=[('selected', self.colors['row_selected'])],
            foreground=[('selected', self.colors['text_light'])]
        )
        style.map(
            "Log.Treeview.Heading",
            background=[('active', self.colors['header_bg'])]
        )

        columns = ("timestamp", "nip", "nama", "jabatan", "event", "confidence", "liveness")
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            yscrollcommand=scrollbar.set,
            selectmode="browse",
            style="Log.Treeview"
        )

        self.tree.heading("timestamp", text="Waktu")
        self.tree.heading("nip", text="NIP")
        self.tree.heading("nama", text="Nama")
        self.tree.heading("jabatan", text="Jabatan")
        self.tree.heading("event", text="Event")
        self.tree.heading("confidence", text="Confidence")
        self.tree.heading("liveness", text="Liveness")

        self.tree.column("timestamp", width=160, anchor="center")
        self.tree.column("nip", width=80, anchor="center")
        self.tree.column("nama", width=200, anchor="w")
        self.tree.column("jabatan", width=140, anchor="w")
        self.tree.column("event", width=100, anchor="center")
        self.tree.column("confidence", width=100, anchor="center")
        self.tree.column("liveness", width=80, anchor="center")

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1, pady=1)
        scrollbar.config(command=self.tree.yview)

        self.tree.tag_configure(
            "checkin",
            background=self.colors['bg_secondary'],
            foreground=self.colors['btn_green']
        )
        self.tree.tag_configure(
            "checkout",
            background=self.colors['bg_secondary'],
            foreground=self.colors['btn_orange']
        )

        # ========== INFO BAR ==========
        self.info_label = tk.Label(
            main_frame,
            text="",
            font=("Helvetica", 9),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_primary']
        )
        self.info_label.pack(fill=tk.X, pady=(10, 0))

        # ========== CLOSE BUTTON ==========
        close_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        close_frame.pack(fill=tk.X, pady=(10, 0))

        btn_close = self._create_button(
            close_frame,
            text="Tutup",
            button_type='gray',
            command=self.window.destroy
        )
        btn_close.pack(side=tk.RIGHT)

    def _create_stat_card(self, parent, title, value, color):
        card = tk.Frame(
            parent,
            bg=self.colors['bg_secondary'],
            highlightbackground=color,
            highlightthickness=2
        )
        card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        title_lbl = tk.Label(
            card,
            text=title,
            font=("Helvetica", 9, "bold"),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_secondary'],
            pady=8
        )
        title_lbl.pack()

        value_lbl = tk.Label(
            card,
            text=value,
            font=("Helvetica", 18, "bold"),
            fg=color,
            bg=self.colors['bg_secondary'],
            pady=5
        )
        value_lbl.pack(pady=(0, 8))

        return value_lbl

    def _create_button(self, parent, text, button_type, command, small=False):
        btn_colors = get_button_colors(button_type)
        bg_color = btn_colors['bg']
        fg_color = btn_colors['fg']

        font_size = 10 if small else 11
        padx = 12 if small else 18
        pady = 6 if small else 10

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

    def _load_karyawan_dropdown(self):
        self.karyawan_list = get_karyawan_dropdown_list()

        options = ['Semua Karyawan']
        for k in self.karyawan_list:
            options.append(f"{k['nama']} (ID: {k['id']})")

        self.karyawan_combo['values'] = options

    def _get_filter_karyawan_id(self):
        selection = self.filter_karyawan.get()
        if selection == 'Semua Karyawan':
            return None

        try:
            id_part = selection.split('ID: ')[1].rstrip(')')
            return int(id_part)
        except (IndexError, ValueError):
            return None

    def _load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        stats = get_log_stats()
        if stats:
            self.stats_total_label.config(text=str(stats['total']))
            self.stats_today_label.config(text=str(stats['today']))
            self.stats_checkin_label.config(text=str(stats['checkin']))
            self.stats_checkout_label.config(text=str(stats['checkout']))

        karyawan_id = self._get_filter_karyawan_id()
        logs = get_log_absensi(
            filter_date=self.filter_date.get(),
            filter_karyawan_id=karyawan_id,
            filter_event=self.filter_event.get(),
            limit=500
        )

        for log in logs:
            timestamp_str = log['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            confidence_str = f"{log['confidence_score']:.4f}"
            liveness_str = "Live" if log['status_liveness'] else "Spoof"
            event_label = log['jenis_event'].upper()

            tag = "checkin" if log['jenis_event'] == 'check-in' else "checkout"

            self.tree.insert(
                "",
                tk.END,
                values=(
                    timestamp_str,
                    log['nip'],
                    log['nama'],
                    log['jabatan'] or '-',
                    event_label,
                    confidence_str,
                    liveness_str
                ),
                tags=(tag,)
            )

        self.info_label.config(
            text=f"Menampilkan {len(logs)} log (max 500). "
                 f"Filter: tanggal={self.filter_date.get()}, "
                 f"event={self.filter_event.get()}"
        )

    def _on_reset_filter(self):
        self.filter_date.set('today')
        self.filter_karyawan.set('Semua Karyawan')
        self.filter_event.set('all')
        self._load_data()

    def _on_export_csv(self):
        items = self.tree.get_children()
        if not items:
            messagebox.showwarning(
                "Tidak Ada Data",
                "Tidak ada log untuk di-export.\n"
                "Coba ubah filter terlebih dahulu."
            )
            return

        default_filename = f"log_absensi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=default_filename,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not filepath:
            return

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                writer.writerow([
                    'Timestamp', 'NIP', 'Nama', 'Jabatan',
                    'Event', 'Confidence Score', 'Status Liveness'
                ])

                for item in items:
                    values = self.tree.item(item)['values']
                    writer.writerow(values)

            messagebox.showinfo(
                "Export Berhasil",
                f"Log berhasil diexport ke:\n{filepath}\n\n"
                f"Total: {len(items)} baris"
            )
        except Exception as e:
            messagebox.showerror(
                "Export Gagal",
                f"Gagal export CSV:\n{e}"
            )


def open_log_absensi(parent):
    LogAbsensiWindow(parent)