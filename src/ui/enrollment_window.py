# src/ui/enrollment_window.py - Window Enrollment Karyawan Baru

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.ui.theme import get_colors, get_button_colors, hover_color


class EnrollmentWindow:
    def __init__(self, parent):
        self.parent = parent
        self.colors = get_colors()

        self.window = tk.Toplevel(parent)
        self.window.title("Tambah Karyawan Baru")
        self.window.geometry("900x900")
        self.window.resizable(True, True)
        self.window.configure(bg=self.colors['bg_primary'])

        self._center_window()
        self.window.transient(parent)
        self.window.grab_set()

        # Form variables
        self.nip_var = tk.StringVar()
        self.nama_var = tk.StringVar()
        self.jabatan_var = tk.StringVar()
        self.jenis_var = tk.StringVar(value="internal")

        self._create_widgets()

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
            padx=40,
            pady=30
        )
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ========== HEADER ==========
        header_label = tk.Label(
            main_frame,
            text="➕ Tambah Karyawan Baru",
            font=("Helvetica", 18, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_primary']
        )
        header_label.pack(pady=(0, 5))

        subtitle_label = tk.Label(
            main_frame,
            text="Lengkapi data karyawan, lalu lanjut ke pengambilan foto",
            font=("Helvetica", 10),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_primary']
        )
        subtitle_label.pack(pady=(0, 25))

        # ========== FORM CARD ==========
        form_card = tk.Frame(
            main_frame,
            bg=self.colors['bg_secondary'],
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        form_card.pack(fill=tk.X, pady=(0, 20))

        form_inner = tk.Frame(
            form_card,
            bg=self.colors['bg_secondary'],
            padx=30,
            pady=25
        )
        form_inner.pack(fill=tk.X)

        self._create_field(
            form_inner,
            label="NIP / ID Karyawan",
            variable=self.nip_var,
            placeholder="Contoh: 12345"
        )

        self._create_field(
            form_inner,
            label="Nama Lengkap",
            variable=self.nama_var,
            placeholder="Contoh: Enrico Kevin Ariantho"
        )

        self._create_field(
            form_inner,
            label="Jabatan",
            variable=self.jabatan_var,
            placeholder="Contoh: Dosen / Staff IT / Cleaning Service"
        )

        self._create_jenis_field(form_inner)

        # ========== INFO BOX ==========
        info_frame = tk.Frame(
            main_frame,
            bg=self.colors['bg_secondary'],
            highlightbackground=self.colors['btn_blue'],
            highlightthickness=1
        )
        info_frame.pack(fill=tk.X, pady=(0, 20))

        info_label = tk.Label(
            info_frame,
            text="💡 Setelah klik 'Lanjut', sistem akan membuka kamera untuk\n"
                 "    pengambilan 5 foto wajah dengan pose berbeda.",
            font=("Helvetica", 10),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_secondary'],
            justify=tk.LEFT,
            padx=15,
            pady=12
        )
        info_label.pack(fill=tk.X)

        # ========== BUTTONS ==========
        button_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        button_frame.pack(fill=tk.X, pady=(10, 0))

        btn_cancel = self._create_button(
            button_frame,
            text="Batal",
            button_type='gray',
            command=self.window.destroy
        )
        btn_cancel.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        btn_next = self._create_button(
            button_frame,
            text="Lanjut ke Foto  →",
            button_type='green',
            command=self._on_next
        )
        btn_next.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

    def _create_field(self, parent, label, variable, placeholder=""):
        """Helper untuk membuat field input"""
        lbl = tk.Label(
            parent,
            text=label,
            font=("Helvetica", 11, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_secondary'],
            anchor="w"
        )
        lbl.pack(fill=tk.X, pady=(0, 5))

        entry = tk.Entry(
            parent,
            textvariable=variable,
            font=("Helvetica", 11),
            bg=self.colors['bg_input'],
            fg=self.colors['text_primary'],
            insertbackground=self.colors['text_primary'],
            relief=tk.FLAT,
            bd=0,
            highlightbackground=self.colors['border'],
            highlightcolor=self.colors['btn_blue'],
            highlightthickness=1
        )
        entry.pack(fill=tk.X, pady=(0, 15), ipady=8, ipadx=10)

        if placeholder:
            entry.insert(0, placeholder)
            entry.config(fg=self.colors['text_secondary'])

            def on_focus_in(e):
                if entry.get() == placeholder:
                    entry.delete(0, tk.END)
                    entry.config(fg=self.colors['text_primary'])

            def on_focus_out(e):
                if not entry.get():
                    entry.insert(0, placeholder)
                    entry.config(fg=self.colors['text_secondary'])

            entry.bind("<FocusIn>", on_focus_in)
            entry.bind("<FocusOut>", on_focus_out)

        return entry

    def _create_jenis_field(self, parent):
        """Field untuk jenis karyawan (radio buttons)"""
        lbl = tk.Label(
            parent,
            text="Jenis Karyawan",
            font=("Helvetica", 11, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_secondary'],
            anchor="w"
        )
        lbl.pack(fill=tk.X, pady=(0, 8))

        radio_frame = tk.Frame(parent, bg=self.colors['bg_secondary'])
        radio_frame.pack(fill=tk.X, pady=(0, 5))

        rb_style = {
            'font': ("Helvetica", 11),
            'fg': self.colors['text_primary'],
            'bg': self.colors['bg_secondary'],
            'activebackground': self.colors['bg_secondary'],
            'activeforeground': self.colors['text_primary'],
            'selectcolor': self.colors['bg_input'],
            'cursor': 'hand2',
            'highlightthickness': 0
        }

        rb_internal = tk.Radiobutton(
            radio_frame,
            text="Internal (Dosen/Staff Universitas)",
            variable=self.jenis_var,
            value="internal",
            **rb_style
        )
        rb_internal.pack(anchor="w", pady=2)

        rb_vendor = tk.Radiobutton(
            radio_frame,
            text="Vendor (Cleaning Service / Security / Outsourcing)",
            variable=self.jenis_var,
            value="vendor",
            **rb_style
        )
        rb_vendor.pack(anchor="w", pady=2)

    def _create_button(self, parent, text, button_type, command):
        """Helper untuk membuat tombol (macOS compatible)"""
        btn_colors = get_button_colors(button_type)
        bg_color = btn_colors['bg']
        fg_color = btn_colors['fg']

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
            font=("Helvetica", 12, "bold"),
            bg=bg_color,
            fg=fg_color,
            cursor='hand2',
            padx=20,
            pady=12
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

    def _validate_form(self):
        """Validasi form sebelum lanjut ke foto"""
        nip = self.nip_var.get().strip()
        nama = self.nama_var.get().strip()
        jabatan = self.jabatan_var.get().strip()

        # Hapus placeholder text kalau masih ada
        placeholders = {
            "Contoh: 12345",
            "Contoh: Enrico Kevin Ariantho",
            "Contoh: Dosen / Staff IT / Cleaning Service"
        }

        if nip in placeholders:
            nip = ""
        if nama in placeholders:
            nama = ""
        if jabatan in placeholders:
            jabatan = ""

        # Validasi
        errors = []
        if not nip:
            errors.append("• NIP / ID Karyawan harus diisi")
        elif len(nip) > 50:
            errors.append("• NIP terlalu panjang (max 50 karakter)")

        if not nama:
            errors.append("• Nama Lengkap harus diisi")
        elif len(nama) < 2:
            errors.append("• Nama terlalu pendek (min 2 karakter)")
        elif len(nama) > 100:
            errors.append("• Nama terlalu panjang (max 100 karakter)")

        if not jabatan:
            errors.append("• Jabatan harus diisi")
        elif len(jabatan) > 100:
            errors.append("• Jabatan terlalu panjang (max 100 karakter)")

        if errors:
            messagebox.showerror(
                "Form Tidak Valid",
                "Mohon perbaiki data berikut:\n\n" + "\n".join(errors)
            )
            return None

        return {
            'nip': nip,
            'nama': nama,
            'jabatan': jabatan,
            'jenis': self.jenis_var.get()
        }

    def _on_next(self):
        """Handle tombol 'Lanjut'"""
        data = self._validate_form()
        if data is None:
            return

        # Konfirmasi data
        confirm = messagebox.askyesno(
            "Konfirmasi Data",
            f"Pastikan data berikut sudah benar:\n\n"
            f"NIP: {data['nip']}\n"
            f"Nama: {data['nama']}\n"
            f"Jabatan: {data['jabatan']}\n"
            f"Jenis: {data['jenis'].title()}\n\n"
            f"Lanjut ke pengambilan foto?"
        )

        if not confirm:
            return

        # Tutup form window
        self.window.destroy()

        # Buka camera enrollment window
        from src.ui.camera_enrollment import open_camera_enrollment
        open_camera_enrollment(self.parent, data)


def open_enrollment_window(parent):
    """Helper function untuk dipanggil dari main window"""
    EnrollmentWindow(parent)