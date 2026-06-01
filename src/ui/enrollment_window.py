# src/ui/enrollment_window.py - Form data karyawan (CustomTkinter modal)

import os
import sys
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


CARD_RADIUS = 14
ACCENT_GREEN = "#10b981"
ACCENT_GRAY = "#6b7280"

# Maks panjang sesuai schema DB
NIP_MAX_LEN = 50
NAMA_MAX_LEN = 100

# Char set yang valid untuk nama orang (Unicode-aware untuk nama Indonesia)
_NAMA_ALLOWED_PUNCT = " .'-"


def _validate_nip(proposed):
    """Real-time: NIP cuma digit, max NIP_MAX_LEN."""
    if proposed == "":
        return True
    if len(proposed) > NIP_MAX_LEN:
        return False
    return proposed.isdigit()


def _validate_nama(proposed):
    """Real-time: huruf + spasi + . ' -, max NAMA_MAX_LEN."""
    if proposed == "":
        return True
    if len(proposed) > NAMA_MAX_LEN:
        return False
    return all(c.isalpha() or c in _NAMA_ALLOWED_PUNCT for c in proposed)


class EnrollmentWindow:
    def __init__(self, parent):
        self.parent = parent

        self.window = ctk.CTkToplevel(parent)
        self.window.title("Tambah Karyawan Baru")
        self.window.geometry("680x620")
        self.window.resizable(True, True)
        self.window.minsize(560, 560)

        self._center_window()
        self.window.transient(parent)
        self.window.after(50, lambda: self.window.grab_set())  # grab_set after Toplevel ready

        self.nip_var = tk.StringVar()
        self.nama_var = tk.StringVar()
        self.jabatan_var = tk.StringVar(value="Dosen")
        self.jenis_var = tk.StringVar(value="internal")

        self._build_widgets()

    def _center_window(self):
        self.window.update_idletasks()
        try:
            px = self.parent.winfo_x()
            py = self.parent.winfo_y()
            pw = self.parent.winfo_width()
            ph = self.parent.winfo_height()
            w = self.window.winfo_width()
            h = self.window.winfo_height()
            x = px + (pw // 2) - (w // 2)
            y = py + (ph // 2) - (h // 2)
            self.window.geometry(f'+{x}+{y}')
        except Exception:
            pass

    def _build_widgets(self):
        main = ctk.CTkFrame(self.window, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=36, pady=28)

        # ---- HEADER ----
        ctk.CTkLabel(
            main, text="➕  Tambah Karyawan Baru",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            main,
            text="Lengkapi data karyawan, lalu upload 3 foto studio dari HRD/HCM",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        ).pack(anchor="w", pady=(4, 24))

        # ---- FORM CARD ----
        form_card = ctk.CTkFrame(main, corner_radius=CARD_RADIUS)
        form_card.pack(fill="x", pady=(0, 20))

        form_inner = ctk.CTkFrame(form_card, fg_color="transparent")
        form_inner.pack(fill="x", padx=24, pady=22)

        self.nip_entry = self._create_field(
            form_inner, "NIP / ID Karyawan", self.nip_var,
            placeholder="Contoh: 12345",
            validator=_validate_nip,
            helper="Hanya angka, maks 50 digit",
        )
        self.nama_entry = self._create_field(
            form_inner, "Nama Lengkap", self.nama_var,
            placeholder="Contoh: Enrico Kevin Ariantho",
            validator=_validate_nama,
            helper="Hanya huruf, spasi, . ' - (maks 100 karakter)",
        )

        # Jabatan = pilihan tetap antara Dosen / Staff Internal
        ctk.CTkLabel(
            form_inner, text="Jabatan",
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        ctk.CTkSegmentedButton(
            form_inner, variable=self.jabatan_var,
            values=["Dosen", "Staff Internal"],
            font=ctk.CTkFont(size=12, weight="bold"),
            height=38, corner_radius=8,
        ).pack(fill="x", pady=(0, 14))

        # ---- INFO BOX ----
        info_card = ctk.CTkFrame(main, corner_radius=CARD_RADIUS)
        info_card.pack(fill="x", pady=(0, 20))

        ctk.CTkLabel(
            info_card,
            text="💡  Setelah klik 'Lanjut', kamu akan diminta upload 3 foto wajah\n"
                 "    (frontal, miring kanan, miring kiri) format JPG / JPEG / PNG.",
            font=ctk.CTkFont(size=11),
            justify="left",
        ).pack(anchor="w", padx=18, pady=14)

        # ---- BUTTONS ----
        btns = ctk.CTkFrame(main, fg_color="transparent")
        btns.pack(fill="x")

        ctk.CTkButton(
            btns, text="Batal",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=ACCENT_GRAY, hover_color="#4b5563",
            corner_radius=10, height=42,
            command=self.window.destroy,
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            btns, text="Lanjut ke Upload Foto  →",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ACCENT_GREEN, hover_color="#0ea271",
            corner_radius=10, height=42,
            command=self._on_next,
        ).pack(side="left", fill="x", expand=True, padx=(6, 0))

    def _create_field(self, parent, label, variable, placeholder="", validator=None,
                      helper=None):
        ctk.CTkLabel(
            parent, text=label,
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        entry = ctk.CTkEntry(
            parent, textvariable=variable,
            placeholder_text=placeholder,
            font=ctk.CTkFont(size=12),
            height=38, corner_radius=8,
        )

        if validator is not None:
            # Real-time validation per keystroke. %P = proposed value setelah edit.
            # Return False -> ditolak, char gak masuk.
            vcmd = (self.window.register(validator), '%P')
            entry.configure(validate='key', validatecommand=vcmd)

        entry.pack(fill="x", pady=(0, 4 if helper else 14))

        if helper:
            ctk.CTkLabel(
                parent, text=helper,
                font=ctk.CTkFont(size=10),
                text_color="gray", anchor="w",
            ).pack(fill="x", pady=(0, 10))

        return entry

    def _validate_form(self):
        nip = self.nip_var.get().strip()
        nama = self.nama_var.get().strip()
        jabatan = self.jabatan_var.get().strip()

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

        if jabatan not in ("Dosen", "Staff Internal"):
            errors.append("• Jabatan harus Dosen atau Staff Internal")

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
            'jenis': self.jenis_var.get(),
        }

    def _on_next(self):
        data = self._validate_form()
        if data is None:
            return

        confirm = messagebox.askyesno(
            "Konfirmasi Data",
            f"Pastikan data berikut sudah benar:\n\n"
            f"NIP: {data['nip']}\n"
            f"Nama: {data['nama']}\n"
            f"Jabatan: {data['jabatan']}\n\n"
            f"Lanjut ke upload foto?"
        )
        if not confirm:
            return

        self.window.destroy()

        from src.ui.upload_enrollment import open_upload_enrollment
        open_upload_enrollment(self.parent, data)


def open_enrollment_window(parent):
    EnrollmentWindow(parent)
