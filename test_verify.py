# Test YOLO26
from ultralytics import YOLO
model = YOLO("yolo26n.pt")
print("✓ YOLO26 OK")

# Test InsightFace
import insightface
app = insightface.app.FaceAnalysis()
app.prepare(ctx_id=-1)
print("✓ InsightFace OK")

# Test OpenCV
import cv2
print(f"✓ OpenCV OK - version {cv2.__version__}")

# Test psycopg2
import psycopg2
print("✓ psycopg2 OK")

# Test filterpy
from filterpy.kalman import KalmanFilter
print("✓ filterpy OK")

print("\nSemua library siap!")