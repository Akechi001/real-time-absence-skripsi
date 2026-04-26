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

# Kamera
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