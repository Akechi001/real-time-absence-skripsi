# src/ui/camera_enrollment.py - Window Camera Enrollment dengan 5 Pose

import tkinter as tk
from tkinter import messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.ui.theme import get_colors, get_button_colors, hover_color
from src.modules.face_detector import FaceDetector
from src.modules.face_recognizer import FaceRecognizer
from src.database.operations import save_karyawan, save_template
import config


POSES = [
    {'number': 1, 'title': 'Tatap Lurus', 'instruction': 'Hadapkan wajah lurus ke kamera', 'icon': '👁️'},
    {'number': 2, 'title': 'Miring ke Kanan', 'instruction': 'Putar wajah sedikit ke kanan (~15°)', 'icon': '↪️'},
    {'number': 3, 'title': 'Miring ke Kiri', 'instruction': 'Putar wajah sedikit ke kiri (~15°)', 'icon': '↩️'},
    {'number': 4, 'title': 'Sedikit Menunduk', 'instruction': 'Tundukkan kepala sedikit (~10°)', 'icon': '⬇️'},
    {'number': 5, 'title': 'Sedikit Mendongak', 'instruction': 'Dongakkan kepala sedikit (~10°)', 'icon': '⬆️'},
]


class CameraEnrollmentWindow:
    def __init__(self, parent, karyawan_data, on_complete=None):
        self.parent = parent
        self.karyawan_data = karyawan_data
        self.on_complete = on_complete
        self.colors = get_colors()

        self.current_pose_idx = 0
        self.embeddings = []
        self.is_running = False
        self.cap = None
        self.last_face_count = 0
        self.last_faces = []

        self.window = tk.Toplevel(parent)
        self.window.title(f"Enrollment - {karyawan_data['nama']}")
        # PENTING: Window cukup tinggi agar tombol kelihatan
        self.window.geometry("750x900")
        self.window.resizable(True, True)
        self.window.minsize(700, 800)
        self.window.configure(bg=self.colors['bg_primary'])

        self._center_window()
        self.window.transient(parent)
        self.window.grab_set()

        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        # Keyboard shortcuts
        self.window.bind('<space>', lambda e: self._on_capture())
        self.window.bind('<Escape>', lambda e: self._on_cancel())
        self.window.focus_set()

        print("Loading face detection models...")
        self.detector = FaceDetector()
        self.recognizer = FaceRecognizer()

        self._create_widgets()
        self._start_camera()

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
            pady=15
        )
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ========== TOMBOL DI BAWAH (PACK PERTAMA DARI BAWAH) ==========
        # Ini KUNCI: pack tombol PERTAMA dengan side=BOTTOM
        # supaya tidak ke-cut sama widget lain
        button_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(15, 0))

        self.btn_cancel = self._create_button(
            button_frame,
            text="✕ Batal  (ESC)",
            button_type='gray',
            command=self._on_cancel
        )
        self.btn_cancel.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.btn_capture = self._create_button(
            button_frame,
            text="📸 Ambil Foto  (SPACE)",
            button_type='green',
            command=self._on_capture
        )
        self.btn_capture.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # ========== HEADER (PACK DARI ATAS) ==========
        header_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        header_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        title_label = tk.Label(
            header_frame,
            text=f"📸 Enrollment Foto - {self.karyawan_data['nama']}",
            font=("Helvetica", 14, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_primary']
        )
        title_label.pack()

        subtitle_label = tk.Label(
            header_frame,
            text=f"NIP: {self.karyawan_data['nip']}  |  Jabatan: {self.karyawan_data['jabatan']}",
            font=("Helvetica", 9),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_primary']
        )
        subtitle_label.pack(pady=(2, 0))

        # ========== POSE INSTRUCTION ==========
        instruction_card = tk.Frame(
            main_frame,
            bg=self.colors['bg_secondary'],
            highlightbackground=self.colors['btn_blue'],
            highlightthickness=2
        )
        instruction_card.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        instruction_inner = tk.Frame(
            instruction_card,
            bg=self.colors['bg_secondary'],
            padx=15,
            pady=10
        )
        instruction_inner.pack(fill=tk.X)

        self.progress_label = tk.Label(
            instruction_inner,
            text="",
            font=("Helvetica", 10, "bold"),
            fg=self.colors['btn_blue'],
            bg=self.colors['bg_secondary']
        )
        self.progress_label.pack()

        self.pose_title_label = tk.Label(
            instruction_inner,
            text="",
            font=("Helvetica", 15, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['bg_secondary']
        )
        self.pose_title_label.pack(pady=(3, 0))

        self.pose_instruction_label = tk.Label(
            instruction_inner,
            text="",
            font=("Helvetica", 11),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_secondary']
        )
        self.pose_instruction_label.pack(pady=(3, 0))

        self.face_status_label = tk.Label(
            instruction_inner,
            text="",
            font=("Helvetica", 10, "bold"),
            bg=self.colors['bg_secondary']
        )
        self.face_status_label.pack(pady=(5, 0))

        # ========== CAMERA PREVIEW (FILL SISA RUANG) ==========
        # ========== CAMERA PREVIEW ==========
        camera_frame = tk.Frame(
            main_frame,
            bg=self.colors['bg_primary'],
            highlightthickness=0
        )
        camera_frame.pack(fill=tk.BOTH, expand=True)

        # Camera label - blend dengan background
        self.camera_label = tk.Label(
            camera_frame,
            bg=self.colors['bg_primary']
        )
        self.camera_label.pack(expand=True)

        self._update_pose_display()

    def _create_button(self, parent, text, button_type, command):
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

    def _update_pose_display(self):
        if self.current_pose_idx >= len(POSES):
            return

        pose = POSES[self.current_pose_idx]

        self.progress_label.config(text=f"POSE {pose['number']} DARI 5")
        self.pose_title_label.config(text=f"{pose['icon']}  {pose['title']}")
        self.pose_instruction_label.config(text=pose['instruction'])

    def _start_camera(self):
        """Mulai kamera untuk enrollment"""
        try:
            # Tentukan kamera mana yang digunakan
            # Skenario A: ENROLLMENT_CAMERA_INDEX = None → fallback ke CAMERA_INDEX
            # Skenario B: ENROLLMENT_CAMERA_INDEX = 1 → pakai kamera external
            camera_idx = getattr(config, 'ENROLLMENT_CAMERA_INDEX', None)
            if camera_idx is None:
                camera_idx = config.CAMERA_INDEX
                print(f"📷 Enrollment menggunakan kamera index {camera_idx} (Skenario A: 1 kamera)")
            else:
                print(f"📷 Enrollment menggunakan kamera index {camera_idx} (Skenario B: 2 kamera)")

            self.cap = cv2.VideoCapture(camera_idx)
            if not self.cap.isOpened():
                messagebox.showerror(
                    "Error",
                    f"Tidak bisa membuka kamera (index: {camera_idx}).\n\n"
                    f"Pastikan:\n"
                    f"• Kamera terhubung ke laptop\n"
                    f"• Tidak ada aplikasi lain yang menggunakan kamera\n"
                    f"• Mode absensi tidak sedang berjalan"
                )
                self.window.destroy()
                return

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)

            self.is_running = True
            self._update_frame()
        except Exception as e:
            messagebox.showerror("Error", f"Gagal memulai kamera: {e}")
            self.window.destroy()

    def _update_frame(self):
        if not self.is_running or self.cap is None:
            return

        ret, frame = self.cap.read()
        if not ret:
            self.window.after(30, self._update_frame)
            return

        faces = self.detector.detect(frame)
        self.last_faces = faces
        self.last_face_count = len(faces)

        display_frame = frame.copy()
        for face in faces:
            x1, y1, x2, y2, conf = face[:5]
            color = (0, 255, 0) if len(faces) == 1 else (0, 165, 255)
            cv2.rectangle(display_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
            label = f"Face {conf:.2f}"
            cv2.putText(display_frame, label, (int(x1), int(y1) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        self._update_face_status()

        rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb_frame)
        # Resize ke ukuran yang lebih kecil agar muat
        img = img.resize((600, 450), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(image=img)

        self.camera_label.config(image=photo)
        self.camera_label.image = photo

        self.window.after(33, self._update_frame)

    def _update_face_status(self):
        count = self.last_face_count

        if count == 0:
            self.face_status_label.config(
                text="⚠️ Tidak ada wajah terdeteksi",
                fg=self.colors['btn_red']
            )
        elif count == 1:
            self.face_status_label.config(
                text="✓ Wajah terdeteksi - Siap ambil foto",
                fg=self.colors['btn_green']
            )
        else:
            self.face_status_label.config(
                text=f"⚠️ Terdeteksi {count} wajah - Pastikan hanya 1 orang",
                fg=self.colors['btn_orange']
            )

    def _flash_success(self, message):
        """Tampilkan flash success message di face_status_label"""
        self.face_status_label.config(
            text=message,
            fg=self.colors['btn_green']
        )
        # Auto-hide setelah 1.5 detik (biar kembali ke status normal)
        self.window.after(1500, self._update_face_status)

    def _on_capture(self):
        if self.last_face_count == 0:
            messagebox.showwarning(
                "Tidak Ada Wajah",
                "Tidak ada wajah terdeteksi. Pastikan wajah terlihat di kamera."
            )
            return

        if self.last_face_count > 1:
            messagebox.showwarning(
                "Banyak Wajah",
                f"Terdeteksi {self.last_face_count} wajah.\n"
                f"Pastikan hanya 1 orang di depan kamera."
            )
            return

        ret, frame = self.cap.read()
        if not ret:
            messagebox.showerror("Error", "Gagal mengambil frame dari kamera")
            return

        faces = self.detector.detect(frame)
        if len(faces) != 1:
            messagebox.showwarning(
                "Capture Gagal",
                "Wajah tidak terdeteksi dengan baik. Coba lagi."
            )
            return

        face = faces[0]
        bbox = [int(x) for x in face[:4]]

        embedding = self.recognizer.get_embedding(frame, bbox)

        if embedding is None:
            messagebox.showwarning(
                "Capture Gagal",
                "Gagal mengextract fitur wajah. Coba lagi."
            )
            return

        self.embeddings.append(embedding)

        pose = POSES[self.current_pose_idx]
        print(f"✓ Pose {pose['number']} ({pose['title']}) - foto berhasil diambil")

        self.current_pose_idx += 1

        if self.current_pose_idx >= len(POSES):
            self._finish_enrollment()
        else:
            self._update_pose_display()
            # Flash hijau di status sebagai feedback visual (tanpa popup)
            self._flash_success(f"✓ Foto pose {pose['number']} berhasil!")


    def _finish_enrollment(self):
        self.is_running = False
        if self.cap:
            self.cap.release()
            self.cap = None

        self.face_status_label.config(
            text="💾 Menyimpan data ke database...",
            fg=self.colors['btn_blue']
        )
        self.window.update()

        try:
            id_karyawan = save_karyawan(
                self.karyawan_data['nip'],
                self.karyawan_data['nama'],
                self.karyawan_data['jabatan'],
                self.karyawan_data['jenis']
            )

            if not id_karyawan:
                messagebox.showerror(
                    "Gagal",
                    "Gagal menyimpan data karyawan.\nCek apakah NIP sudah ada di database."
                )
                self.window.destroy()
                return

            avg_embedding = np.mean(self.embeddings, axis=0)
            success = save_template(id_karyawan, avg_embedding)

            if success:
                messagebox.showinfo(
                    "🎉 Enrollment Berhasil!",
                    f"Karyawan baru berhasil didaftarkan!\n\n"
                    f"ID: {id_karyawan}\n"
                    f"Nama: {self.karyawan_data['nama']}\n"
                    f"Total foto: 5\n"
                    f"Embedding dimensi: {len(avg_embedding)}\n\n"
                    f"Karyawan sudah siap untuk absensi."
                )

                if self.on_complete:
                    self.on_complete(id_karyawan)

                self.window.destroy()
            else:
                messagebox.showerror(
                    "Gagal",
                    "Data karyawan tersimpan, tapi template foto gagal disimpan."
                )
                self.window.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Terjadi kesalahan saat menyimpan:\n{e}")
            self.window.destroy()

    def _on_cancel(self):
        if self.current_pose_idx == 0:
            self._on_close()
            return

        confirm = messagebox.askyesno(
            "Batal Enrollment?",
            f"Anda sudah mengambil {self.current_pose_idx} foto.\n"
            f"Yakin ingin membatalkan enrollment?\n\n"
            f"Data tidak akan disimpan."
        )
        if confirm:
            self._on_close()

    def _on_close(self):
        self.is_running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        self.window.destroy()


def open_camera_enrollment(parent, karyawan_data, on_complete=None):
    CameraEnrollmentWindow(parent, karyawan_data, on_complete)