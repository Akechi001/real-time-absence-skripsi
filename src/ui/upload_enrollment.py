# src/ui/upload_enrollment.py - Upload 3 foto studio (CustomTkinter modal)

import os
import sys
import shutil
import tkinter as tk
from tkinter import messagebox, filedialog

import cv2
import numpy as np
import customtkinter as ctk
from PIL import Image

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.modules.face_detector import FaceDetector
from src.modules.face_recognizer import FaceRecognizer
from src.database.operations import save_karyawan_with_template
import config


POSES = [
    {'key': 'frontal', 'title': 'Foto 1: Frontal',      'subtitle': 'Tatap lurus ke kamera'},
    {'key': 'kanan',   'title': 'Foto 2: Miring Kanan', 'subtitle': 'Wajah ~15° ke kanan'},
    {'key': 'kiri',    'title': 'Foto 3: Miring Kiri',  'subtitle': 'Wajah ~15° ke kiri'},
]

ALLOWED_EXTS = ('.jpg', '.jpeg', '.png')
PREVIEW_W, PREVIEW_H = 220, 270
CARD_RADIUS = 14

ACCENT_GREEN = "#10b981"
ACCENT_BLUE  = "#3b82f6"
ACCENT_RED   = "#ef4444"
ACCENT_GRAY  = "#6b7280"


def _safe_imread(path):
    """cv2.imread tahan path non-ASCII"""
    data = np.fromfile(path, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


class UploadEnrollmentWindow:
    def __init__(self, parent, karyawan_data, on_complete=None):
        self.parent = parent
        self.karyawan_data = karyawan_data
        self.on_complete = on_complete

        # state per slot
        self.slots = [None, None, None]
        self.preview_imgs = [None, None, None]  # ref CTkImage

        self.window = ctk.CTkToplevel(parent)
        self.window.title(f"Upload Foto - {karyawan_data['nama']}")
        self.window.geometry("900x800")
        self.window.minsize(820, 720)
        self._center_window()

        self.window.transient(parent)
        self.window.after(50, lambda: self.window.grab_set())
        self.window.protocol("WM_DELETE_WINDOW", self._on_cancel)

        print("Loading face detection models...")
        self.detector = FaceDetector()
        self.recognizer = FaceRecognizer()

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

    # ------------------------------------------------------------------
    # LAYOUT
    # ------------------------------------------------------------------
    def _build_widgets(self):
        main = ctk.CTkFrame(self.window, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=28, pady=22)

        # ---- TOMBOL BAWAH (pack pertama biar tidak ke-cut) ----
        btns = ctk.CTkFrame(main, fg_color="transparent")
        btns.pack(side="bottom", fill="x", pady=(18, 0))

        ctk.CTkButton(
            btns, text="✕  Batal",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=ACCENT_GRAY, hover_color="#4b5563",
            corner_radius=10, height=44,
            command=self._on_cancel,
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            btns, text="💾  Simpan Karyawan",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ACCENT_GREEN, hover_color="#0ea271",
            corner_radius=10, height=44,
            command=self._on_save,
        ).pack(side="left", fill="x", expand=True, padx=(6, 0))

        # ---- HEADER ----
        ctk.CTkLabel(
            main, text=f"📁  Upload Foto Studio — {self.karyawan_data['nama']}",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            main,
            text=f"NIP: {self.karyawan_data['nip']}   |   "
                 f"Jabatan: {self.karyawan_data['jabatan']}",
            font=ctk.CTkFont(size=10),
            text_color="gray",
        ).pack(anchor="w", pady=(2, 10))

        ctk.CTkLabel(
            main,
            text="Upload 3 foto wajah dari HRD/HCM (JPG / JPEG / PNG). "
                 "Tiap foto harus berisi tepat 1 wajah.",
            font=ctk.CTkFont(size=11, slant="italic"),
            text_color="gray",
        ).pack(anchor="w", pady=(0, 16))

        # ---- 3 CARD ROW ----
        cards = ctk.CTkFrame(main, fg_color="transparent")
        cards.pack(fill="both", expand=True)
        for i in range(3):
            cards.grid_columnconfigure(i, weight=1, uniform="card")

        self.preview_labels = []
        self.status_labels = []
        for idx, pose in enumerate(POSES):
            self._build_card(cards, idx, pose)

    def _build_card(self, parent, idx, pose):
        card = ctk.CTkFrame(parent, corner_radius=CARD_RADIUS)
        card.grid(row=0, column=idx, sticky="nsew",
                  padx=(0 if idx == 0 else 8, 8 if idx < 2 else 0))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=18)

        ctk.CTkLabel(
            inner, text=pose['title'],
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack()

        ctk.CTkLabel(
            inner, text=pose['subtitle'],
            font=ctk.CTkFont(size=10),
            text_color="gray",
        ).pack(pady=(2, 12))

        # Preview area — placeholder via empty CTkLabel
        preview = ctk.CTkLabel(
            inner,
            text="(belum ada foto)",
            width=PREVIEW_W, height=PREVIEW_H,
            corner_radius=10,
            fg_color=("#f3f4f6", "#1f2937"),
            text_color="gray",
            font=ctk.CTkFont(size=11, slant="italic"),
        )
        preview.pack(pady=(0, 10))
        self.preview_labels.append(preview)

        status = ctk.CTkLabel(
            inner, text="Belum di-upload",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="gray",
            wraplength=PREVIEW_W,
        )
        status.pack(pady=(0, 10))
        self.status_labels.append(status)

        ctk.CTkButton(
            inner, text="📁  Pilih File",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=ACCENT_BLUE, hover_color="#2563eb",
            corner_radius=8, height=36,
            command=lambda i=idx: self._on_pick_file(i),
        ).pack(fill="x")

    # ------------------------------------------------------------------
    # FILE HANDLING
    # ------------------------------------------------------------------
    def _on_pick_file(self, idx):
        path = filedialog.askopenfilename(
            title=f"Pilih foto untuk {POSES[idx]['title']}",
            filetypes=[("JPEG / PNG", "*.jpg *.jpeg *.png"), ("All files", "*.*")],
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()
        if ext not in ALLOWED_EXTS:
            messagebox.showerror(
                "Format Tidak Didukung",
                f"Hanya JPG/JPEG/PNG.\nFile kamu: {ext}",
            )
            return

        frame = _safe_imread(path)
        if frame is None:
            messagebox.showerror(
                "File Rusak", f"Gagal baca file:\n{path}"
            )
            return

        faces = self.detector.detect(frame)
        if len(faces) == 0:
            self._set_invalid(idx, "✗  Tidak ada wajah terdeteksi")
            self._show_preview(idx, frame, faces=[], failed=True)
            return
        if len(faces) > 1:
            self._set_invalid(idx, f"✗  Terdeteksi {len(faces)} wajah — pastikan hanya 1 orang")
            self._show_preview(idx, frame, faces=faces, failed=True)
            return

        bbox = [int(x) for x in faces[0][:4]]
        embedding = self.recognizer.get_embedding(frame, bbox)
        if embedding is None:
            self._set_invalid(idx, "✗  Gagal ekstrak fitur wajah")
            self._show_preview(idx, frame, faces=faces, failed=True)
            return

        self.slots[idx] = {
            'path': path,
            'embedding': embedding,
            'frame': frame,
        }
        self._show_preview(idx, frame, faces=faces, failed=False)
        self._set_valid(idx, "✓  Wajah terdeteksi & fitur diekstrak")

    def _show_preview(self, idx, frame_bgr, faces, failed):
        display = frame_bgr.copy()
        for face in faces:
            x1, y1, x2, y2, _ = face[:5]
            color = (0, 0, 255) if failed else (0, 255, 0)  # BGR
            cv2.rectangle(display, (int(x1), int(y1)), (int(x2), int(y2)), color, 3)

        rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        pil.thumbnail((PREVIEW_W, PREVIEW_H), Image.Resampling.LANCZOS)

        ctk_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=pil.size)
        self.preview_imgs[idx] = ctk_img  # keep ref
        self.preview_labels[idx].configure(image=ctk_img, text="")

    def _set_valid(self, idx, msg):
        self.status_labels[idx].configure(text=msg, text_color=ACCENT_GREEN)

    def _set_invalid(self, idx, msg):
        self.slots[idx] = None
        self.status_labels[idx].configure(text=msg, text_color=ACCENT_RED)

    # ------------------------------------------------------------------
    # SAVE
    # ------------------------------------------------------------------
    def _on_save(self):
        if not all(self.slots):
            missing = [POSES[i]['title'] for i, s in enumerate(self.slots) if s is None]
            messagebox.showwarning(
                "Foto Belum Lengkap",
                "Mohon upload semua foto:\n\n• " + "\n• ".join(missing),
            )
            return

        confirm = messagebox.askyesno(
            "Konfirmasi",
            f"Simpan karyawan ini?\n\n"
            f"NIP: {self.karyawan_data['nip']}\n"
            f"Nama: {self.karyawan_data['nama']}\n"
            f"Jabatan: {self.karyawan_data['jabatan']}\n"
            f"Foto: 3 file di-upload",
        )
        if not confirm:
            return

        # Karyawan + template di-insert dalam satu transaksi.
        # Kalau template gagal, karyawan-insert otomatis rollback —
        # mencegah orphan record (karyawan tanpa foto).
        embeddings = np.stack([s['embedding'] for s in self.slots])
        avg_embedding = np.mean(embeddings, axis=0)

        id_karyawan = save_karyawan_with_template(
            self.karyawan_data['nip'],
            self.karyawan_data['nama'],
            self.karyawan_data['jabatan'],
            self.karyawan_data['jenis'],
            avg_embedding,
        )
        if not id_karyawan:
            messagebox.showerror(
                "Gagal",
                "Gagal simpan data karyawan + foto.\n"
                "Cek apakah NIP sudah ada di database.",
            )
            return

        # Karyawan + template sukses di DB → baru copy foto asli ke disk
        try:
            target_dir = os.path.join(config.PHOTOS_DIR, str(id_karyawan))
            os.makedirs(target_dir, exist_ok=True)
            for slot, pose in zip(self.slots, POSES):
                ext = os.path.splitext(slot['path'])[1].lower()
                dst = os.path.join(target_dir, f"foto_{pose['key']}{ext}")
                shutil.copy2(slot['path'], dst)
        except Exception as e:
            messagebox.showwarning(
                "Foto Tidak Tersalin",
                f"Karyawan tersimpan (ID {id_karyawan}) tapi gagal copy foto fisik:\n{e}\n\n"
                f"Embedding tetap ada di DB, sistem absensi tetap bisa kenali wajah.",
            )

        messagebox.showinfo(
            "🎉  Enrollment Berhasil",
            f"Karyawan berhasil didaftarkan.\n\n"
            f"ID: {id_karyawan}\n"
            f"Nama: {self.karyawan_data['nama']}\n"
            f"Embedding dimensi: {len(avg_embedding)}",
        )

        if self.on_complete:
            self.on_complete(id_karyawan)
        self.window.destroy()

    def _on_cancel(self):
        if any(self.slots):
            if not messagebox.askyesno(
                "Batal Enrollment?",
                "Foto yang sudah di-upload akan hilang.\nYakin ingin batal?",
            ):
                return
        self.window.destroy()


def open_upload_enrollment(parent, karyawan_data, on_complete=None):
    UploadEnrollmentWindow(parent, karyawan_data, on_complete)
