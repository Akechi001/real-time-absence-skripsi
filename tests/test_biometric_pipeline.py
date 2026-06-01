"""
test_biometric_pipeline.py — End-to-end testing pipeline biometrik
(face detection → recognition → anti-spoofing) terhadap foto enrollment
nyata yang tersimpan di data/photos/{id_karyawan}/.

Output:
- tests/hasil_biometric_pipeline.txt — detail per-foto + summary
- tests/summary_metrics.txt — ringkasan metrik untuk skripsi BAB IV
"""

import sys
import os
import time
from datetime import datetime

import cv2
import numpy as np

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import operations as ops
from src.modules.face_detector import FaceDetector
from src.modules.face_recognizer import FaceRecognizer
from src.modules.anti_spoofing.detector import AntiSpoofingDetector


PHOTOS_DIR = "data/photos"
PHOTO_BASE_NAMES = ["foto_frontal", "foto_kanan", "foto_kiri"]
PHOTO_EXTENSIONS = [".jpeg", ".jpg", ".png"]


def find_photo(photo_dir, base_name):
    """Cari file foto dengan ekstensi apapun (.jpeg / .jpg / .png)."""
    for ext in PHOTO_EXTENSIONS:
        path = os.path.join(photo_dir, base_name + ext)
        if os.path.exists(path):
            return path
    return None


def main():
    out_lines = []

    def out(line=""):
        print(line)
        out_lines.append(line)

    out("=" * 110)
    out("BIOMETRIC PIPELINE TESTING — Sistem Absensi Wajah")
    out("STIE Ciputra Makassar — Skripsi Enrico Kevin Ariantho (0806022210012)")
    out(f"Dijalankan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    out("=" * 110)
    out()

    out("Loading models...")
    detector = FaceDetector()
    recognizer = FaceRecognizer()
    anti_spoof = AntiSpoofingDetector()
    out()

    out("Querying database...")
    all_karyawan = ops.get_all_karyawan()
    templates = ops.get_all_templates()
    out(f"  Total karyawan internal     : {len(all_karyawan)}")
    out(f"  Aktif (status_aktif=TRUE)   : "
        f"{sum(1 for k in all_karyawan if k['status_aktif'])}")
    out(f"  Punya template wajah        : "
        f"{sum(1 for k in all_karyawan if k['has_template'])}")
    out(f"  Templates loaded (active)   : {len(templates)}")
    out()

    # Yang ditest: karyawan aktif + ada folder photos
    # (mengikuti instruksi user "loop active karyawan, skip jika no photos")
    candidates = []
    skipped_no_photos = []
    for k in all_karyawan:
        if not k["status_aktif"]:
            continue
        photo_dir = os.path.join(PHOTOS_DIR, str(k["id_karyawan"]))
        if not os.path.isdir(photo_dir):
            skipped_no_photos.append(k)
            continue
        candidates.append(k)

    out(f"Karyawan aktif yang akan ditest    : {len(candidates)}")
    out(f"Karyawan aktif yang di-skip (no photos): {len(skipped_no_photos)}")
    if skipped_no_photos:
        for k in skipped_no_photos:
            out(f"  - id={k['id_karyawan']}, nama={k['nama']} (folder "
                f"data/photos/{k['id_karyawan']}/ tidak ada)")
    out()

    if not candidates:
        out("⚠ Tidak ada kandidat untuk diuji. Stop.")
        return

    # Header tabel
    headers = ["Karyawan", "Foto", "Wajah", "Confidence", "ID Benar?",
               "Anti-Spoof", "Latency(ms)"]
    widths = [28, 16, 6, 10, 10, 16, 11]

    def fmt_row(cells):
        return "| " + " | ".join(
            f"{str(c):<{w}}" for c, w in zip(cells, widths)
        ) + " |"

    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    out(sep)
    out(fmt_row(headers))
    out(sep)

    # Statistik akumulator
    stats = {
        "total_photos": 0,
        "face_detected": 0,
        "embed_extracted": 0,
        "embed_shape_valid": 0,
        "id_correct": 0,
        "id_above_threshold": 0,
        "antispoof_real": 0,
        "latencies_ms": [],
    }

    per_karyawan_summary = []

    for k in candidates:
        id_karyawan = k["id_karyawan"]
        nama = k["nama"][:27]
        photo_dir = os.path.join(PHOTOS_DIR, str(id_karyawan))

        kar_stats = {"detect": 0, "correct": 0, "real": 0, "n": 0}

        for base_name in PHOTO_BASE_NAMES:
            photo_path = find_photo(photo_dir, base_name)
            if photo_path is None:
                out(fmt_row([nama, base_name, "MISS", "-", "-", "-", "-"]))
                continue

            stats["total_photos"] += 1
            kar_stats["n"] += 1
            t_start = time.time()

            frame = cv2.imread(photo_path)
            if frame is None:
                out(fmt_row([nama, base_name, "ERR", "read fail",
                             "-", "-", "-"]))
                continue

            # --- Step a: Face detection ---
            faces = detector.detect(frame)
            face_count = len(faces)

            if face_count == 0:
                latency_ms = (time.time() - t_start) * 1000
                stats["latencies_ms"].append(latency_ms)
                out(fmt_row([nama, base_name, "0", "-", "-", "-",
                             f"{latency_ms:.0f}"]))
                continue

            stats["face_detected"] += 1
            kar_stats["detect"] += 1
            bbox = faces[0]  # ambil 1 wajah utama

            # --- Step b: Get embedding ---
            embedding = recognizer.get_embedding(frame, bbox)

            if embedding is None:
                latency_ms = (time.time() - t_start) * 1000
                stats["latencies_ms"].append(latency_ms)
                out(fmt_row([nama, base_name, face_count, "no_emb",
                             "-", "-", f"{latency_ms:.0f}"]))
                continue

            stats["embed_extracted"] += 1
            if embedding.shape == (512,):
                stats["embed_shape_valid"] += 1

            # --- Step c: Identify ---
            match = recognizer.identify(embedding, templates)
            if match is None:
                conf_str = "<thresh"
                id_str = "TIDAK"
                id_correct = False
            else:
                conf_str = f"{match['confidence']:.3f}"
                stats["id_above_threshold"] += 1
                id_correct = (match["id_karyawan"] == id_karyawan)
                if id_correct:
                    stats["id_correct"] += 1
                    kar_stats["correct"] += 1
                    id_str = "YA"
                else:
                    id_str = f"->id{match['id_karyawan']}"

            # --- Step d: Anti-spoofing ---
            is_real, spoof_conf = anti_spoof.predict(frame, bbox)
            spoof_str = f"{'REAL' if is_real else 'SPOOF'} {spoof_conf:.2f}"
            if is_real:
                stats["antispoof_real"] += 1
                kar_stats["real"] += 1

            # --- Step e: Latency ---
            latency_ms = (time.time() - t_start) * 1000
            stats["latencies_ms"].append(latency_ms)

            out(fmt_row([nama, base_name, face_count, conf_str, id_str,
                         spoof_str, f"{latency_ms:.0f}"]))

        per_karyawan_summary.append({
            "id": id_karyawan, "nama": k["nama"], **kar_stats
        })

    out(sep)
    out()

    # ─── Summary statistics ───
    total = stats["total_photos"]
    if total == 0:
        out("Tidak ada foto valid yang diuji.")
        return

    fd_pct = stats["face_detected"] / total * 100
    embed_pct = stats["embed_extracted"] / total * 100
    shape_pct = (stats["embed_shape_valid"] / stats["embed_extracted"] * 100
                 if stats["embed_extracted"] > 0 else 0)
    acc_pct_total = stats["id_correct"] / total * 100
    acc_pct_detected = (stats["id_correct"] / stats["face_detected"] * 100
                        if stats["face_detected"] > 0 else 0)
    spoof_pct = (stats["antispoof_real"] / stats["face_detected"] * 100
                 if stats["face_detected"] > 0 else 0)

    latencies = stats["latencies_ms"]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    min_lat = min(latencies) if latencies else 0
    max_lat = max(latencies) if latencies else 0

    summary_lines = [
        "=" * 110,
        "RINGKASAN STATISTIK",
        "=" * 110,
        "",
        f"Total foto diuji                            : {total}",
        f"Face Detection Rate                          : "
        f"{stats['face_detected']}/{total} = {fd_pct:.1f}%",
        f"Embedding Extraction Success                 : "
        f"{stats['embed_extracted']}/{total} = {embed_pct:.1f}%",
        f"Embedding Shape Valid (512-dim)              : "
        f"{stats['embed_shape_valid']}/{stats['embed_extracted']} "
        f"= {shape_pct:.1f}%",
        f"Recognition Accuracy (vs total foto)         : "
        f"{stats['id_correct']}/{total} = {acc_pct_total:.1f}%",
        f"Recognition Accuracy (vs wajah ter-detect)   : "
        f"{stats['id_correct']}/{stats['face_detected']} = {acc_pct_detected:.1f}%",
        f"Anti-Spoof Pass Rate (genuine photos)        : "
        f"{stats['antispoof_real']}/{stats['face_detected']} = {spoof_pct:.1f}%",
        f"Average Latency per foto                     : {avg_lat:.0f} ms",
        f"Min / Max Latency                            : "
        f"{min_lat:.0f} / {max_lat:.0f} ms",
        "",
        "Per-Karyawan:",
    ]

    for ks in per_karyawan_summary:
        if ks["n"] > 0:
            summary_lines.append(
                f"  id={ks['id']:>3} | {ks['nama'][:30]:<30} | "
                f"detect={ks['detect']}/{ks['n']}, "
                f"correct={ks['correct']}/{ks['n']}, "
                f"real={ks['real']}/{ks['n']}"
            )

    for l in summary_lines:
        out(l)

    out()
    out("=" * 110)
    out("KETERANGAN FIELD:")
    out("  - 'Wajah'      : jumlah wajah ter-detect (FaceDetector YOLO26)")
    out("  - 'Confidence' : cosine similarity ArcFace dengan template terbaik "
        f"(threshold {0.4})")
    out("  - 'ID Benar?'  : YA jika id_karyawan match dengan foto yang diuji")
    out("  - 'Anti-Spoof' : REAL/SPOOF + confidence (ensemble MiniFASNet V2 + V1SE)")
    out("  - 'Latency'    : total processing time per foto (detect + embed + "
        "identify + antispoof)")
    out("=" * 110)

    out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "hasil_biometric_pipeline.txt")
    with open(out_file, "w") as f:
        f.write("\n".join(out_lines))
    print(f"\n✓ Output saved: {out_file}")

    # ─── File terpisah untuk metrik ringkas (langsung copy ke skripsi) ───
    metrics_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "summary_metrics.txt")
    with open(metrics_file, "w") as f:
        f.write("METRIK PENGUJIAN — Sistem Absensi Wajah\n")
        f.write("STIE Ciputra Makassar — Skripsi Enrico Kevin Ariantho\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Tanggal pengujian       : "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Jumlah karyawan diuji   : {len(candidates)}\n")
        f.write(f"Total foto diuji        : {total}\n\n")
        f.write("BIOMETRIC PIPELINE\n")
        f.write("-" * 60 + "\n")
        f.write(f"Face Detection Rate           : {fd_pct:.1f}% "
                f"({stats['face_detected']}/{total})\n")
        f.write(f"Recognition Accuracy          : {acc_pct_detected:.1f}% "
                f"({stats['id_correct']}/{stats['face_detected']} dari wajah "
                f"ter-detect)\n")
        f.write(f"Anti-Spoofing Pass (genuine)  : {spoof_pct:.1f}% "
                f"({stats['antispoof_real']}/{stats['face_detected']})\n\n")
        f.write("PERFORMA\n")
        f.write("-" * 60 + "\n")
        f.write(f"Latency rata-rata             : {avg_lat:.0f} ms\n")
        f.write(f"Latency minimum               : {min_lat:.0f} ms\n")
        f.write(f"Latency maximum               : {max_lat:.0f} ms\n")
        f.write(f"Throughput estimasi (1/avg)   : "
                f"{(1000/avg_lat if avg_lat>0 else 0):.1f} foto/detik\n")

    print(f"✓ Metrics saved: {metrics_file}")


if __name__ == "__main__":
    main()
