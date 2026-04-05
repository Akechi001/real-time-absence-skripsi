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
EAR_THRESHOLD = 0.25        # threshold kedipan mata
EAR_CONSEC_FRAMES = 2       # frame berturut-turut untuk deteksi kedip
HEAD_MOVE_THRESHOLD = 10    # threshold pergerakan kepala (pixel)
LIVENESS_WINDOW = 30        # jumlah frame untuk verifikasi liveness

# Kamera
CAMERA_INDEX = 0            # index kamera (0 = webcam default)
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FPS_SAMPLING = 10           # frame per detik yang diproses

# Cooldown absensi (detik)
COOLDOWN_SECONDS = 60

# Path
PHOTOS_DIR = "data/photos"