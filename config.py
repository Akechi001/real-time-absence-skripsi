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
EAR_THRESHOLD = 0.25
EAR_CONSEC_FRAMES = 1      # dari 2
HEAD_MOVE_THRESHOLD = 3    # dari 10
LIVENESS_WINDOW = 8        # dari 30

# Kamera
CAMERA_INDEX = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FPS_SAMPLING = 10

# Cooldown absensi (detik)
COOLDOWN_SECONDS = 60

# Path
PHOTOS_DIR = "data/photos"