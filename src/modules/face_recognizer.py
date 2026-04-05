# src/modules/face_recognizer.py - Face recognition menggunakan InsightFace ArcFace

import numpy as np
import insightface
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config

class FaceRecognizer:
    def __init__(self):
        self.app = insightface.app.FaceAnalysis(name=config.INSIGHTFACE_MODEL)
        self.app.prepare(ctx_id=-1)  # CPU
        self.threshold = config.FACE_SIMILARITY_THRESHOLD
        print("✓ FaceRecognizer initialized")


    def get_embedding(self, frame, bbox):
        """
        Ekstrak embedding wajah dari frame penuh
        menggunakan bbox sebagai referensi posisi
        """
        x1, y1, x2, y2 = bbox[:4]

        # Berikan frame penuh ke InsightFace
        faces = self.app.get(frame)

        if not faces:
            print("InsightFace tidak mendeteksi wajah")
            return None

        # Cari wajah yang paling overlap dengan bbox YOLO
        best_face = None
        best_overlap = 0

        for face in faces:
            fx1, fy1, fx2, fy2 = map(int, face.bbox)

            # Hitung overlap
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
            print("Tidak ada wajah yang overlap dengan bbox YOLO")
            return None

        return best_face.embedding

    def cosine_similarity(self, emb1, emb2):
        """Hitung cosine similarity antara dua embedding"""
        emb1 = emb1 / np.linalg.norm(emb1)
        emb2 = emb2 / np.linalg.norm(emb2)
        return float(np.dot(emb1, emb2))

    def identify(self, embedding, templates):
        """
        Cocokkan embedding dengan template database
        templates: list of dict {id_karyawan, nama, embedding}
        Returns: (id_karyawan, nama, confidence) atau None
        """
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