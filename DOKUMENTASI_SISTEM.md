# Dokumentasi Sistem Absensi Wajah dengan Liveness Detection

> **Sistem Absensi Otomatis berbasis Face Recognition dengan Verifikasi Liveness Detection 2-Tahap**
> Skripsi — Enrico Kevin Ariantho (NIM 0806022210012)
> STIE Ciputra Makassar

---

## Daftar Isi

1. [Gambaran     Umum Sistem](#1-gambaran-umum-sistem)
2. [Tech Stack & Dependencies](#2-tech-stack--dependencies)
3. [Arsitektur Sistem](#3-arsitektur-sistem)
4. [Struktur Folder Proyek](#4-struktur-folder-proyek)
5. [Komponen Inti](#5-komponen-inti)
6. [Database Schema](#6-database-schema)
7. [Alur Kerja Sistem](#7-alur-kerja-sistem)
8. [Konfigurasi & Threshold](#8-konfigurasi--threshold)
9. [Antarmuka Pengguna (UI)](#9-antarmuka-pengguna-ui)
10. [Mode Operasi 24 Jam](#10-mode-operasi-24-jam)
11. [Algoritma Resolver Tengah Malam](#11-algoritma-resolver-tengah-malam)
12. [Optimasi & Mitigasi Memory](#12-optimasi--mitigasi-memory)
13. [Cara Menjalankan Sistem](#13-cara-menjalankan-sistem)

---

## 1. Gambaran Umum Sistem

Sistem ini adalah aplikasi desktop untuk **pencatatan kehadiran karyawan** menggunakan **pengenalan wajah (face recognition)** secara *real-time*, dilengkapi dengan **verifikasi keaslian (liveness detection) dua tahap** untuk mencegah serangan *spoofing* (foto cetak, foto di layar HP, dll).

### Karakteristik Utama

| Aspek | Penjelasan |
|---|---|
| **Tipe Sistem** | Desktop application (Python + Tkinter) |
| **Mode Input** | Kamera real-time (laptop / webcam external) |
| **Output** | Database PostgreSQL + payload JSON (siap integrasi backend HRIS) |
| **Akurasi Pengenalan** | ArcFace cosine similarity threshold 0.4 |
| **Anti-Spoofing** | 2-stage: motion-based liveness + CNN-based texture analysis |
| **Resolusi Keputusan** | Batch tengah malam (passage-based logging) |

### Filosofi Desain

1. **Pemisahan tanggung jawab**: sistem ini hanya **mencatat lewatan (passage) mentah** di pintu masuk. Keputusan final (check-in / check-out / status terlambat) dihitung *batch* tengah malam, **bukan** *real-time*. Ini mencegah ketidakkonsistenan saat karyawan melewati kamera berulang kali.
2. **Data acquisition layer**: sistem ini bertugas sebagai *data layer* — overlay logika bisnis (cuti, izin, half-day) dilakukan oleh server HRIS terpisah di sisi kampus.
3. **Failsafe**: sistem punya `auto-restart loop` (mode 24 jam) yang memantau dan menghidupkan ulang proses absensi jika terjadi *crash*.

---

## 2. Tech Stack & Dependencies

### Bahasa & Runtime

| Komponen | Versi | Tujuan |
|---|---|---|
| **Python** | 3.11 | Bahasa utama |
| **macOS** | Apple Silicon (M-series) | Lingkungan deployment & development |
| **PostgreSQL** | 18 | Database relasional |

### Library Computer Vision & ML

| Library | Versi | Fungsi |
|---|---|---|
| **Ultralytics (YOLO)** | 8.4.33 | Face detection (YOLO26n custom-trained) |
| **InsightFace** | 0.7.3 | Face recognition (ArcFace) + 2D landmark detection (`buffalo_l` model) |
| **ONNX Runtime** | 1.24.4 | Inference engine untuk model InsightFace |
| **PyTorch** | 2.11.0 | Inference engine untuk model anti-spoofing (MiniFASNet) |
| **OpenCV** | 4.13.0 | Capture frame kamera, manipulasi gambar, display |
| **NumPy** | 2.4.4 | Operasi numerik (embedding, landmark) |
| **Pillow** | 12.2.0 | Konversi format gambar (PIL ↔ ndarray) |

### Library Database

| Library | Versi | Fungsi |
|---|---|---|
| **psycopg2-binary** | 2.9.11 | Driver PostgreSQL untuk Python |
| **python-dotenv** | 1.2.2 | Load `.env` file untuk kredensial DB |

### Library Antarmuka Pengguna

| Library | Versi | Fungsi |
|---|---|---|
| **CustomTkinter** | 5.2.2 | UI modern dengan *rounded corners* + dark mode native |
| **Tkinter** | built-in | Engine GUI Python (di-wrap oleh CustomTkinter) |

### Model File

| File | Ukuran | Sumber |
|---|---|---|
| `yolo26n_face.pt` | 5.4 MB | YOLO26n custom-trained untuk deteksi wajah |
| `2.7_80x80_MiniFASNetV2.pth` | 1.8 MB | Anti-spoofing CNN (Silent-Face) |
| `4_0_0_80x80_MiniFASNetV1SE.pth` | 1.8 MB | Anti-spoofing CNN dengan Squeeze-Excitation |
| InsightFace `buffalo_l` | ~330 MB | Detection + Recognition + Landmark (download otomatis dari ~/.insightface) |

---

## 3. Arsitektur Sistem

### Diagram Tingkat Tinggi

```
┌─────────────────────────────────────────────────────────────────┐
│                    Pintu Masuk Kampus                            │
│  ┌───────────────┐                                              │
│  │ Kamera Webcam │                                              │
│  └───────┬───────┘                                              │
│          │ video stream                                          │
└──────────┼──────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│              SISTEM ABSENSI (Local Process)                      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Mode Real-time (attendance subprocess)                    │   │
│  │ ┌──────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │   │
│  │ │ YOLO ├─►│ ArcFace  ├─►│ Liveness ├─►│ Anti-Spoofing│  │   │
│  │ │ Face │  │ (buffalo │  │ Stage 1  │  │ Stage 2      │  │   │
│  │ │ Det. │  │ _l)      │  │ (EAR+Head│  │ (MiniFASNet) │  │   │
│  │ └──────┘  └──────────┘  └──────────┘  └──────┬───────┘  │   │
│  │                                                │           │   │
│  │                                                ▼           │   │
│  │                                          INSERT row        │   │
│  └─────────────────────────────────┬────────────────────────┘   │
│                                    │                              │
│  ┌─────────────────────────────────▼──────────────────────────┐  │
│  │ PostgreSQL: absensi_face                                    │  │
│  │ • karyawan (master)                                         │  │
│  │ • template_wajah (embedding ArcFace)                        │  │
│  │ • log_absensi (raw lewatan / passage)                       │  │
│  │ • absensi_harian (hasil resolve tengah malam)               │  │
│  │ • resolve_log (audit trail batch job)                       │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                    ▲                              │
│  ┌─────────────────────────────────┴──────────────────────────┐  │
│  │ Batch Job (launchd 00:05 daily)                            │  │
│  │ scripts/midnight_resolve.py                                │  │
│  │  → resolve_attendance_for_date() per tanggal yang belum    │  │
│  │    diproses → INSERT ke absensi_harian                     │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ UI Dashboard (ui_app.py) — CustomTkinter SaaS-style       │   │
│  │ ┌──────────┐ ┌──────────┐ ┌──────────────────────────┐   │   │
│  │ │ Sidebar  │ │ Dashboard│ │ Karyawan / Log Absensi   │   │   │
│  │ └──────────┘ └──────────┘ └──────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
           │
           ▼ (payload JSON, future integration)
┌─────────────────────────────────────────────────────────────────┐
│            Server HRIS STIE Ciputra Makassar (External)          │
│  Overlay business logic (MHL, cuti, izin, half-day, libur)       │
└─────────────────────────────────────────────────────────────────┘
```

### Multi-Process Design

Sistem dibagi menjadi **3 proses Python** yang independen:

| Proses | File | Tugas |
|---|---|---|
| **UI Process** | `ui_app.py` → `main_window.py` | Dashboard admin, mengelola karyawan, lihat log |
| **Attendance Subprocess** | `main.py` → `src/attendance.py` | Buka kamera, jalankan pipeline biometrik, insert ke DB |
| **Daemon Wrapper** | `scripts/attendance_daemon.py` | Auto-restart loop untuk attendance subprocess |

Komunikasi antar-proses: **via database PostgreSQL** (shared state). UI dan attendance tidak punya IPC langsung — keduanya baca/tulis tabel yang sama.

### Threading di Attendance Subprocess

Dalam **proses attendance**, ada **2 thread**:

```
Main Thread (cv2 + UI display)
  ├─ Capture frame dari kamera (cv2.VideoCapture.read)
  ├─ Render display_frame ke window cv2.imshow
  ├─ Trigger Background Worker tiap 1/FPS_SAMPLING detik
  └─ Polling key Q untuk exit

Background Worker Thread
  ├─ YOLO inference (face detection)
  ├─ InsightFace inference (ArcFace + landmark)
  ├─ Liveness Stage 1 (EAR + head movement)
  ├─ Anti-Spoofing Stage 2 (MiniFASNet)
  ├─ INSERT log_absensi
  └─ gc.collect() tiap 5 menit (mitigasi leak)
```

Pemisahan ini menjaga **UI display tetap responsif** walaupun inferensi memakan 200-500ms per frame.

---

## 4. Struktur Folder Proyek

```
real-time-absence-skripsi/
│
├── main.py                          # Entry point mode absensi (CLI subprocess)
├── ui_app.py                        # Entry point UI admin
├── config.py                        # Konfigurasi global (threshold, kamera, DB)
├── yolo26n_face.pt                  # Model YOLO custom-trained
├── .env                             # Kredensial PostgreSQL (gitignored)
│
├── models/anti_spoofing/            # Bobot model anti-spoofing
│   ├── 2.7_80x80_MiniFASNetV2.pth
│   └── 4_0_0_80x80_MiniFASNetV1SE.pth
│
├── data/photos/{id_karyawan}/       # Foto asli enrollment (audit trail)
│   ├── foto_frontal.jpg
│   ├── foto_kanan.jpg
│   └── foto_kiri.jpg
│
├── logs/                            # Log harian dari daemon mode
│   ├── attendance.log               # Current day
│   ├── attendance.log.YYYY-MM-DD    # Rotated (keep 30 hari)
│   └── midnight_resolve.log
│
├── src/
│   ├── attendance.py                # AttendanceSystem class (pipeline biometrik)
│   ├── payload.py                   # Build & send JSON payload (stub)
│   │
│   ├── modules/
│   │   ├── face_detector.py         # YOLO26 wrapper
│   │   ├── face_recognizer.py       # InsightFace ArcFace wrapper
│   │   ├── liveness.py              # EAR adaptive + head movement
│   │   └── anti_spoofing/
│   │       ├── MiniFASNet.py        # Arsitektur CNN (dari Silent-Face)
│   │       └── detector.py          # Ensemble inference + softmax voting
│   │
│   ├── database/
│   │   ├── db.py                    # Connection helper
│   │   └── operations.py            # CRUD + resolver + statistics
│   │
│   ├── ui/                          # CustomTkinter SaaS dashboard
│   │   ├── theme.py                 # Color palette light/dark
│   │   ├── main_window.py           # DashboardApp (sidebar + content)
│   │   ├── home_page.py             # Dashboard home (prediksi hari ini)
│   │   ├── karyawan_list.py         # Daftar karyawan + CRUD
│   │   ├── log_absensi.py           # 2 tab: Harian + Raw Lewatan
│   │   ├── enrollment_window.py     # Form tambah karyawan
│   │   ├── upload_enrollment.py     # Upload 3 foto + face detect
│   │   └── camera_picker.py         # Modal pilih kamera + preview
│   │
│   └── utils/
│       └── camera_detector.py       # Enumerate kamera available
│
└── scripts/
    ├── attendance_daemon.py         # Auto-restart loop (24 jam mode)
    ├── midnight_resolve.py          # Resolver batch (dipanggil launchd)
    ├── preview_camera.py            # Preview kamera (subprocess utility)
    ├── start.sh                     # Startup checklist
    ├── mem_monitor.py               # Pantau RSS proses (dev tool)
    ├── com.absensi.midnight.plist   # launchd config (template)
    ├── MIDNIGHT_SETUP.md            # Dokumentasi setup launchd
    └── migrations/
        ├── 001_absensi_harian.sql   # CREATE tabel absensi_harian + resolve_log
        └── 002_allow_passage_event.sql  # ALTER constraint untuk 'passage'
```

---

## 5. Komponen Inti

### 5.1 Face Detection — YOLO26n Custom-Trained

**File**: `src/modules/face_detector.py`

YOLO (You Only Look Once) versi 26 nano, di-*fine-tune* khusus untuk deteksi wajah manusia. Model `.pt` ukuran 5.4 MB, dijalankan di CPU (Apple Silicon Neural Engine tidak digunakan langsung; ultralytics fallback ke CPU MPS).

**Karakteristik**:
- Input: frame BGR `(H, W, 3)` dari OpenCV
- Output: list bounding box `[x1, y1, x2, y2, confidence]`
- Confidence threshold: `0.5` (config.YOLO_CONFIDENCE)
- Latency: ~30–200 ms/frame (tergantung CPU throttle)

**Filter aspect ratio**: hanya bounding box dengan `aspect_ratio ∈ [0.5, 1.5]` yang diloloskan, untuk memastikan wajah relatif frontal (filter sudut yaw ekstrem).

### 5.2 Face Recognition — InsightFace ArcFace

**File**: `src/modules/face_recognizer.py`

**Model**: `buffalo_l` dari InsightFace (ONNX format), terdiri dari 3 sub-model:
- **Detection** (`det_10g.onnx`) — backup detector + landmark anchor
- **Recognition** (`w600k_r50.onnx`) — ArcFace ResNet50, output embedding 512-dim
- **Landmark 2D-106** (`2d106det.onnx`) — 106 titik landmark wajah (dipakai untuk EAR)

**Workflow**:
1. `app.get(frame)` → list of Face object dengan `bbox`, `embedding`, `landmark_2d_106`
2. Match bbox YOLO dengan bbox InsightFace berdasarkan overlap area
3. Hitung **cosine similarity** antara embedding query dan setiap template di DB
4. Threshold: cosine ≥ `0.4` (FACE_SIMILARITY_THRESHOLD)

**Detector size**: `(320, 320)` — lebih kecil dari default `(640, 640)` untuk speedup ~2-3x.

### 5.3 Liveness Detection Stage 1 — EAR Adaptive + Head Movement

**File**: `src/modules/liveness.py`

Stage 1 adalah **motion-based liveness** menggunakan dua sinyal:

#### A. Eye Aspect Ratio (EAR) dengan Adaptive Threshold

EAR mendeteksi kedipan dengan mengukur rasio tinggi/lebar mata.

```
EAR = (height of eye region) / (width of eye region)
```

**Landmark mata** (dari InsightFace 2D-106):
- Mata kanan: indices `[33, 35, 36, 37, 38, 39, 40, 41, 42]`
- Mata kiri: indices `[87, 88, 89, 90, 91, 93, 94, 95, 96]`

**Adaptive Threshold**:
- Sistem kalibrasi **10 frame pertama** → ambil **median** sebagai `baseline_ear`
- Threshold dinamis: `baseline_ear × 0.75`
- Kedipan terdeteksi jika EAR turun < threshold selama `EAR_CONSEC_FRAMES = 1` frame

**Mengapa adaptive?** Setiap orang punya EAR baseline berbeda (peneliti = 0.13–0.18, orang lain bisa 0.30+). Fixed threshold (mis. 0.20) sering false-positive untuk orang dengan mata sipit/fokus ke layar.

#### B. Head Movement Detection

Track posisi **nose tip** (landmark index `86`) di sliding window 8 frame terakhir.

```
movement = max(positions) - min(positions)  # per axis (x, y)
head_moved = movement > HEAD_MOVE_THRESHOLD (15 pixel)
```

**Liveness lolos jika**: `blink_count ≥ 1` OR `head_moved == True`

**Per-track state**: setiap `track_id` (face slot) punya state independen. Di-reset setelah berhasil log absensi (lewat `reset_state`).

### 5.4 Liveness Detection Stage 2 — Anti-Spoofing CNN (MiniFASNet)

**File**: `src/modules/anti_spoofing/detector.py`, `MiniFASNet.py`

Stage 2 menggunakan **ensemble dua CNN** dari proyek Silent-Face-Anti-Spoofing (Minivision):

| Model | Input | Tipe | Fungsi |
|---|---|---|---|
| `2.7_80x80_MiniFASNetV2.pth` | 80×80 RGB, scale 2.7× face | V2 base | Texture analysis pada face crop |
| `4_0_0_80x80_MiniFASNetV1SE.pth` | 80×80 RGB, scale 4.0× face | V1 dengan Squeeze-Excitation | Wider context (with surrounding) |

**Cara kerja**:
1. Crop wajah dengan padding sesuai `scale` (2.7× atau 4.0× dari bounding box)
2. Resize ke 80×80, normalize, ubah ke tensor
3. Inference tiap model → softmax output `[p_spoof_class0, p_real, p_spoof_class2]`
4. **Average ensemble** (softmax voting): `avg_prediction = (V2_output + V1SE_output) / 2`
5. Label = `argmax(avg_prediction)`:
   - Label `1` = wajah asli (real)
   - Label `0` dan `2` = spoofing (cetak / layar)

**Threshold**: real jika `is_real AND confidence ≥ 0.5`

**Karakteristik berdasarkan uji empiris**:
| Skenario serangan | Hasil deteksi |
|---|---|
| Wajah asli (live) | Confidence 0.99–1.00 untuk class real |
| Foto cetak diam | Ditolak konsisten 100% |
| Foto cetak digerakkan | Stage 1 kadang lolos, Stage 2 **selalu tolak** |
| Foto di layar HP | Ditolak konsisten 100% |

### 5.5 Sequential Pipeline

Pipeline absensi pada `AttendanceSystem.process_frame()`:

```python
1. YOLO.detect(frame)              → bounding boxes (fast filter)
2. InsightFace.app.get(frame)      → embeddings + landmarks (1 call shared)
3. ArcFace.get_embedding(bbox)     → query embedding
4. ArcFace.identify(embedding)     → match dengan template DB
5. Cek cooldown (60 detik per id)  → skip kalau masih cooldown
6. LivenessStage1.check(face_obj)  → EAR + head movement
7. AntiSpoofing.predict(frame)     → MiniFASNet ensemble
8. save_log_absensi('passage')     → INSERT row mentah
9. build_payload + send_payload    → HTTP POST (stub)
10. Set cooldown + reset liveness state
```

**Cooldown**: 60 detik per `id_karyawan`. Mencegah double-logging kalau orang berdiri di depan kamera. Karyawan lain tetap diproses normal di periode itu.

### 5.6 Passage-Based Logging

Filosofi: sistem **tidak menentukan** check-in vs check-out *real-time*. Setiap deteksi disimpan sebagai **'passage'** (lewatan). Keputusan final diambil **batch tengah malam**.

**Mengapa**: kalau orang melewati kamera 4× (06:55, 07:20, 07:30, 07:55), sistem alternating akan menghasilkan 2 check-in + 2 check-out (kacau). Pendekatan passage menghindari ini — hari berakhir → ambil `MIN(timestamp)` = check-in beneran, `MAX(timestamp)` = check-out beneran.

---

## 6. Database Schema

### 6.1 Tabel `karyawan`

Master data karyawan.

| Kolom | Tipe | Constraint | Keterangan |
|---|---|---|---|
| `id_karyawan` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `nip` | VARCHAR(50) | UNIQUE NOT NULL | Nomor Induk Pegawai (digit only) |
| `nama` | VARCHAR(100) | NOT NULL | Nama lengkap |
| `jabatan` | VARCHAR(100) |  | "Dosen" atau "Staff Internal" |
| `jenis_karyawan` | VARCHAR(20) |  | "internal" (vendor sudah di-filter, lihat catatan) |
| `status_aktif` | BOOLEAN | DEFAULT TRUE | Soft delete flag |

**Catatan**: Vendor secara DB tetap bisa ada, tapi UI saat ini cuma menampilkan internal. Soft delete (`status_aktif = FALSE`) digunakan untuk menjaga referensi `log_absensi` historis.

### 6.2 Tabel `template_wajah`

Embedding ArcFace untuk pencocokan identitas.

| Kolom | Tipe | Constraint | Keterangan |
|---|---|---|---|
| `id_karyawan` | INTEGER | FK → karyawan(id_karyawan) | |
| `embedding` | BYTEA | NOT NULL | Pickle dump dari numpy array 512-dim |
| `versi_model` | VARCHAR(50) |  | "yolo26n_face+buffalo_l" |

**Embedding** dihitung sebagai rata-rata dari **3 foto enrollment** (frontal, kanan, kiri):
```python
avg_embedding = np.mean([emb_frontal, emb_kanan, emb_kiri], axis=0)
```

### 6.3 Tabel `log_absensi` (raw passage)

Setiap deteksi kamera = 1 row.

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id_log` | SERIAL PK | Auto-increment |
| `id_karyawan` | INTEGER FK | |
| `timestamp` | TIMESTAMP DEFAULT NOW | Waktu deteksi |
| `jenis_event` | VARCHAR CHECK | 'passage', 'check-in', 'check-out' (legacy) |
| `confidence_score` | FLOAT | Cosine similarity ArcFace |
| `status_liveness` | BOOLEAN | Stage 1 + Stage 2 keduanya lolos? |
| `keterangan` | VARCHAR CHECK | 'normal', 'half-day', 'leaving-office' |

**Constraint** `jenis_event_check`: `jenis_event IN ('passage', 'check-in', 'check-out')` — `'passage'` ditambahkan via migration `002`.

### 6.4 Tabel `absensi_harian` (resolved)

Hasil resolve batch tengah malam.

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id_absensi` | SERIAL PK | |
| `id_karyawan` | INTEGER FK | |
| `tanggal` | DATE | Tanggal yang di-resolve |
| `check_in_time` | TIMESTAMP NULL | MIN(timestamp) atau NULL jika data tidak lengkap |
| `check_out_time` | TIMESTAMP NULL | MAX(timestamp) atau NULL |
| `status_terlambat` | BOOLEAN NULL | TRUE jika check_in > WORK_START_TIME |
| `status_pulang_cepat` | BOOLEAN NULL | TRUE jika check_out < WORK_END_TIME |
| `keterangan` | TEXT | "normal", "terlambat", "pulang cepat", "terlambat, pulang cepat", "data tidak lengkap..." |
| `resolved_at` | TIMESTAMP | Waktu batch job jalan |

**Constraint** `UNIQUE(id_karyawan, tanggal)` — satu row per karyawan per hari.

### 6.5 Tabel `resolve_log` (audit)

Audit trail batch job. Mencegah re-process tanggal yang sudah berhasil.

| Kolom | Tipe |
|---|---|
| `tanggal` | DATE PK |
| `resolved_at` | TIMESTAMP |
| `karyawan_count` | INTEGER (jumlah karyawan yang di-resolve hari itu) |

---

## 7. Alur Kerja Sistem

### 7.1 Enrollment (Pendaftaran Karyawan Baru)

```
[UI Admin]
  Klik "Tambah Karyawan" di page Karyawan
       ↓
  Form: NIP (digit only), Nama (huruf only), Jabatan (Dosen/Staff Internal)
       ↓
  Validasi real-time + submission-time
       ↓
  Buka window Upload Foto (3 slot: frontal, kanan, kiri)
       ↓
  Untuk tiap slot:
    - filedialog → file JPG/JPEG/PNG
    - YOLO detect → cek tepat 1 wajah
    - InsightFace get_embedding → ekstrak embedding 512-dim
    - Preview thumbnail dengan bounding box hijau/merah
       ↓
  Klik Simpan:
    - Hitung avg_embedding = mean([3 embedding])
    - Transaksi atomic:
        INSERT INTO karyawan + INSERT INTO template_wajah
        (kalau salah satu gagal → rollback semua, mencegah orphan)
    - Copy foto asli ke data/photos/{id_karyawan}/
```

**Foto disimpan** untuk audit trail dan re-extraction jika model di-upgrade nanti.

### 7.2 Mode Absensi (Real-time)

```
[Dashboard]
  Klik "🎥 Mulai Absensi"
       ↓
  Camera Picker: pilih kamera + Preview button
       ↓
  Confirm → spawn attendance_daemon.py subprocess (detached)
       ↓
  Daemon loop:
    spawn main.py → load model → buka kamera → render UI cv2
       ↓
    Main thread (cv2):
      capture frame → render display → trigger BG worker tiap 50ms
       ↓
    BG worker thread:
      YOLO detect → ArcFace match → Liveness Stage 1 → Stage 2
      → INSERT 'passage' ke log_absensi → send payload
       ↓
    Tekan Q → exit code 0 → daemon stop
    Atau crash → daemon auto-restart (dengan backoff)
```

**Auto-restart logic** (`scripts/attendance_daemon.py`):
- Exit code `0` = intentional stop → daemon berhenti
- Exit code `!= 0` = crash → restart setelah 3 detik
- Crash throttle: 3× dalam 60 detik → wait 30 detik (mencegah tight loop)

**Logging**: `logs/attendance.log` dengan `TimedRotatingFileHandler` (rotate jam 00:00 setiap hari, simpan 30 hari terakhir).

### 7.3 Resolver Tengah Malam (Batch Job)

```
[launchd / macOS scheduler]
  Trigger 00:05 setiap hari → spawn scripts/midnight_resolve.py
       ↓
  midnight_resolve.py:
    - get_unresolved_dates(until=yesterday)
        → SELECT DISTINCT date FROM log_absensi
          WHERE date <= yesterday
          AND date NOT IN (SELECT tanggal FROM resolve_log)
       ↓
    Untuk tiap tanggal yang belum di-resolve:
      resolve_attendance_for_date(tanggal)
        → Query: GROUP BY id_karyawan WHERE date(timestamp) = tanggal
          (filter internal saja)
        → Untuk tiap karyawan:
            cnt < 2  → check_in/out NULL, "data tidak lengkap"
            cnt ≥ 2  → check_in = MIN, check_out = MAX
                     status_terlambat = (MIN.time > 07:30)
                     status_pulang_cepat = (MAX.time < 17:00)
        → INSERT INTO absensi_harian (ON CONFLICT DO NOTHING)
        → UPSERT INTO resolve_log
       ↓
  Log ke logs/midnight_resolve.log
```

**Idempotent**: aman jalan berkali-kali (resolve_log skip tanggal yang sudah selesai).

**Lazy Fallback**: kalau laptop sleep saat 00:05 dan launchd skip, **UI auto-resolve** saat buka page Dashboard atau Log Absensi (lewat `resolve_pending()` di refresh).

### 7.4 Prediksi Hari Ini (Dashboard Real-time)

Tabel **"Prediksi Absensi Hari Ini"** di Dashboard menggunakan logika berbeda dari midnight resolver:

```python
def predict_today_absensi(now):
    day_ended = (now.time() >= WORK_END_TIME)

    For each karyawan dengan lewatan hari ini:
        if not day_ended:
            # Hari masih berjalan — last_passage hanya "last seen", bukan check-out
            check_in = MIN(timestamp)
            check_out = NULL          # diam-diam dianggap belum pulang
            status = "Belum Pulang" (+ "Terlambat" kalau check_in > 07:30)
        elif cnt < 2:
            status = "Data Tidak Lengkap"
        else:
            check_in = MIN, check_out = MAX
            status_terlambat = MIN.time > 07:30
            status_pulang_cepat = MAX.time < 17:00
```

**Mengapa dipisah**: sebelum jam pulang, sistem **tidak boleh asumsi** karyawan sudah pulang hanya karena last detection 11:00. Mereka mungkin masih di kantor.

---

## 8. Konfigurasi & Threshold

Semua di `config.py`:

### Database

```python
DB_CONFIG = {
    "host":     localhost,
    "port":     5432,
    "database": absensi_face,
    "user":     postgres,
    "password": (dari .env)
}
```

### Face Detection (YOLO26)

```python
YOLO_MODEL_PATH   = "yolo26n_face.pt"
YOLO_CONFIDENCE   = 0.5    # minimal confidence buat dianggap wajah
YOLO_DEVICE       = "cpu"  # tidak pakai GPU/MPS
```

### Face Recognition (InsightFace ArcFace)

```python
INSIGHTFACE_MODEL          = "buffalo_l"
FACE_SIMILARITY_THRESHOLD  = 0.4    # cosine similarity minimum
```

### Liveness Detection

```python
EAR_THRESHOLD        = 0.20  # fallback statis (sebelum adaptive kalibrasi)
EAR_CONSEC_FRAMES    = 1     # frame berturut-turut EAR di bawah threshold → blink
HEAD_MOVE_THRESHOLD  = 15    # pixel — gerakan nose tip dalam window
LIVENESS_WINDOW      = 8     # ukuran sliding window untuk head movement
```

### Anti-Spoofing CNN

```python
ANTI_SPOOFING_THRESHOLD = 0.5  # minimum confidence untuk dianggap real face
```

### Kamera

```python
CAMERA_INDEX = 0       # default, bisa override via UI camera picker
FRAME_WIDTH  = 640
FRAME_HEIGHT = 480
FPS_SAMPLING = 20      # frame per detik untuk inference (bukan render)
```

### Cooldown

```python
COOLDOWN_SECONDS = 60  # interval antar deteksi untuk karyawan yang sama
```

### Resolver Tengah Malam

```python
WORK_START_TIME       = "07:30"   # check-in setelah ini = terlambat
WORK_END_TIME         = "17:00"   # check-out sebelum ini = pulang cepat
RESOLVE_ONLY_INTERNAL = True      # vendor di-skip dari absensi_harian
```

---

## 9. Antarmuka Pengguna (UI)

Sistem UI menggunakan **CustomTkinter** untuk tampilan SaaS modern dengan rounded corners. Arsitektur: **single-window dengan sidebar + content area** (tidak ada modal Toplevel kecuali untuk dialog enrollment).

### 9.1 Layout Dashboard

```
┌──────────────────────────────────────────────────────────────────┐
│ 🎓 Absensi Wajah   │  Dashboard               🎥 Mulai Absensi  │
│   STIE Ciputra Mks │  Selamat datang!...                          │
│                    │                                               │
│ MENU               │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐            │
│ ▶ 📊 Dashboard     │  │ 12  │ │  4  │ │  1  │ │  0  │            │
│   👥 Karyawan      │  └─────┘ └─────┘ └─────┘ └─────┘            │
│   📋 Log Absensi   │   Total   Today  Terlam  Cepat               │
│                    │                                               │
│                    │  🔮 Prediksi Absensi Hari Ini  Lihat Riwayat→│
│                    │  ┌──────────────────────────────────────┐    │
│                    │  │ Nama       │ Jabatan │ In    │ Status│    │
│                    │  │ Enrico K.  │ Dosen   │ 07:25 │ ✓ Norm│    │
│                    │  └──────────────────────────────────────┘    │
│                    │                                               │
│ © 2026 EKA         │                                               │
└──────────────────────────────────────────────────────────────────┘
```

### 9.2 Tiga Page Utama

| Page | Tombol Kanan Atas | Konten |
|---|---|---|
| **Dashboard** | 🎥 Mulai Absensi (toggle Start/Stop) | 4 stat cards + tabel prediksi hari ini |
| **Karyawan** | ➕ Tambah Karyawan + 🔄 Refresh | Tabel CRUD + tombol Hapus |
| **Log Absensi** | 📥 Export CSV + 🔄 Refresh | 2 tab: Absensi Harian + Raw Lewatan |

### 9.3 Auto-Refresh

Tiap **5 detik**, page yang sedang aktif dipanggil `.refresh()`:
- Dashboard: stat cards + tabel prediksi
- Karyawan: tabel daftar (dengan preserve selection)
- Log Absensi: tabel data + lazy resolve

**Implementasi** (`main_window.py:_tick_auto_refresh`):
```python
def _tick_auto_refresh(self):
    if not self._auto_refresh_paused:
        page = self.pages.get(self.current_name)
        if page and hasattr(page, 'refresh'):
            page.refresh()
    self._auto_refresh_job = self.root.after(5000, self._tick_auto_refresh)
```

### 9.4 Validasi Input

Pada form Tambah Karyawan:

| Field | Validasi Real-time (per keystroke) | Validasi Submit |
|---|---|---|
| **NIP** | Hanya digit, max 50 karakter | Tidak boleh kosong |
| **Nama** | Hanya huruf + spasi + `. ' -`, max 100 | Min 2 karakter |
| **Jabatan** | SegmentedButton: Dosen / Staff Internal | Salah satu dari dua opsi |

### 9.5 Camera Picker

Sebelum mulai absensi, modal dialog muncul:
- Dropdown kamera dengan label generic ("Kamera 1 · 1920×1080")
- Tombol **👁 Preview** — spawn subprocess `scripts/preview_camera.py` untuk verifikasi visual sebelum confirm
- Tombol **Batal / Mulai Absensi**

**Catatan**: nama kamera tidak deterministik di macOS karena OpenCV backend AVFoundation tidak expose `uniqueID`. Preview button adalah ground truth visual.

---

## 10. Mode Operasi 24 Jam

### Komponen

```
ui_app.py [UI Dashboard]
   │
   │ klik "Mulai Absensi" → spawn subprocess
   ▼
scripts/attendance_daemon.py [Auto-Restart Loop]
   │
   │ spawn subprocess
   ▼
main.py → src/attendance.py [AttendanceSystem]
   │
   │ open camera, run pipeline
   ▼
PostgreSQL [log_absensi]
```

### Lifecycle

1. **Start**: user klik tombol → daemon spawn detached (`start_new_session=True`)
2. **Loop**:
   - Spawn `main.py` sebagai child subprocess
   - Tunggu sampai exit
   - Cek exit code:
     - `0` = user tekan Q → daemon stop
     - `≠ 0` = crash → restart setelah 3 detik (atau 30 detik jika throttled)
3. **Stop**: user klik tombol lagi → bikin file `logs/STOP` → daemon detect di iterasi berikutnya
4. **Log harian**: `logs/attendance.log` rotate jam 00:00 → keep 30 hari

### Signal Handling

```python
signal.signal(signal.SIGTERM, _on_signal)  # bikin STOP file → exit graceful
signal.signal(signal.SIGINT,  _on_signal)  # Ctrl-C dari terminal
```

### Auto-Start saat Boot (Opsional)

Plist `~/Library/LaunchAgents/com.absensi.attendance.plist`:
- `RunAtLoad = true` → daemon jalan otomatis saat user login

(File template ada di `scripts/`, perlu di-install manual.)

---

## 11. Algoritma Resolver Tengah Malam

### Pseudocode

```python
def resolve_attendance_for_date(tanggal):
    """
    Untuk satu tanggal, untuk tiap karyawan internal:
    - Ambil MIN + MAX timestamp dari log_absensi
    - Hitung status_terlambat & status_pulang_cepat
    - INSERT ke absensi_harian
    """
    work_start = parse("07:30")
    work_end   = parse("17:00")

    rows = QUERY:
        SELECT id_karyawan,
               MIN(timestamp) AS earliest,
               MAX(timestamp) AS latest,
               COUNT(*) AS cnt
        FROM log_absensi l
        JOIN karyawan k ON l.id_karyawan = k.id_karyawan
        WHERE DATE(l.timestamp) = tanggal
          AND k.status_aktif = TRUE
          AND k.jenis_karyawan = 'internal'
        GROUP BY l.id_karyawan

    for (id, earliest, latest, cnt) in rows:
        if cnt < 2:
            INSERT (
                check_in   = NULL,
                check_out  = NULL,
                keterangan = f"data tidak lengkap (cuma 1 lewatan jam {earliest.HH:MM})"
            )
        else:
            terlambat   = earliest.time() > work_start
            pulang_cepat = latest.time() < work_end
            INSERT (
                check_in            = earliest,
                check_out           = latest,
                status_terlambat    = terlambat,
                status_pulang_cepat = pulang_cepat,
                keterangan          = compose(terlambat, pulang_cepat)
            ) ON CONFLICT DO NOTHING

    UPSERT INTO resolve_log (tanggal, karyawan_count = len(rows))
```

### Tiga Lapis Pengaman Eksekusi

| Layer | Trigger | Reliability |
|---|---|---|
| **1. launchd 00:05 otomatis** | macOS scheduler | Jalan otomatis kalau laptop nyala/sleep |
| **2. Lazy fallback di UI** | Saat user buka Dashboard/Log Absensi | Jalan saat user interaksi |
| **3. Manual via script** | `python scripts/midnight_resolve.py` | Operator memicu sendiri |

**Idempotent**: tiga-tiganya aman dijalankan bersamaan (resolve_log mencegah duplikasi).

---

## 12. Optimasi & Mitigasi Memory

### Masalah Awal

Sistem berjalan 24/7 dengan model deep learning (YOLO + InsightFace + 2 MiniFASNet) → memory bisa **terus naik** karena:
1. **PhotoImage leak** di Tkinter (saat enrollment lama menggunakan live preview kamera)
2. **YOLO Results object** menahan reference ke `orig_img` (frame input)
3. **InsightFace Face object** simpan embedding + landmark 2D/3D (~15-20KB per face)
4. **NumPy view** ke landmark array menahan Face object hidup di deque liveness
5. **ONNX/Torch arena memory pool** tidak release sampai dipaksa

### Mitigasi yang Diterapkan

| Lokasi | Teknik |
|---|---|
| `src/ui/upload_enrollment.py` | Drop live preview kamera (refactor ke upload-based) — hilangkan 33ms PhotoImage loop |
| `src/modules/face_detector.py:detect()` | `del results` setelah iterasi |
| `src/attendance.py:process_frame()` | `del faces_insightface` setelah loop |
| `src/modules/liveness.py:check_liveness()` | `nose_tip = landmarks[86].copy()` — putus view ke Face object |
| `src/attendance.py:background_worker()` | `gc.collect()` periodik tiap 5 menit |

### Tooling

- `scripts/mem_monitor.py` — pantau RSS proses attendance dari terminal lain
- `gc.collect()` log: `🧹 gc.collect() → N objects released`

### Hasil Empiris

| Sebelum | Sesudah |
|---|---|
| Growth ~5-10 MB/menit (linear) | Fluktuatif di range 200-810 MB (stable) |
| Crash ~1-2 jam | Jalan 4-6+ jam tanpa masalah |

macOS Memory Compression juga aktif → halaman model yang jarang diakses ter-kompresi, RSS swing ekstrim (200 ↔ 810 MB) adalah fitur normal.

---

## 13. Cara Menjalankan Sistem

### 13.1 Setup Awal

```bash
# 1. Clone repo
cd ~/IdeaProjects/real-time-absence-skripsi

# 2. Install Python 3.11 + Tkinter (macOS)
brew install python@3.11 python-tk@3.11

# 3. Bikin venv
python3.11 -m venv venv
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt   # ultralytics, insightface, opencv, etc.

# 5. Setup PostgreSQL
brew install postgresql@18
brew services start postgresql@18
createdb absensi_face
# Edit .env dengan kredensial PostgreSQL

# 6. Jalankan migrations
psql -U postgres -d absensi_face -f scripts/migrations/001_absensi_harian.sql
psql -U postgres -d absensi_face -f scripts/migrations/002_allow_passage_event.sql

# 7. (Opsional) Setup launchd untuk midnight resolver
# Lihat scripts/MIDNIGHT_SETUP.md
```

### 13.2 Jalankan App

```bash
source venv/bin/activate
python ui_app.py
```

Atau cek dependency sehat dulu:

```bash
bash scripts/start.sh
```

### 13.3 Setelah Restart Laptop

```bash
cd ~/IdeaProjects/real-time-absence-skripsi
source venv/bin/activate
python ui_app.py
```

- Postgres auto-start (sudah `brew services start`)
- launchd auto-load (kalau sudah di-setup)
- UI Dashboard tinggal di-buka

---

## Lampiran

### A. Skenario Pengujian yang Direkomendasikan untuk BAB IV Skripsi

**Black-box Functional Testing**:
1. Tambah karyawan baru (form valid, foto valid) → tersimpan di DB
2. Tambah karyawan dengan foto tanpa wajah → ditolak dengan pesan jelas
3. Tambah karyawan dengan NIP duplikat → ditolak
4. Mulai mode absensi → kamera buka, deteksi wajah jalan
5. Stop mode absensi (Q key) → daemon stop graceful
6. Midnight resolver dipicu manual → row absensi_harian terbuat

**Performa Biometrik**:
- **Recognition**: 5 orang × 10 trial → ukur akurasi (TPR), FAR, FRR
- **Anti-Spoofing**: 4 skenario serangan × 10 trial:
  - Wajah asli (genuine attempt)
  - Foto cetak diam
  - Foto cetak digerakkan
  - Foto di layar HP/tablet
- **Latensi**: rata-rata waktu pipeline per frame (catat dari log `TIMING:`)

**Reliability**:
- Jalankan mode 24 jam selama 4-6 jam
- Catat: jumlah auto-restart, RSS over time, uptime persen

### B. Catatan Integrasi dengan Server Kampus (HRIS)

Sistem ini didesain sebagai **data acquisition layer**. Server kampus mengambil data dari sistem ini (via push payload atau pull DB) dan meng-overlay dengan tabel MHL (cuti, izin, half-day, libur nasional).

Status final attendance (approved / rejected / dispensasi) tidak ditentukan oleh sistem ini, melainkan oleh server HRIS. Sistem ini hanya mencatat **fakta deteksi kamera** (passage) dan **status raw** (terlambat berdasarkan WORK_START_TIME).

**Format payload JSON** (saat ini stub di `src/payload.py`):

```json
{
    "id_karyawan": 17,
    "nama": "Enrico Kevin Ariantho",
    "timestamp": "2026-05-27T11:50:09.765218",
    "jenis_event": "passage",
    "confidence_score": 0.653,
    "status_liveness": true,
    "keterangan": "normal",
    "source": "face_recognition_system",
    "versi_model": "yolo26n_face+buffalo_l"
}
```

Endpoint HTTP POST tinggal aktivasi di `send_payload()`.

---

*Dokumentasi ini dibuat untuk keperluan skripsi Sidang Akhir. Update terakhir: 2026-05-27.*
