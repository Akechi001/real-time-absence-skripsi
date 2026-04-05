# src/modules/liveness.py - Liveness detection menggunakan EAR dan head movement

import cv2
import numpy as np
from collections import deque
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import config

class LivenessDetector:
    def __init__(self):
        self.ear_threshold = config.EAR_THRESHOLD
        self.ear_consec_frames = config.EAR_CONSEC_FRAMES
        self.liveness_window = config.LIVENESS_WINDOW
        self.head_move_threshold = config.HEAD_MOVE_THRESHOLD

        # State per track_id
        self.states = {}
        print("✓ LivenessDetector initialized")

    def _get_state(self, track_id):
        """Ambil atau buat state untuk track_id"""
        if track_id not in self.states:
            self.states[track_id] = {
                'ear_counter': 0,
                'blink_count': 0,
                'head_positions': deque(maxlen=self.liveness_window),
                'is_live': False
            }
        return self.states[track_id]

    def calculate_ear(self, eye_landmarks):
        """Hitung Eye Aspect Ratio (EAR)"""
        # Jarak vertikal
        A = np.linalg.norm(eye_landmarks[1] - eye_landmarks[5])
        B = np.linalg.norm(eye_landmarks[2] - eye_landmarks[4])
        # Jarak horizontal
        C = np.linalg.norm(eye_landmarks[0] - eye_landmarks[3])
        ear = (A + B) / (2.0 * C)
        return ear

    def check_liveness(self, track_id, face_obj):
        """
        Cek liveness dari face object InsightFace
        Returns: (is_live, reason)
        """
        state = self._get_state(track_id)

        if face_obj is None:
            return False, "no_face"

        # Ambil landmark dari InsightFace
        landmarks = face_obj.landmark_2d_106
        if landmarks is None:
            return False, "no_landmark"

        # Landmark mata dari InsightFace buffalo_l
        # Mata kiri: index 33-38, Mata kanan: index 87-92
        try:
            left_eye = landmarks[33:39]
            right_eye = landmarks[87:93]

            left_ear = self.calculate_ear(left_eye)
            right_ear = self.calculate_ear(right_eye)
            ear = (left_ear + right_ear) / 2.0

            # Deteksi kedipan
            if ear < self.ear_threshold:
                state['ear_counter'] += 1
            else:
                if state['ear_counter'] >= self.ear_consec_frames:
                    state['blink_count'] += 1
                state['ear_counter'] = 0

            # Deteksi pergerakan kepala
            nose_tip = landmarks[86]
            state['head_positions'].append(nose_tip)

            head_moved = False
            if len(state['head_positions']) >= 10:
                positions = np.array(state['head_positions'])
                movement = np.max(positions, axis=0) - np.min(positions, axis=0)
                head_moved = np.any(movement > self.head_move_threshold)

            # Liveness = blink terdeteksi ATAU kepala bergerak
            if state['blink_count'] >= 1 or head_moved:
                state['is_live'] = True

            return state['is_live'], "ok"

        except Exception as e:
            return False, str(e)

    def reset_state(self, track_id):
        """Reset state untuk track_id tertentu"""
        if track_id in self.states:
            del self.states[track_id]


if __name__ == "__main__":
    detector = LivenessDetector()
    print("✓ LivenessDetector siap digunakan")