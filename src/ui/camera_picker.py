# src/ui/camera_picker.py - Modal popup pilih kamera sebelum Mulai Absensi

import os
import subprocess
import sys
import tkinter as tk

import customtkinter as ctk

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.utils.camera_detector import list_cameras


# Path absolut ke scripts/preview_camera.py (anti relative resolution issues)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
)))
_PREVIEW_SCRIPT = os.path.join(_PROJECT_ROOT, 'scripts', 'preview_camera.py')


CARD_RADIUS = 14
ACCENT_GREEN = "#10b981"
ACCENT_GRAY = "#6b7280"
ACCENT_BLUE = "#3b82f6"


class CameraPickerDialog:
    """
    Modal dialog buat pilih kamera. Block sampai user pilih atau cancel.

    Pemakaian:
        idx = CameraPickerDialog.ask(parent, default_index=0)
        if idx is not None:
            # user pilih kamera idx
        else:
            # user batal
    """

    def __init__(self, parent, default_index=0):
        self.parent = parent
        self.default_index = default_index
        self.selected_index = None
        self.cameras = list_cameras()
        self._preview_proc = None  # track subprocess preview supaya tidak menumpuk

        self.window = ctk.CTkToplevel(parent)
        self.window.title("Pilih Kamera")
        self.window.geometry("520x340")
        self.window.resizable(False, False)
        self._center_window()

        self.window.transient(parent)
        self.window.after(50, lambda: self.window.grab_set())
        self.window.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self._build_widgets()

    @classmethod
    def ask(cls, parent, default_index=0):
        dialog = cls(parent, default_index)
        parent.wait_window(dialog.window)
        return dialog.selected_index

    # ------------------------------------------------------------------
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
        main.pack(fill="both", expand=True, padx=28, pady=24)

        # Header
        ctk.CTkLabel(
            main, text="🎥  Pilih Kamera",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            main, text="Kamera mana yang dipakai untuk mode absensi?",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        ).pack(anchor="w", pady=(4, 18))

        # Camera selector
        if not self.cameras:
            self._build_no_camera_state(main)
            return

        # Label di atas dropdown
        ctk.CTkLabel(
            main, text="Kamera",
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        # Build dropdown values
        self._labels = [c['label'] for c in self.cameras]
        self._index_by_label = {c['label']: c['index'] for c in self.cameras}

        # Cari label default — kalau default_index ada di list, pakai itu
        default_label = self._labels[0]
        for c in self.cameras:
            if c['index'] == self.default_index:
                default_label = c['label']
                break

        # Combo dropdown + tombol Preview di samping
        picker_row = ctk.CTkFrame(main, fg_color="transparent")
        picker_row.pack(fill="x", pady=(0, 12))

        self.combo_var = tk.StringVar(value=default_label)
        ctk.CTkComboBox(
            picker_row, variable=self.combo_var,
            values=self._labels,
            height=42, corner_radius=10,
            font=ctk.CTkFont(size=12),
            dropdown_font=ctk.CTkFont(size=12),
            state="readonly",
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            picker_row, text="👁  Preview",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=ACCENT_BLUE, hover_color="#2563eb",
            corner_radius=10, height=42, width=110,
            command=self._on_preview,
        ).pack(side="left", padx=(8, 0))

        # Info note — instruksi Preview
        ctk.CTkLabel(
            main,
            text="💡  Klik Preview untuk lihat live feed dari kamera yang dipilih. "
                 "Tekan Q di window preview untuk tutup.",
            font=ctk.CTkFont(size=10, slant="italic"),
            text_color="gray",
            wraplength=440, justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 18))

        # Buttons
        btns = ctk.CTkFrame(main, fg_color="transparent")
        btns.pack(fill="x")

        ctk.CTkButton(
            btns, text="Batal",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=ACCENT_GRAY, hover_color="#4b5563",
            corner_radius=10, height=42,
            command=self._on_cancel,
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            btns, text="🎥  Mulai Absensi",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ACCENT_GREEN, hover_color="#0ea271",
            corner_radius=10, height=42,
            command=self._on_confirm,
        ).pack(side="left", fill="x", expand=True, padx=(6, 0))

    def _build_no_camera_state(self, parent):
        """Empty state — tidak ada kamera ke-detect"""
        ctk.CTkLabel(
            parent, text="🚫",
            font=ctk.CTkFont(size=48),
        ).pack(pady=(20, 8))

        ctk.CTkLabel(
            parent, text="Tidak Ada Kamera Terdeteksi",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack()

        ctk.CTkLabel(
            parent,
            text="Pastikan kamera terhubung dan tidak dipakai aplikasi lain.\n"
                 "Restart app setelah kamera terpasang.",
            font=ctk.CTkFont(size=11),
            text_color="gray", justify="center",
        ).pack(pady=(6, 22))

        ctk.CTkButton(
            parent, text="Tutup",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=ACCENT_GRAY, hover_color="#4b5563",
            corner_radius=10, height=40, width=120,
            command=self._on_cancel,
        ).pack()

    def _on_confirm(self):
        label = self.combo_var.get()
        self.selected_index = self._index_by_label.get(label)
        self._kill_preview_proc()
        self.window.destroy()

    def _on_cancel(self):
        self.selected_index = None
        self._kill_preview_proc()
        self.window.destroy()

    def _on_preview(self):
        """Buka preview live feed via subprocess.

        Di macOS, cv2.imshow HARUS dipanggil di main thread proses Cocoa-nya.
        Memanggil dari thread Tkinter sekunder → "Unknown C++ exception".
        Solusinya: spawn proses Python terpisah yang punya main thread sendiri.

        Hanya 1 preview subprocess aktif sekaligus — kalau ada yang lama
        masih jalan, dia akan di-terminate dulu. Mencegah RAM bocor
        karena beberapa cv2.VideoCapture aktif bersamaan.
        """
        label = self.combo_var.get()
        idx = self._index_by_label.get(label)
        if idx is None:
            return

        # Bunuh preview process lama (kalau masih jalan) sebelum spawn baru
        self._kill_preview_proc()

        try:
            self._preview_proc = subprocess.Popen(
                [sys.executable, _PREVIEW_SCRIPT, str(idx), label],
                cwd=_PROJECT_ROOT,
            )
        except Exception as e:
            print(f"[preview] gagal spawn subprocess: {e}")

    def _kill_preview_proc(self):
        """Terminate preview subprocess yang lama (kalau masih jalan)."""
        p = self._preview_proc
        if p is None:
            return
        if p.poll() is not None:
            # Sudah exit sendiri
            self._preview_proc = None
            return
        try:
            p.terminate()
            try:
                p.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=1.0)
        except Exception as e:
            print(f"[preview] gagal terminate: {e}")
        finally:
            self._preview_proc = None
