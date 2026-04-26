# src/modules/liveness.py - Liveness detection menggunakan EAR dan head movement

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
        self.calibration_frames = 10  # frame untuk hitung baseline
        self.blink_drop_ratio = 0.75  # blink jika EAR turun ke 75% dari baseline
        self.states = {}
        print("✓ LivenessDetector initialized")

    def _get_state(self, track_id):
        if track_id not in self.states:
            self.states[track_id] = {
                'ear_counter': 0,
                'blink_count': 0,
                'head_positions': deque(maxlen=self.liveness_window),
                'is_live': False,
                'ear_history': deque(maxlen=self.calibration_frames),
                'baseline_ear': None,
            }
        return self.states[track_id]

    def reset_state(self, track_id):
        if track_id in self.states:
            del self.states[track_id]

    def calculate_ear_bbox(self, eye_landmarks):
        """Hitung EAR dengan pendekatan bounding box (height/width)"""
        if len(eye_landmarks) == 0:
            return 0
        xs = eye_landmarks[:, 0]
        ys = eye_landmarks[:, 1]
        width = np.max(xs) - np.min(xs)
        height = np.max(ys) - np.min(ys)
        if width == 0:
            return 0
        return height / width

    def check_liveness(self, track_id, face_obj):
        state = self._get_state(track_id)

        if face_obj is None:
            return False, "no_face"

        landmarks = face_obj.landmark_2d_106
        if landmarks is None:
            return False, "no_landmark"

        try:
            # Pakai semua titik di area mata
            right_eye_indices = [33, 35, 36, 37, 38, 39, 40, 41, 42]
            left_eye_indices = [87, 88, 89, 90, 91, 93, 94, 95, 96]

            right_eye = landmarks[right_eye_indices]
            left_eye = landmarks[left_eye_indices]

            right_ear = self.calculate_ear_bbox(right_eye)
            left_ear = self.calculate_ear_bbox(left_eye)
            ear = (left_ear + right_ear) / 2.0

            # ── Adaptive threshold: hitung baseline EAR ──
            state['ear_history'].append(ear)

            if state['baseline_ear'] is None and len(state['ear_history']) >= self.calibration_frames:
                # Pakai median sebagai baseline (lebih robust dari mean)
                state['baseline_ear'] = float(np.median(state['ear_history']))
                print(f"✓ EAR Baseline calibrated: {state['baseline_ear']:.3f}")

            # Threshold dinamis: 75% dari baseline
            if state['baseline_ear'] is not None:
                dynamic_threshold = state['baseline_ear'] * self.blink_drop_ratio
            else:
                dynamic_threshold = self.ear_threshold  # fallback

            # Deteksi kedipan dengan threshold dinamis
            if ear < dynamic_threshold:
                state['ear_counter'] += 1
            else:
                if state['ear_counter'] >= self.ear_consec_frames:
                    state['blink_count'] += 1
                state['ear_counter'] = 0

            # Deteksi pergerakan kepala (pakai nose tip - landmark 86)
            nose_tip = landmarks[86]
            state['head_positions'].append(nose_tip)

            head_moved = False
            if len(state['head_positions']) >= 5:
                positions = np.array(state['head_positions'])
                movement = np.max(positions, axis=0) - np.min(positions, axis=0)
                head_moved = np.any(movement > self.head_move_threshold)

            baseline_str = f"{state['baseline_ear']:.3f}" if state['baseline_ear'] else "calibrating"
            print(
                f"DEBUG EAR: avg={ear:.3f} baseline={baseline_str} "
                f"threshold={dynamic_threshold:.3f} blink={state['blink_count']} "
                f"head_moved={head_moved} positions={len(state['head_positions'])}"
            )

            if state['blink_count'] >= 1 or head_moved:
                state['is_live'] = True

            return state['is_live'], "ok"

        except Exception as e:
            print(f"DEBUG Exception: {e}")
            return False, str(e)


if __name__ == "__main__":
    detector = LivenessDetector()
    print("✓ LivenessDetector siap digunakan")