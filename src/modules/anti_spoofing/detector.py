# src/modules/anti_spoofing/detector.py - Anti-spoofing detector

import os
import sys
import cv2
import numpy as np
import torch
import torch.nn.functional as F

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from src.modules.anti_spoofing.MiniFASNet import (
    MiniFASNetV1, MiniFASNetV2, MiniFASNetV1SE, MiniFASNetV2SE
)
import config


# Mapping nama model ke class
MODEL_MAPPING = {
    'MiniFASNetV1': MiniFASNetV1,
    'MiniFASNetV2': MiniFASNetV2,
    'MiniFASNetV1SE': MiniFASNetV1SE,
    'MiniFASNetV2SE': MiniFASNetV2SE,
}


def parse_model_name(model_name):
    """Parse nama file model untuk dapat info: scale, height, width, type"""
    info = model_name.split('_')[0:-1]
    h_input, w_input = info[-1].split('x')
    model_type = model_name.split('.pth')[0].split('_')[-1]

    if info[0] == "org":
        scale = None
    else:
        scale = float(info[0])

    return int(h_input), int(w_input), model_type, scale


def get_kernel(height, width):
    """Hitung kernel size untuk conv6 berdasarkan input size"""
    kernel_size = ((height + 15) // 16, (width + 15) // 16)
    return kernel_size


class AntiSpoofingDetector:
    def __init__(self, model_dir="models/anti_spoofing"):
        """Load semua model anti-spoofing dari folder"""
        self.device = torch.device("cpu")
        self.models = []

        for model_name in os.listdir(model_dir):
            if not model_name.endswith('.pth'):
                continue

            h, w, model_type, scale = parse_model_name(model_name)
            kernel_size = get_kernel(h, w)

            # Buat model instance
            model_class = MODEL_MAPPING.get(model_type)
            if model_class is None:
                print(f"⚠️ Model type tidak dikenal: {model_type}")
                continue

            model = model_class(conv6_kernel=kernel_size).to(self.device)

            # Load weights
            model_path = os.path.join(model_dir, model_name)
            state_dict = torch.load(model_path, map_location=self.device, weights_only=True)

            # Remap state dict untuk handle perbedaan naming SE module
            new_state_dict = {}
            for key, value in state_dict.items():
                new_key = key.replace('module.', '')

                # Map naming SE module: se_fc1/se_bn1 → se_module.fc1/se_module.bn1
                if 'se_fc1' in new_key:
                    new_key = new_key.replace('se_fc1', 'se_module.fc1')
                elif 'se_bn1' in new_key:
                    new_key = new_key.replace('se_bn1', 'se_module.bn1')
                elif 'se_fc2' in new_key:
                    new_key = new_key.replace('se_fc2', 'se_module.fc2')
                elif 'se_bn2' in new_key:
                    new_key = new_key.replace('se_bn2', 'se_module.bn2')

                new_state_dict[new_key] = value

            # Load dengan strict=False untuk skip num_batches_tracked
            model.load_state_dict(new_state_dict, strict=False)
            model.eval()

            self.models.append({
                'name': model_name,
                'model': model,
                'h': h,
                'w': w,
                'scale': scale,
            })
            print(f"✓ Loaded {model_name}")

        print(f"✓ AntiSpoofingDetector initialized with {len(self.models)} models")

    def crop_face(self, frame, bbox, scale=2.7):
        """Crop wajah dengan padding sesuai scale dari Silent-Face"""
        x1, y1, x2, y2 = [int(v) for v in bbox[:4]]

        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        w = x2 - x1
        h = y2 - y1

        new_w = w * scale
        new_h = h * scale

        new_x1 = int(max(0, cx - new_w / 2))
        new_y1 = int(max(0, cy - new_h / 2))
        new_x2 = int(min(frame.shape[1], cx + new_w / 2))
        new_y2 = int(min(frame.shape[0], cy + new_h / 2))

        crop = frame[new_y1:new_y2, new_x1:new_x2]
        return crop

    def predict(self, frame, bbox):
        """
        Prediksi apakah wajah real atau spoof
        Returns: (is_real, confidence)
        """
        if frame is None or len(self.models) == 0:
            return False, 0.0

        prediction_sum = np.zeros((1, 3))

        for m in self.models:
            scale = m['scale'] if m['scale'] is not None else 2.7
            face_crop = self.crop_face(frame, bbox, scale=scale)

            if face_crop.size == 0:
                continue

            # Resize ke input size model
            face_resized = cv2.resize(face_crop, (m['w'], m['h']))

            # Convert ke tensor
            img = face_resized.astype(np.float32)
            img = img.transpose((2, 0, 1))  # HWC -> CHW
            img = np.expand_dims(img, axis=0)
            img_tensor = torch.from_numpy(img).to(self.device)

            with torch.no_grad():
                output = m['model'].forward(img_tensor)
                output = F.softmax(output, dim=1).cpu().numpy()

            prediction_sum += output

        avg_prediction = prediction_sum / len(self.models)
        label = int(np.argmax(avg_prediction))
        confidence = float(avg_prediction[0][label])

        # Label 1 = real face, label 0 dan 2 = spoof
        is_real = (label == 1)

        return is_real, confidence


if __name__ == "__main__":
    detector = AntiSpoofingDetector()
    print("✓ AntiSpoofingDetector siap digunakan")