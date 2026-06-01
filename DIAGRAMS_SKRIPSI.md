# Diagram-Diagram BAB III — Sistem Absensi Wajah

> Skripsi — Enrico Kevin Ariantho (NIM 0806022210012)
> STIE Ciputra Makassar

---

## 3.3.1.1 Use Case Diagram

```mermaid
flowchart LR
    subgraph Actors
        Admin([Admin / ICT])
        Karyawan([Karyawan Internal])
        System([System Scheduler])
        HRIS([Server HRIS Kampus])
    end

    subgraph SistemAbsensi["Sistem Absensi Wajah"]
        UC1((Tambah Karyawan<br/>Upload 3 Foto))
        UC2((Hapus Karyawan<br/>Soft Delete))
        UC3((Lihat Daftar Karyawan))
        UC4((Mulai Mode Absensi))
        UC5((Stop Mode Absensi))
        UC6((Pilih Kamera))
        UC7((Lihat Log Absensi))
        UC8((Lihat Prediksi Hari Ini))
        UC9((Export Log ke CSV))
        UC10((Resolve Absensi<br/>Tengah Malam))
        UC11((Auto-Restart<br/>Daemon Mode))
        UC12((Terdeteksi Kamera<br/>+ Diverifikasi Liveness))
        UC13((Push Payload<br/>ke Server HRIS))
    end

    Admin --> UC1
    Admin --> UC2
    Admin --> UC3
    Admin --> UC4
    Admin --> UC5
    Admin --> UC7
    Admin --> UC8
    Admin --> UC9
    UC4 -.includes.-> UC6

    Karyawan --> UC12

    System --> UC10
    System --> UC11

    UC12 -.->|trigger| UC13
    UC13 --> HRIS
```

### Tabel Skenario Use Case

| ID | Nama Use Case | Aktor | Deskripsi Singkat |
|---|---|---|---|
| UC1 | Tambah Karyawan | Admin/ICT | Daftarkan karyawan baru dengan upload 3 foto studio (frontal, kanan, kiri), embedding ArcFace di-extract & disimpan |
| UC2 | Hapus Karyawan | Admin/ICT | Soft delete karyawan (status_aktif=FALSE) + hard delete template_wajah |
| UC3 | Lihat Daftar Karyawan | Admin/ICT | Tampilkan tabel karyawan internal terdaftar |
| UC4 | Mulai Mode Absensi | Admin/ICT | Spawn daemon attendance subprocess + buka kamera real-time |
| UC5 | Stop Mode Absensi | Admin/ICT | Kirim sinyal STOP ke daemon untuk graceful shutdown |
| UC6 | Pilih Kamera | Admin/ICT | Modal dialog pilih kamera available + tombol Preview |
| UC7 | Lihat Log Absensi | Admin/ICT | 2 tab: Absensi Harian (resolved) + Raw Lewatan (passage mentah) |
| UC8 | Lihat Prediksi Hari Ini | Admin/ICT | Live preview hasil resolver berdasarkan lewatan kamera sampai sekarang |
| UC9 | Export Log ke CSV | Admin/ICT | Download tabel log dalam format CSV |
| UC10 | Resolve Absensi Tengah Malam | System (launchd) | Batch job harian 00:05 — agregat MIN/MAX timestamp jadi check-in/check-out |
| UC11 | Auto-Restart Daemon | System (daemon) | Wrapper attendance_daemon.py respawn main.py kalau crash atau uptime > 15 menit |
| UC12 | Terdeteksi Kamera | Karyawan (pasif) | Karyawan lewat → YOLO detect → ArcFace match → liveness verify → log passage |
| UC13 | Push Payload ke HRIS | System | Build JSON payload + kirim HTTP POST ke server kampus (stub) |

---

## 3.3.1.2 Activity Diagram

### A. Aktivitas Mode Absensi Real-Time

```mermaid
flowchart TD
    Start([Mulai]) --> A1[Spawn daemon subprocess]
    A1 --> A2[Load model: YOLO, InsightFace, MiniFASNet]
    A2 --> A3[Buka cv2.VideoCapture]
    A3 --> A4{Frame berhasil<br/>dibaca?}
    A4 -->|Tidak| A5[Retry 10x dengan delay 100ms]
    A5 --> A4_2{Recovered?}
    A4_2 -->|Tidak| End_Restart[Set preemptive_restart=True<br/>exit code 2]
    A4_2 -->|Ya| A4
    A4 -->|Ya| A6{Uptime ><br/>MAX_UPTIME_SECONDS?}
    A6 -->|Ya| End_Restart
    A6 -->|Tidak| A7[YOLO detect faces]
    A7 --> A8{Ada wajah?}
    A8 -->|Tidak| A4
    A8 -->|Ya| A9[InsightFace get embedding]
    A9 --> A10[ArcFace cosine similarity match]
    A10 --> A11{Confidence ><br/>0.4?}
    A11 -->|Tidak| A12[Mark: 'Wajah tidak dikenali']
    A12 --> A4
    A11 -->|Ya| A13{Karyawan<br/>cooldown?}
    A13 -->|Ya| A14[Skip — masih cooldown]
    A14 --> A4
    A13 -->|Tidak| A15[Liveness Stage 1:<br/>EAR + head movement]
    A15 --> A16{Live?}
    A16 -->|Tidak| A17[Mark: 'Liveness gagal']
    A17 --> A4
    A16 -->|Ya| A18[Liveness Stage 2:<br/>MiniFASNet ensemble]
    A18 --> A19{Real face?}
    A19 -->|Tidak| A20[Mark: 'Spoofing terdeteksi']
    A20 --> A4
    A19 -->|Ya| A21[INSERT log_absensi<br/>jenis_event='passage']
    A21 --> A22[Build & send payload]
    A22 --> A23[Set cooldown 60 detik]
    A23 --> A4
    A4 -->|Q ditekan| End_Stop[Set stop_event<br/>exit code 0]
    End_Restart --> Daemon_Restart[Daemon spawn main.py baru]
    Daemon_Restart --> A2
    End_Stop --> End([Selesai])
```

### B. Aktivitas Enrollment Karyawan

```mermaid
flowchart TD
    Start([Admin klik Tambah Karyawan]) --> B1[Form input: NIP, Nama, Jabatan]
    B1 --> B2{Validasi:<br/>NIP digit only<br/>Nama huruf only<br/>Jabatan dropdown}
    B2 -->|Invalid| B3[Tampilkan error]
    B3 --> B1
    B2 -->|Valid| B4[Konfirmasi data]
    B4 --> B5{User confirm?}
    B5 -->|Tidak| End_Cancel([Batal])
    B5 -->|Ya| B6[Buka Upload Foto Window]
    B6 --> B7[Slot Foto 1: Frontal]
    B7 --> B8[User pilih file]
    B8 --> B9{Format JPG/PNG?}
    B9 -->|Tidak| B10[Tolak: format tidak didukung]
    B10 --> B8
    B9 -->|Ya| B11[YOLO detect faces]
    B11 --> B12{Tepat 1 wajah?}
    B12 -->|Tidak| B13[Tolak: 0/banyak wajah]
    B13 --> B8
    B12 -->|Ya| B14[Extract ArcFace embedding]
    B14 --> B15{Embedding valid?}
    B15 -->|Tidak| B16[Tolak: gagal ekstrak]
    B16 --> B8
    B15 -->|Ya| B17[Preview thumbnail dengan bbox hijau]
    B17 --> B18{Sudah 3 foto?}
    B18 -->|Belum| B19[Lanjut ke slot berikutnya]
    B19 --> B8
    B18 -->|Ya| B20[Klik Simpan]
    B20 --> B21[Rata-rata 3 embedding]
    B21 --> B22[Transaksi atomic:<br/>INSERT karyawan + template_wajah]
    B22 --> B23{Sukses?}
    B23 -->|Tidak| B24[Rollback + tampilkan error]
    B24 --> End_Cancel
    B23 -->|Ya| B25[Copy foto asli ke data/photos/id_karyawan/]
    B25 --> B26[Tampilkan dialog sukses]
    B26 --> End([Selesai])
```

### C. Aktivitas Resolve Absensi Tengah Malam (Batch Job)

```mermaid
flowchart TD
    Start([launchd trigger 00:05]) --> C1[Eksekusi midnight_resolve.py]
    C1 --> C2[Query unresolved dates dari resolve_log]
    C2 --> C3{Ada tanggal<br/>belum di-resolve?}
    C3 -->|Tidak| C4[Log: 'Tidak ada tanggal untuk diresolve']
    C4 --> End([Selesai])
    C3 -->|Ya| C5[Loop tiap tanggal]
    C5 --> C6[Query GROUP BY id_karyawan<br/>FROM log_absensi WHERE date=tanggal<br/>AND jenis_karyawan='internal']
    C6 --> C7{Untuk tiap karyawan}
    C7 --> C8{Jumlah lewatan ><br/>= 2?}
    C8 -->|Tidak| C9[INSERT absensi_harian:<br/>check_in/out=NULL<br/>keterangan='data tidak lengkap']
    C8 -->|Ya| C10[check_in = MIN timestamp<br/>check_out = MAX timestamp]
    C10 --> C11[status_terlambat = check_in > 07:30]
    C11 --> C12[status_pulang_cepat = check_out < 17:00]
    C12 --> C13[INSERT absensi_harian<br/>ON CONFLICT DO NOTHING]
    C9 --> C14{Masih ada<br/>karyawan?}
    C13 --> C14
    C14 -->|Ya| C7
    C14 -->|Tidak| C15[UPSERT resolve_log:<br/>tanggal, karyawan_count]
    C15 --> C16{Masih ada<br/>tanggal?}
    C16 -->|Ya| C5
    C16 -->|Tidak| End
```

---

## 3.3.1.3 Sequence Diagram

### A. Sequence Mode Absensi Real-Time (Karyawan Lewat Kamera)

```mermaid
sequenceDiagram
    actor Karyawan
    participant Cam as Kamera
    participant AS as AttendanceSystem
    participant YOLO as FaceDetector
    participant IF as FaceRecognizer
    participant LV as LivenessDetector
    participant CNN as AntiSpoofingDetector
    participant DB as PostgreSQL
    participant Payload as PayloadSender

    Karyawan->>Cam: Berjalan di depan kamera
    Cam->>AS: cap.read() returns frame
    AS->>YOLO: detect(frame)
    YOLO-->>AS: bbox list [x1,y1,x2,y2,conf]
    AS->>IF: app.get(frame)
    IF-->>AS: faces with embedding + landmark
    AS->>IF: get_embedding(frame, bbox)
    IF-->>AS: embedding 512-dim
    AS->>DB: SELECT * FROM template_wajah
    DB-->>AS: list templates aktif
    AS->>AS: cosine_similarity per template
    AS->>AS: identify() → {id, nama, confidence}

    alt cooldown active
        AS-->>AS: skip (60s cooldown)
    else not in cooldown
        AS->>LV: check_liveness(track_id, face_obj)
        LV->>LV: EAR adaptive (10 frame calibration)
        LV->>LV: nose tip movement window
        LV-->>AS: is_live: bool

        alt is_live = False
            AS-->>AS: skip, display 'Liveness gagal'
        else is_live = True
            AS->>CNN: predict(frame, bbox)
            CNN->>CNN: crop face dengan scale 2.7 & 4.0
            CNN->>CNN: V2.forward(80x80) + V1SE.forward(80x80)
            CNN->>CNN: softmax ensemble voting
            CNN-->>AS: is_real, spoof_confidence

            alt is_real & conf >= 0.5
                AS->>DB: INSERT log_absensi(id, 'passage', conf, true)
                DB-->>AS: OK
                AS->>Payload: build_payload(id, nama, 'passage')
                Payload-->>AS: payload dict
                AS->>Payload: send_payload() [stub HTTP POST]
                AS->>AS: set cooldown 60s
            else spoofing detected
                AS-->>AS: skip, display 'Spoofing'
            end
        end
    end

    AS->>Cam: cv2.imshow(display_frame)
    Cam-->>Karyawan: Visual feedback dengan bbox & status
```

### B. Sequence Enrollment Karyawan Baru

```mermaid
sequenceDiagram
    actor Admin
    participant UI as DashboardApp
    participant KaryaList as KaryawanListFrame
    participant FormWin as EnrollmentWindow
    participant UploadWin as UploadEnrollmentWindow
    participant FD as FaceDetector
    participant FR as FaceRecognizer
    participant FS as FileSystem
    participant DB as PostgreSQL

    Admin->>UI: Klik nav 'Karyawan'
    UI->>KaryaList: show_page('karyawan')
    KaryaList-->>Admin: Tampilkan tabel karyawan

    Admin->>KaryaList: Klik 'Tambah Karyawan'
    KaryaList->>FormWin: open_enrollment_window(parent)
    FormWin-->>Admin: Form NIP/Nama/Jabatan

    Admin->>FormWin: Input data + klik Lanjut
    FormWin->>FormWin: _validate_form()
    FormWin->>FormWin: messagebox konfirmasi data
    Admin->>FormWin: Confirm
    FormWin->>UploadWin: open_upload_enrollment(parent, data)
    UploadWin-->>Admin: 3 slot upload (frontal/kanan/kiri)

    loop 3 kali (per slot foto)
        Admin->>UploadWin: Pilih file foto
        UploadWin->>FS: imread(path)
        FS-->>UploadWin: frame
        UploadWin->>FD: detect(frame)
        FD-->>UploadWin: faces list
        UploadWin->>UploadWin: Validasi tepat 1 wajah
        UploadWin->>FR: get_embedding(frame, bbox)
        FR-->>UploadWin: embedding 512-dim
        UploadWin->>UploadWin: Preview thumbnail + bbox hijau
    end

    Admin->>UploadWin: Klik 'Simpan'
    UploadWin->>UploadWin: avg_embedding = np.mean(3 embeddings)
    UploadWin->>DB: save_karyawan_with_template(transaksi atomic)
    DB->>DB: INSERT karyawan
    DB->>DB: INSERT template_wajah (BYTEA pickle)
    alt sukses
        DB-->>UploadWin: id_karyawan
        UploadWin->>FS: copy foto asli ke data/photos/id_karyawan/
        UploadWin-->>Admin: messagebox sukses
    else gagal (NIP duplikat dll)
        DB-->>UploadWin: rollback
        UploadWin-->>Admin: messagebox error
    end
```

### C. Sequence Resolve Absensi Tengah Malam

```mermaid
sequenceDiagram
    participant LA as launchd
    participant MR as midnight_resolve.py
    participant DB as PostgreSQL

    Note over LA,DB: Trigger setiap hari jam 00:05

    LA->>MR: Spawn process
    MR->>DB: SELECT unresolved dates
    DB-->>MR: [tanggal1, tanggal2, ...]

    loop Untuk tiap tanggal
        MR->>DB: SELECT id_karyawan, MIN, MAX, COUNT<br/>FROM log_absensi WHERE DATE = tanggal<br/>GROUP BY id_karyawan
        DB-->>MR: rows aggregated per karyawan

        loop Untuk tiap karyawan
            alt count >= 2 (data lengkap)
                MR->>MR: check_in = MIN<br/>check_out = MAX
                MR->>MR: status_terlambat = MIN.time > 07:30
                MR->>MR: status_pulang_cepat = MAX.time < 17:00
                MR->>DB: INSERT absensi_harian (full data)
            else count < 2 (data tidak lengkap)
                MR->>MR: check_in/out = NULL
                MR->>DB: INSERT absensi_harian (incomplete)
            end
            DB-->>MR: OK (ON CONFLICT DO NOTHING)
        end

        MR->>DB: UPSERT resolve_log (tanggal, karyawan_count)
        DB-->>MR: OK
    end

    MR-->>LA: Exit (sukses)
    Note over MR: Log ke logs/midnight_resolve.log
```

### D. Sequence Auto-Restart Daemon (Mode 24 Jam)

```mermaid
sequenceDiagram
    actor Admin
    participant UI as DashboardApp
    participant Daemon as attendance_daemon.py
    participant Main as main.py
    participant DB as PostgreSQL

    Admin->>UI: Klik 'Mulai Absensi'
    UI->>UI: CameraPickerDialog.ask()
    UI->>Daemon: subprocess.Popen(detached, env=CAMERA_INDEX)

    Daemon->>Daemon: Write pidfile (guard double-instance)

    loop while not STOP file
        Daemon->>Main: subprocess.run(main.py, env)
        Main->>Main: Load model + buka kamera
        Main->>DB: SELECT templates
        Main->>Main: Pipeline loop (YOLO, ArcFace, liveness)

        alt uptime > MAX_UPTIME_SECONDS (15 menit)
            Main-->>Daemon: exit code 2 (preemptive)
            Note over Daemon: rc=2 → restart (bukan crash)
            Daemon->>Daemon: sleep 3 detik
        else user tekan Q
            Main-->>Daemon: exit code 0 (intentional)
            Note over Daemon: rc=0 → daemon stop
        else camera read fail 10x retry
            Main-->>Daemon: exit code 2
            Daemon->>Daemon: sleep 3 detik
        else exception/crash
            Main-->>Daemon: exit code != 0/2
            Daemon->>Daemon: count crash + maybe backoff 30s
        end
    end

    Daemon->>Daemon: Delete pidfile
    Daemon-->>Admin: Daemon exit

    Note over Admin,DB: User klik 'Stop' → buat file logs/STOP
    Admin->>UI: Klik 'Stop Absensi'
    UI->>Daemon: Buat file logs/STOP
    Daemon->>Daemon: Detect STOP file di iterasi berikutnya
    Daemon->>Daemon: Exit gracefully
```

---

## 3.3.1.5 Deployment Diagram

```mermaid
flowchart TB
    subgraph DevMachine["💻 MacBook Air (Apple Silicon M2)"]
        subgraph OS["🍎 macOS"]
            subgraph PythonRuntime["🐍 Python 3.11 Runtime (venv)"]
                UIProc[ui_app.py<br/>Dashboard Process]
                DaemonProc[attendance_daemon.py<br/>Auto-Restart Wrapper]
                MainProc[main.py<br/>AttendanceSystem Process]
                MidnightProc[midnight_resolve.py<br/>Batch Job]
            end

            subgraph LaunchD["⏰ launchd"]
                LDMidnight[com.absensi.midnight<br/>Trigger 00:05 daily]
            end

            subgraph PG["🗄️ PostgreSQL 18 (brew services)"]
                DBInst[(absensi_face<br/>Database)]
            end

            subgraph FS["📁 File System"]
                ModelsDir[models/anti_spoofing/<br/>2x MiniFASNet .pth]
                YoloModel[yolo26n_face.pt<br/>5.4 MB]
                IFCache[~/.insightface/<br/>buffalo_l<br/>~330 MB]
                PhotosDir[data/photos/id/<br/>Enrollment fotos]
                LogsDir[logs/<br/>attendance.log rotating]
            end

            CamDev[📷 Webcam<br/>USB / Built-in<br/>AVFoundation]
            CV2Window[🖥️ cv2.imshow window]
        end
    end

    CamDev -->|video stream| MainProc
    UIProc -.->|spawn detached| DaemonProc
    DaemonProc -.->|spawn subprocess| MainProc
    MainProc --> CV2Window
    MainProc -->|read templates| DBInst
    MainProc -->|insert log| DBInst
    UIProc -->|CRUD| DBInst
    LDMidnight -.->|launchctl trigger| MidnightProc
    MidnightProc -->|aggregate| DBInst
    MainProc -.->|load weights| ModelsDir
    MainProc -.->|load model| YoloModel
    MainProc -.->|download once| IFCache
    UIProc -.->|copy fotos| PhotosDir
    DaemonProc -.->|append rotating| LogsDir

    subgraph External["🌐 External (Future Integration)"]
        HRISServer[Server HRIS<br/>STIE Ciputra Makassar<br/>Overlay MHL: cuti, izin, half-day]
        HRDB[(hris_kampus DB)]
    end

    MainProc -.->|HTTP POST<br/>JSON payload<br/>(stub belum aktif)| HRISServer
    HRISServer --> HRDB
```

### Deployment Detail

| Komponen | Lokasi | Tipe Deployment | Catatan |
|---|---|---|---|
| **Python 3.11 + venv** | `~/IdeaProjects/real-time-absence-skripsi/venv` | Application runtime | Isolated dependencies |
| **PostgreSQL 18** | localhost:5432 | `brew services start postgresql@18` | Auto-start saat boot |
| **YOLO Model** | `yolo26n_face.pt` | File static (5.4 MB) | Custom-trained |
| **InsightFace buffalo_l** | `~/.insightface/models/buffalo_l/` | Downloaded otomatis | ~330 MB, 5 ONNX files |
| **MiniFASNet** | `models/anti_spoofing/*.pth` | File static (~3.6 MB total) | 2 model ensemble |
| **launchd plist** | `~/Library/LaunchAgents/com.absensi.midnight.plist` | macOS scheduler | Trigger 00:05 daily |
| **Enrollment Photos** | `data/photos/{id_karyawan}/` | File system | Audit trail |
| **Logs** | `logs/attendance.log` + `attendance.log.YYYY-MM-DD` | TimedRotatingFileHandler | Keep 30 hari |
| **Database file** | `/opt/homebrew/var/postgresql@18/` | Persistent local DB | |

### Multi-Process Communication

```
UIProc ────spawn────► DaemonProc ────spawn────► MainProc
   │                       │                        │
   │                       │ writes                 │
   │                       └──► logs/STOP ◄────┐    │
   │                                            │   │
   ▼                                            │   ▼
Database ◄──────── Database ◄──────── Database (shared)

(launchd) ────trigger────► MidnightProc ────► Database
```

---

## 3.3.2 Perancangan Database

### Entity-Relationship Diagram

```mermaid
erDiagram
    KARYAWAN ||--o{ TEMPLATE_WAJAH : "memiliki (1:1)"
    KARYAWAN ||--o{ LOG_ABSENSI : "tercatat (1:N)"
    KARYAWAN ||--o{ ABSENSI_HARIAN : "diagregat (1:N)"
    LOG_ABSENSI }o--|| ABSENSI_HARIAN : "diagregat MIN/MAX"
    ABSENSI_HARIAN }o--|| RESOLVE_LOG : "tracked"

    KARYAWAN {
        SERIAL id_karyawan PK
        VARCHAR(50) nip UK "UNIQUE NOT NULL, digit only"
        VARCHAR(100) nama "NOT NULL"
        VARCHAR(100) jabatan "Dosen atau Staff Internal"
        VARCHAR(20) jenis_karyawan "internal (default)"
        BOOLEAN status_aktif "DEFAULT TRUE (soft delete flag)"
    }

    TEMPLATE_WAJAH {
        INTEGER id_karyawan FK "REFERENCES karyawan"
        BYTEA embedding "pickle dari numpy 512-dim ArcFace"
        VARCHAR(50) versi_model "yolo26n_face+buffalo_l"
    }

    LOG_ABSENSI {
        SERIAL id_log PK
        INTEGER id_karyawan FK "REFERENCES karyawan"
        TIMESTAMP timestamp "DEFAULT NOW()"
        VARCHAR jenis_event "CHECK: passage / check-in / check-out"
        FLOAT confidence_score "Cosine similarity ArcFace"
        BOOLEAN status_liveness "Stage 1 + Stage 2 lolos?"
        VARCHAR keterangan "CHECK: normal/half-day/leaving-office"
    }

    ABSENSI_HARIAN {
        SERIAL id_absensi PK
        INTEGER id_karyawan FK "REFERENCES karyawan"
        DATE tanggal "Tanggal yang di-resolve"
        TIMESTAMP check_in_time "MIN(timestamp) atau NULL"
        TIMESTAMP check_out_time "MAX(timestamp) atau NULL"
        BOOLEAN status_terlambat "MIN.time > 07:30"
        BOOLEAN status_pulang_cepat "MAX.time < 17:00"
        TEXT keterangan "normal / terlambat / pulang cepat / data tidak lengkap"
        TIMESTAMP resolved_at "Waktu batch job jalan"
    }

    RESOLVE_LOG {
        DATE tanggal PK "Tanggal yang sudah diproses"
        TIMESTAMP resolved_at "Waktu batch job"
        INTEGER karyawan_count "Jumlah karyawan diproses hari itu"
    }
```

### Spesifikasi Tabel

#### Tabel `karyawan`

Master data karyawan.

| Kolom | Tipe Data | Constraint | Keterangan |
|---|---|---|---|
| `id_karyawan` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `nip` | VARCHAR(50) | UNIQUE, NOT NULL | Nomor Induk Pegawai (digit only, validasi UI) |
| `nama` | VARCHAR(100) | NOT NULL | Nama lengkap (huruf + spasi + `. ' -`) |
| `jabatan` | VARCHAR(100) | — | "Dosen" atau "Staff Internal" |
| `jenis_karyawan` | VARCHAR(20) | DEFAULT 'internal' | Vendor sudah di-filter dari UI |
| `status_aktif` | BOOLEAN | DEFAULT TRUE | Soft delete (FALSE = nonaktif tapi histori log tetap dipertahankan) |

#### Tabel `template_wajah`

Embedding ArcFace untuk pencocokan identitas.

| Kolom | Tipe Data | Constraint | Keterangan |
|---|---|---|---|
| `id_karyawan` | INTEGER | FK → karyawan(id_karyawan) | One-to-One dengan karyawan |
| `embedding` | BYTEA | NOT NULL | `pickle.dumps(numpy_array_512_dim)` |
| `versi_model` | VARCHAR(50) | DEFAULT 'yolo26n_face+buffalo_l' | Untuk re-extraction kalau model upgrade |

**Catatan**: Embedding = rata-rata dari 3 foto enrollment (frontal, kanan, kiri):
```
avg_embedding = np.mean([emb_frontal, emb_kanan, emb_kiri], axis=0)
```

#### Tabel `log_absensi`

Setiap deteksi kamera = 1 row (raw passage).

| Kolom | Tipe Data | Constraint | Keterangan |
|---|---|---|---|
| `id_log` | SERIAL | PRIMARY KEY | |
| `id_karyawan` | INTEGER | FK → karyawan(id_karyawan) | |
| `timestamp` | TIMESTAMP | DEFAULT NOW() | Waktu deteksi tepat |
| `jenis_event` | VARCHAR | CHECK IN ('passage', 'check-in', 'check-out') | 'passage' untuk sistem baru; 'check-in'/'check-out' untuk data legacy |
| `confidence_score` | FLOAT | — | Cosine similarity ArcFace (0-1) |
| `status_liveness` | BOOLEAN | — | TRUE jika Stage 1 + Stage 2 keduanya lolos |
| `keterangan` | VARCHAR | CHECK IN ('normal', 'half-day', 'leaving-office') | Default 'normal' |

#### Tabel `absensi_harian`

Hasil resolve batch tengah malam.

| Kolom | Tipe Data | Constraint | Keterangan |
|---|---|---|---|
| `id_absensi` | SERIAL | PRIMARY KEY | |
| `id_karyawan` | INTEGER | FK → karyawan(id_karyawan) | |
| `tanggal` | DATE | NOT NULL | Tanggal yang di-resolve |
| `check_in_time` | TIMESTAMP | NULL | MIN(timestamp) dari log_absensi, atau NULL jika tidak lengkap |
| `check_out_time` | TIMESTAMP | NULL | MAX(timestamp) dari log_absensi, atau NULL |
| `status_terlambat` | BOOLEAN | NULL | TRUE jika `check_in_time.time() > WORK_START_TIME` (07:30) |
| `status_pulang_cepat` | BOOLEAN | NULL | TRUE jika `check_out_time.time() < WORK_END_TIME` (17:00) |
| `keterangan` | TEXT | — | "normal" / "terlambat" / "pulang cepat" / "terlambat, pulang cepat" / "data tidak lengkap" |
| `resolved_at` | TIMESTAMP | DEFAULT NOW() | Waktu batch job jalan |

**Constraint**: `UNIQUE(id_karyawan, tanggal)` — satu row per karyawan per hari.

#### Tabel `resolve_log`

Audit trail batch job.

| Kolom | Tipe Data | Constraint | Keterangan |
|---|---|---|---|
| `tanggal` | DATE | PRIMARY KEY | Tanggal yang sudah diproses |
| `resolved_at` | TIMESTAMP | DEFAULT NOW() | |
| `karyawan_count` | INTEGER | DEFAULT 0 | Jumlah karyawan yang diproses (untuk monitoring) |

**Fungsi**: Mencegah re-process tanggal yang sudah berhasil. Saat midnight resolver dipanggil, query:
```sql
SELECT DISTINCT DATE(timestamp) FROM log_absensi
WHERE DATE(timestamp) <= yesterday
  AND DATE(timestamp) NOT IN (SELECT tanggal FROM resolve_log);
```

### Index

Untuk performa query yang sering dijalankan:

```sql
CREATE INDEX idx_absensi_harian_tanggal
    ON absensi_harian(tanggal DESC);

CREATE INDEX idx_absensi_harian_karyawan_tanggal
    ON absensi_harian(id_karyawan, tanggal DESC);
```

### Relationship Cardinality

| Tabel A | Cardinality | Tabel B | Penjelasan |
|---|---|---|---|
| karyawan | 1 : 1 | template_wajah | Setiap karyawan punya 1 template (saat enrollment) |
| karyawan | 1 : N | log_absensi | Setiap karyawan banyak passage seiring waktu |
| karyawan | 1 : N | absensi_harian | Setiap karyawan banyak row harian (1 per tanggal) |
| log_absensi | N : 1 | absensi_harian | N lewatan di-agregat MIN/MAX jadi 1 row harian |
| absensi_harian | N : 1 | resolve_log | N row absensi_harian per tanggal di-track 1 entry resolve_log |

### Alur Data Flow

```
[Kamera Deteksi]
       │
       ▼
INSERT log_absensi (jenis_event='passage')   ← Real-time (saat orang lewat)
       │
       │  ── Hari berjalan ── orang lewat berkali-kali ──
       │
       ▼
[Midnight 00:05 — Batch Job]
       │
       │  SELECT MIN(timestamp), MAX(timestamp) per karyawan per date
       │
       ▼
INSERT absensi_harian (resolved)             ← Aggregate
       │
       ▼
UPSERT resolve_log (tanggal, karyawan_count) ← Audit trail
       │
       ▼
[Server HRIS]                                ← Future: ICT pull/push
       │
       │  Overlay MHL: cuti, izin, half-day
       │
       ▼
Status absensi FINAL (di server HRIS, bukan di sistem ini)
```

### Skema SQL (Lengkap)

```sql
-- Master karyawan
CREATE TABLE karyawan (
    id_karyawan     SERIAL PRIMARY KEY,
    nip             VARCHAR(50) UNIQUE NOT NULL,
    nama            VARCHAR(100) NOT NULL,
    jabatan         VARCHAR(100),
    jenis_karyawan  VARCHAR(20) DEFAULT 'internal',
    status_aktif    BOOLEAN DEFAULT TRUE
);

-- Template wajah (embedding ArcFace)
CREATE TABLE template_wajah (
    id_karyawan     INTEGER REFERENCES karyawan(id_karyawan),
    embedding       BYTEA NOT NULL,
    versi_model     VARCHAR(50) DEFAULT 'yolo26n_face+buffalo_l'
);

-- Log absensi (raw passage)
CREATE TABLE log_absensi (
    id_log           SERIAL PRIMARY KEY,
    id_karyawan      INTEGER REFERENCES karyawan(id_karyawan),
    timestamp        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    jenis_event      VARCHAR CHECK (jenis_event IN ('passage', 'check-in', 'check-out')),
    confidence_score FLOAT,
    status_liveness  BOOLEAN,
    keterangan       VARCHAR CHECK (keterangan IN ('normal', 'half-day', 'leaving-office'))
                     DEFAULT 'normal'
);

-- Absensi harian (resolved)
CREATE TABLE absensi_harian (
    id_absensi          SERIAL PRIMARY KEY,
    id_karyawan         INTEGER NOT NULL REFERENCES karyawan(id_karyawan),
    tanggal             DATE NOT NULL,
    check_in_time       TIMESTAMP,
    check_out_time      TIMESTAMP,
    status_terlambat    BOOLEAN,
    status_pulang_cepat BOOLEAN,
    keterangan          TEXT,
    resolved_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id_karyawan, tanggal)
);

CREATE INDEX idx_absensi_harian_tanggal
    ON absensi_harian(tanggal DESC);
CREATE INDEX idx_absensi_harian_karyawan_tanggal
    ON absensi_harian(id_karyawan, tanggal DESC);

-- Resolve log (audit trail)
CREATE TABLE resolve_log (
    tanggal         DATE PRIMARY KEY,
    resolved_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    karyawan_count  INTEGER NOT NULL DEFAULT 0
);
```

---

## Catatan untuk Skripsi

- Semua diagram pakai **Mermaid** — bisa di-render di GitHub, VS Code (extension), atau https://mermaid.live/
- Kalau dosen butuh format lain (PlantUML, ASCII, atau gambar PNG), aku bisa convert
- Untuk **screenshot diagram**: pakai mermaid.live → paste code → klik export PNG/SVG
- Untuk **deployment diagram konvensional UML**, ada perbedaan style — tapi Mermaid `flowchart` di atas sudah cukup representatif untuk skripsi S1
