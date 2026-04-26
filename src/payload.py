# src/payload.py - Payload builder dan sender

import json
from datetime import datetime


def build_payload(id_karyawan, nama, jenis_event, confidence, status_liveness):
    """Bangun payload JSON untuk simulasi integrasi backend"""
    return {
        "id_karyawan": id_karyawan,
        "nama": nama,
        "timestamp": datetime.now().isoformat(),
        "jenis_event": jenis_event,
        "confidence_score": round(confidence, 4),
        "status_liveness": status_liveness,
        "keterangan": "normal",
        "source": "face_recognition_system",
        "versi_model": "yolo26n_face+buffalo_l"
    }


def send_payload(payload):
    """Kirim payload ke endpoint backend (simulasi)"""
    print(f"\n[PAYLOAD] {json.dumps(payload, indent=2)}")

    # Uncomment kalau ada endpoint nyata:
    # import requests
    # try:
    #     response = requests.post(
    #         "http://backend-kampus/api/absensi",
    #         json=payload,
    #         timeout=5
    #     )
    #     print(f"[PAYLOAD] Response: {response.status_code}")
    # except Exception as e:
    #     print(f"[PAYLOAD] Error: {e}")