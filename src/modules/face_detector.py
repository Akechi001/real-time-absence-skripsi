# src/modules/face_detector.py - Deteksi wajah menggunakan YOLO26

import cv2
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config
from ultralytics import YOLO

class FaceDetector:
    def __init__(self):
        self.model = YOLO(config.YOLO_MODEL_PATH)
        self.confidence = config.YOLO_CONFIDENCE
        self.device = config.YOLO_DEVICE
        print("✓ FaceDetector initialized")

    def detect(self, frame):
        """
        Deteksi wajah dalam frame
        Returns: list of bounding boxes [x1, y1, x2, y2, confidence]
        """
        results = self.model(
            frame,
            device=self.device,
            conf=self.confidence,
            verbose=False
        )

        faces = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])

                # Filter sudut yaw - hanya proses wajah frontal
                w = x2 - x1
                h = y2 - y1
                aspect_ratio = w / h if h > 0 else 0

                # Wajah frontal memiliki aspect ratio mendekati 1
                if 0.5 <= aspect_ratio <= 1.5:
                    faces.append([x1, y1, x2, y2, conf])

        return faces

    def draw_faces(self, frame, faces):
        """Gambar bounding box pada frame"""
        for face in faces:
            x1, y1, x2, y2, conf = face
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"{conf:.2f}", (x1, y1-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        return frame


if __name__ == "__main__":
    detector = FaceDetector()
    cap = cv2.VideoCapture(config.CAMERA_INDEX)

    print("Tekan 'q' untuk keluar")
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        faces = detector.detect(frame)
        frame = detector.draw_faces(frame, faces)

        cv2.putText(frame, f"Faces: {len(faces)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow("Face Detection - YOLO26", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()