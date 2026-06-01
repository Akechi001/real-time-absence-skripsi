# config.py - Konfigurasi Global Sistem Absensi

from dotenv import load_dotenv
import os

load_dotenv()

# Database
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("DB_NAME", "absensi_face"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "")
}

# YOLO26
YOLO_MODEL_PATH = "yolo26n_face.pt"
YOLO_CONFIDENCE = 0.5
YOLO_DEVICE = "cpu"

# InsightFace
INSIGHTFACE_MODEL = "buffalo_l"
FACE_SIMILARITY_THRESHOLD = 0.4  # threshold cosine similarity

# Liveness
EAR_THRESHOLD = 0.20
EAR_CONSEC_FRAMES = 1
HEAD_MOVE_THRESHOLD = 15
LIVENESS_WINDOW = 8

# Kamera (cuma 1 — buat attendance saja, enrollment via upload foto)
CAMERA_INDEX = 0

FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FPS_SAMPLING = 20

# Cooldown absensi (detik)
COOLDOWN_SECONDS = 60

# Path
PHOTOS_DIR = "data/photos"

# Anti-spoofing CNN
ANTI_SPOOFING_THRESHOLD = 0.5

# Resolve absensi harian (jam tengah malam)
WORK_START_TIME = "07:30"        # check-in lewat dari jam ini = terlambat
WORK_END_TIME = "16:30"          # check-out sebelum jam ini = pulang cepat
RESOLVE_ONLY_INTERNAL = True     # vendor di-skip dari absensi_harian (multi-shift)

# Pre-emptive restart untuk mitigasi memory leak.
#
# Sumber leak: kombinasi ONNX Runtime + PyTorch + OpenCV internal
# buffers/allocators di CPU backend yang tidak shrink. Sudah dicoba
# fix via onnx_patch.py (disable arena pool), torch.set_num_threads(1),
# dan gc.collect() periodic — TIDAK CUKUP. Swap tetap naik ~1.5 GB/menit
# di MacBook Air.
#
# Pragmatic mitigation: restart subprocess attendance tiap 15 menit
# supaya swap tidak menggunung sampai system thrashing.
#
# Downtime per restart: ~10 detik (load YOLO + InsightFace + MiniFASNet).
# Total downtime/hari: 96 × 10s = 16 menit (~1.1% uptime).
MAX_UPTIME_SECONDS = 900         # 15 menit (set 0 untuk disable)