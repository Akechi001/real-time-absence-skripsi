# src/modules/face_recognizer.py - Face recognition menggunakan InsightFace ArcFace

import numpy as np
import insightface
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config


class FaceRecognizer:
    def __init__(self):
        # Hanya load model yang dibutuhkan untuk percepat inference
        # detection: untuk deteksi wajah
        # recognition: untuk embedding ArcFace
        # landmark_2d_106: untuk liveness EAR + head movement
        self.app = insightface.app.FaceAnalysis(
            name=config.INSIGHTFACE_MODEL,
            allowed_modules=['detection', 'recognition', 'landmark_2d_106']
        )
        # det_size lebih kecil untuk speed up (default 640x640)
        self.app.prepare(ctx_id=-1, det_size=(320, 320))
        self.threshold = config.FACE_SIMILARITY_THRESHOLD
        print("✓ FaceRecognizer initialized")

    def get_embedding(self, frame, bbox, faces_insightface=None):
        """
        Ekstrak embedding wajah dari frame
        Jika faces_insightface diberikan, pakai itu (hindari double call)
        """
        x1, y1, x2, y2 = bbox[:4]

        # Pakai faces_insightface yang sudah ada, atau panggil app.get
        if faces_insightface is None:
            faces = self.app.get(frame)
        else:
            faces = faces_insightface

        if not faces:
            return None

        # Cari wajah yang paling overlap dengan bbox YOLO
        best_face = None
        best_overlap = 0

        for face in faces:
            fx1, fy1, fx2, fy2 = map(int, face.bbox)
            ox1 = max(x1, fx1)
            oy1 = max(y1, fy1)
            ox2 = min(x2, fx2)
            oy2 = min(y2, fy2)

            if ox2 > ox1 and oy2 > oy1:
                overlap = (ox2 - ox1) * (oy2 - oy1)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_face = face

        if best_face is None:
            return None

        return best_face.embedding

    def cosine_similarity(self, emb1, emb2):
        emb1 = emb1 / np.linalg.norm(emb1)
        emb2 = emb2 / np.linalg.norm(emb2)
        return float(np.dot(emb1, emb2))

    def identify(self, embedding, templates):
        if embedding is None or not templates:
            return None

        best_match = None
        best_score = -1

        for template in templates:
            score = self.cosine_similarity(embedding, template['embedding'])
            if score > best_score:
                best_score = score
                best_match = template

        if best_score >= self.threshold:
            return {
                'id_karyawan': best_match['id_karyawan'],
                'nama': best_match['nama'],
                'confidence': best_score
            }

        return None


if __name__ == "__main__":
    recognizer = FaceRecognizer()
    print("✓ FaceRecognizer siap digunakan")