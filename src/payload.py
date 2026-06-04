# src/payload.py - Payload builder dan sender

import json
from datetime import datetime


def build_payload(id_karyawan, nama, jenis_event, confidence, status_liveness):
    """
    Bangun struktur payload JSON yang menyerupai kebutuhan pencatatan
    kehadiran, disiapkan untuk simulasi integrasi ke backend absensi kampus.

    jenis_event = 'passage' (lewatan mentah).
    Keputusan check-in / check-out / terlambat / pulang cepat dilakukan
    batch tengah malam berdasarkan MIN/MAX timestamp per tanggal.
    """
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
    """
    Catat (log) payload yang telah dibentuk sebagai simulasi integrasi.

    Sesuai ruang lingkup penelitian, sistem TIDAK melakukan pengiriman HTTP
    nyata ke backend absensi kampus — payload hanya disiapkan & dicatat.
    Blok requests.post di bawah disediakan sebagai jalur integrasi nyata
    bila endpoint tersedia (di luar lingkup penelitian).
    """
    print(f"\n[PAYLOAD] {json.dumps(payload, indent=2)}")

    # Jalur integrasi nyata (di luar lingkup) — aktifkan bila endpoint tersedia:
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