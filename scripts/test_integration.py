"""
test_integration.py — Integration testing antar-modul (Bab V).

Memverifikasi TITIK SAMBUNG antar modul (aliran data antar tahap), BUKAN
keluaran akhir fungsional. Mengimpor modul sistem yang ada (tidak mengubah
logika apa pun) dan memanggil pipeline nyata.

Skenario:
  IT-01  YOLO -> InsightFace : bbox YOLO dipetakan ke Face InsightFace via overlap
  IT-02  InsightFace -> Matching : embedding diteruskan ke cosine vs template DB
  IT-03  Matching -> Cooldown : setelah dikenali, cooldown dicek sebelum liveness
  IT-04  Liveness -> DB : hanya yang lolos liveness 2 tahap yang masuk log_absensi
  IT-05  DB -> Payload : struktur payload JSON benar (dibentuk & di-log, BUKAN HTTP)
  IT-06  Log -> Resolver : agregasi log -> absensi_harian (check-in/out benar)

Pakai DB tes:
    DB_NAME=absensi_test python scripts/test_integration.py

Strategi cleanup mengikuti test_functional.py: marker TEST_NIP_PREFIX +
tanggal sintetis, dibersihkan SEBELUM dan SESUDAH run (idempoten).

IT-01..IT-04 butuh satu citra wajah (fixture). Default: ambil dari
data/probes/<id>/*.jpg (kalau ada), atau data/photos/*/foto_frontal.jpeg,
atau override via --image PATH.
"""

import sys
import os
import glob
import time
import argparse
from datetime import datetime, date

import numpy as np
import cv2

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src.database.db import get_connection
from src.database import operations as ops
from src.payload import build_payload, send_payload

TEST_NIP_PREFIX = "TEST_IT_"
TEST_FUTURE_DATE = date(2099, 2, 20)

results = []


def log(status, tc, desc, detail=""):
    line = f"[{status}] {tc}: {desc}"
    if detail:
        line += f"\n        → {detail}"
    print(line)
    results.append(line)


def passed(tc, desc, detail=""):
    log("PASS", tc, desc, detail)


def failed(tc, desc, detail=""):
    log("FAIL", tc, desc, detail)


def skipped(tc, desc, detail=""):
    log("SKIP", tc, desc, detail)


def cleanup_test_data():
    conn = get_connection()
    if not conn:
        print("⚠ Cleanup gagal — tidak bisa connect DB")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM log_absensi WHERE id_karyawan IN "
            "(SELECT id_karyawan FROM karyawan WHERE nip LIKE %s)",
            (f"{TEST_NIP_PREFIX}%",))
        cur.execute("DELETE FROM absensi_harian WHERE tanggal = %s", (TEST_FUTURE_DATE,))
        cur.execute("DELETE FROM resolve_log WHERE tanggal = %s", (TEST_FUTURE_DATE,))
        cur.execute(
            "DELETE FROM template_wajah WHERE id_karyawan IN "
            "(SELECT id_karyawan FROM karyawan WHERE nip LIKE %s)",
            (f"{TEST_NIP_PREFIX}%",))
        cur.execute("DELETE FROM karyawan WHERE nip LIKE %s", (f"{TEST_NIP_PREFIX}%",))
        conn.commit()
    finally:
        conn.close()


def find_fixture(explicit=None):
    if explicit:
        return explicit if os.path.exists(explicit) else None
    for pat in ("data/probes/*/*/*.jpg", "data/probes/*/*/*.jpeg",
                "data/probes/*/*.jpg", "data/probes/*/*.jpeg",
                "data/photos/*/foto_frontal.jpeg", "data/photos/*/*.jpg"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[0]
    return None


def _overlap(b, fbbox):
    fx1, fy1, fx2, fy2 = fbbox
    ox1, oy1 = max(b[0], fx1), max(b[1], fy1)
    ox2, oy2 = min(b[2], fx2), min(b[3], fy2)
    return (ox2 - ox1) * (oy2 - oy1) if (ox2 > ox1 and oy2 > oy1) else 0.0


def count_logs(id_karyawan):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM log_absensi WHERE id_karyawan=%s", (id_karyawan,))
    n = cur.fetchone()[0]
    conn.close()
    return n


# ──────────────────────────────────────────────────────────────────────────


def run_image_tests(system, frame):
    """IT-01..IT-04 (butuh fixture). Mengembalikan id_karyawan tes (atau None)."""
    detector = system.detector
    recognizer = system.recognizer

    # Ekstraksi awal — persis jalur process_frame
    yolo_faces = detector.detect(frame)
    faces_if = recognizer.app.get(frame)

    if not yolo_faces:
        skipped("IT-01", "YOLO → InsightFace", "YOLO tidak mendeteksi wajah di fixture")
        skipped("IT-02", "InsightFace → Matching", "tergantung IT-01 (tak ada wajah)")
        skipped("IT-03", "Matching → Cooldown", "tergantung wajah ter-enroll")
        skipped("IT-04", "Liveness → DB", "tergantung wajah ter-enroll")
        return None
    if not faces_if:
        skipped("IT-01", "YOLO → InsightFace", "InsightFace tidak mendeteksi wajah di fixture")
        return None

    bbox = max(yolo_faces, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))

    # ── IT-01: bbox YOLO dipetakan ke Face InsightFace via overlap ──
    emb_get = recognizer.get_embedding(frame, [int(x) for x in bbox[:4]], faces_if)
    # cari face InsightFace dengan overlap terbesar (replikasi logika get_embedding)
    overlaps = [(_overlap(bbox, f.bbox), f) for f in faces_if]
    best_ov, best_face = max(overlaps, key=lambda x: x[0])
    if emb_get is None:
        failed("IT-01", "YOLO → InsightFace", "get_embedding mengembalikan None")
    elif best_ov <= 0:
        failed("IT-01", "YOLO → InsightFace",
               "tidak ada overlap antara bbox YOLO & wajah InsightFace")
    else:
        sim_map = recognizer.cosine_similarity(emb_get, best_face.embedding)
        if sim_map > 0.99:
            passed("IT-01", "bbox YOLO dipetakan ke Face InsightFace yang overlap",
                   f"YOLO={len(yolo_faces)} face, InsightFace={len(faces_if)} face, "
                   f"overlap_area={best_ov:.0f}px, embedding(get)==embedding(overlap) "
                   f"cosine={sim_map:.4f} (≈1 → wajah yang BENAR dipilih, bukan acak)")
        else:
            failed("IT-01", "YOLO → InsightFace",
                   f"embedding get_embedding ≠ face overlap (cosine={sim_map:.4f})")

    # ── IT-02: embedding → cosine vs template DB (dua cabang) ──
    if emb_get is None:
        skipped("IT-02", "InsightFace → Matching", "embedding None dari IT-01")
        return None

    nip = f"{TEST_NIP_PREFIX}IT02"
    id_test = ops.save_karyawan_with_template(nip, "IT Subject", "Dosen", "internal", emb_get)
    if id_test is None:
        failed("IT-02", "InsightFace → Matching", "setup enroll gagal")
        return None
    system.reload_templates()  # muat template tes ke shared_templates

    templates = ops.get_all_templates()
    match = recognizer.identify(emb_get, templates)            # cabang dikenali
    rng = np.random.default_rng(7)
    fake_tpl = [{'id_karyawan': -1, 'nama': 'x',
                 'embedding': rng.random(512, dtype=np.float32)}]
    reject = recognizer.identify(emb_get, fake_tpl)            # cabang tak dikenali

    if match and match['id_karyawan'] == id_test and reject is None:
        passed("IT-02", "embedding diteruskan ke cosine → identitas benar / tidak dikenali",
               f"match: id={match['id_karyawan']} conf={match['confidence']:.3f} (benar); "
               f"vs template asing → None (tidak dikenali)")
    else:
        failed("IT-02", "InsightFace → Matching",
               f"match={match}, reject={reject} (expected match id={id_test}, reject=None)")

    # ── IT-03: setelah dikenali, cooldown dicek SEBELUM liveness ──
    # Aktifkan window cooldown khusus uji ini (config ambient bisa 0 saat sesi
    # pengujian latensi). is_cooldown membaca config.COOLDOWN_SECONDS saat call.
    orig_cd = config.COOLDOWN_SECONDS
    config.COOLDOWN_SECONDS = 60
    try:
        system.cooldown[id_test] = time.time()   # simulasi: subjek baru saja lewat
        res = system.process_frame(frame, yolo_faces)
    finally:
        config.COOLDOWN_SECONDS = orig_cd
    st = res[0]['status'] if res else None
    if st == 'cooldown':
        passed("IT-03", "match → cooldown dicek sebelum liveness (di-skip saat cooldown)",
               f"process_frame → status='cooldown' (wajah dikenali lalu di-skip di "
               f"gerbang cooldown, tidak lanjut ke liveness)")
    else:
        failed("IT-03", "Matching → Cooldown",
               f"status='{st}' (expected 'cooldown')")

    # ── IT-04: hanya yang lolos liveness 2 tahap yang masuk log_absensi ──
    system.cooldown.clear()
    system.liveness.reset_state(0)
    before = count_logs(id_test)
    res = system.process_frame(frame, yolo_faces)
    after = count_logs(id_test)
    st = res[0]['status'] if res else None
    written = after - before
    # invariant gerbang: log bertambah HANYA jika status success (lolos 2 tahap)
    if written == (1 if st == 'success' else 0):
        if st != 'success':
            passed("IT-04", "gagal liveness TIDAK tercatat ke log_absensi",
                   f"frame statis → liveness Stage 1 gagal (status='{st}'), "
                   f"log_absensi bertambah {written} baris (benar: tidak dicatat)")
        else:
            passed("IT-04", "lolos liveness 2 tahap → tercatat (invariant terpenuhi)",
                   f"status='success', log bertambah {written} (gerbang konsisten)")
    else:
        failed("IT-04", "Liveness → DB",
               f"status='{st}' tapi log bertambah {written} (invariant gerbang dilanggar)")

    return id_test


def run_logic_tests():
    """IT-05, IT-06 — tidak butuh citra."""
    # ── IT-05: DB → Payload (struktur, BUKAN HTTP) ──
    payload = build_payload(123, "Nama Uji", "passage", 0.8765, True)
    required = {
        'id_karyawan': int, 'nama': str, 'timestamp': str, 'jenis_event': str,
        'confidence_score': (int, float), 'status_liveness': bool,
        'keterangan': str, 'source': str, 'versi_model': str,
    }
    missing = [k for k in required if k not in payload]
    badtype = [k for k in required if k in payload and not isinstance(payload[k], required[k])]
    http_ok = True
    try:
        send_payload(payload)  # hanya membentuk & me-log; tidak kirim HTTP
    except Exception as e:
        http_ok = False
        http_err = str(e)
    if not missing and not badtype and payload['jenis_event'] == 'passage' and http_ok:
        passed("IT-05", "struktur payload JSON benar (dibentuk & di-log, bukan HTTP)",
               f"field lengkap & tipe benar: {sorted(required)}; "
               f"jenis_event='passage'; send_payload() jalan tanpa kirim HTTP (hanya log)")
    else:
        failed("IT-05", "DB → Payload",
               f"missing={missing}, badtype={badtype}, http_ok={http_ok}")

    # ── IT-06: Log → Resolver (agregasi check-in/check-out) ──
    nip = f"{TEST_NIP_PREFIX}IT06"
    id_k = ops.save_karyawan(nip, "IT Resolver", "Dosen", "internal")
    if id_k is None:
        return failed("IT-06", "Log → Resolver", "setup enroll gagal")
    ts = [datetime(2099, 2, 20, 7, 40, 0),
          datetime(2099, 2, 20, 12, 0, 0),
          datetime(2099, 2, 20, 16, 50, 0)]
    conn = get_connection()
    cur = conn.cursor()
    for t in ts:
        cur.execute(
            "INSERT INTO log_absensi (id_karyawan, timestamp, jenis_event, "
            "confidence_score, status_liveness) VALUES (%s,%s,'passage',0.9,TRUE)",
            (id_k, t))
    conn.commit()
    conn.close()

    inserted = ops.resolve_attendance_for_date(TEST_FUTURE_DATE)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT check_in_time, check_out_time FROM absensi_harian "
                "WHERE id_karyawan=%s AND tanggal=%s", (id_k, TEST_FUTURE_DATE))
    row = cur.fetchone()
    conn.close()
    if row and row[0] == ts[0] and row[1] == ts[-1]:
        passed("IT-06", "resolver agregasi log → absensi_harian (check-in/out benar)",
               f"{len(ts)} log → check_in={row[0].time()} (MIN), "
               f"check_out={row[1].time()} (MAX), rows_inserted={inserted}")
    else:
        failed("IT-06", "Log → Resolver",
               f"row={row} (expected check_in={ts[0]}, check_out={ts[-1]})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--image', default=None, help='path citra fixture untuk IT-01..04')
    args = ap.parse_args()

    dbname = config.DB_CONFIG['database']
    header = [
        "=" * 72,
        "INTEGRATION TESTING — Titik sambung antar modul (Bab V)",
        f"Database: {dbname}",
        f"Dijalankan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 72, "",
    ]
    for l in header:
        print(l)
    results.extend(header)

    if dbname != 'absensi_test':
        warn = (f"⚠️  PERINGATAN: terhubung ke '{dbname}', BUKAN absensi_test. "
                f"Jalankan dengan: DB_NAME=absensi_test python scripts/test_integration.py")
        print(warn + "\n")
        results.append(warn)

    print("Pre-test cleanup...")
    cleanup_test_data()
    print()

    # IT-05 & IT-06 dulu (tak butuh model/citra) supaya tetap jalan walau fixture absen
    run_logic_tests()

    fixture = find_fixture(args.image)
    if fixture is None:
        msg = ("Tidak ada citra fixture (data/probes/<id>/*.jpg atau "
               "data/photos/*/foto_frontal.jpeg). IT-01..IT-04 dilewati. "
               "Beri citra via --image PATH, atau capture probe dulu.")
        print("\n" + msg)
        for tc in ("IT-01", "IT-02", "IT-03", "IT-04"):
            skipped(tc, "butuh citra fixture", "tidak ditemukan citra")
        results.append(msg)
    else:
        print(f"\nFixture: {fixture}")
        frame = cv2.imread(fixture)
        if frame is None:
            for tc in ("IT-01", "IT-02", "IT-03", "IT-04"):
                skipped(tc, "fixture gagal dibaca", fixture)
        else:
            print("Memuat AttendanceSystem (YOLO + InsightFace + MiniFASNet)...\n")
            from src.attendance import AttendanceSystem
            system = AttendanceSystem()
            try:
                run_image_tests(system, frame)
            except Exception as e:
                failed("IT-01..04", "Exception saat integration test",
                       f"{type(e).__name__}: {e}")

    print("\nPost-test cleanup...")
    cleanup_test_data()

    p = sum(1 for r in results if r.startswith("[PASS]"))
    f = sum(1 for r in results if r.startswith("[FAIL]"))
    s = sum(1 for r in results if r.startswith("[SKIP]"))
    summary = ["", "=" * 72,
               f"RINGKASAN: {p} PASS, {f} FAIL, {s} SKIP", "=" * 72]
    for l in summary:
        print(l)
    results.extend(summary)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "tests", "hasil_integration_testing.txt")
    with open(out, "w") as fh:
        fh.write("\n".join(results))
    print(f"\n✓ Output: {os.path.normpath(out)}")


if __name__ == "__main__":
    main()
