# scripts/eval_far_frr.py
#
# Pengujian akurasi pengenalan wajah LEVEL MODUL (Bab V) — Fase 3 & Fase 5.
#
# TIDAK lewat process_frame: murni mengukur recognition, tanpa cooldown/liveness.
# Memakai fungsi yang SAMA dengan sistem nyata:
#   - ekstraksi embedding : FaceDetector.detect (YOLO) + FaceRecognizer.get_embedding
#   - cosine similarity    : FaceRecognizer.cosine_similarity
#   - keputusan match      : FaceRecognizer.identify (argmax + threshold)
#   - template subjek      : operations.get_all_templates() (tabel template_wajah)
#
# Menghasilkan DUA analisis dari capture probe yang sama:
#   (A) Tabel MULTI-SUBJEK (Fase 3) per (subjek, kondisi): N, rata-rata confidence,
#       dikenali benar/salah/tidak, FRR — via identify() argmax (mirip sistem live).
#   (B) FAR/FRR pairwise (Fase 5) untuk threshold 0,3/0,4/0,5 — metodologi biometrik.
#
# Probe disimpan per subjek & kondisi:  data/probes/<id_karyawan>/<kondisi>/*.jpg
# (file lepas langsung di <id_karyawan>/ dianggap kondisi "normal").
#
# Pakai DB tes:
#   capture : DB_NAME=absensi_test python scripts/eval_far_frr.py capture <id> --kondisi noglasses
#   eval    : DB_NAME=absensi_test python scripts/eval_far_frr.py eval
#
# Tidak mengubah file sistem apa pun.

import sys
import os
import csv
import glob
import time
import argparse

import cv2
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from src.modules.face_detector import FaceDetector
from src.modules.face_recognizer import FaceRecognizer
from src.database.operations import get_all_templates

PROBES_DIR = "data/probes"
RESULTS_DIR = "results"
THRESHOLDS = [0.3, 0.4, 0.5]


def extract_embedding(detector, recognizer, frame):
    """Embedding (np.array) atau None — persis jalur process_frame (YOLO->get_embedding)."""
    faces_yolo = detector.detect(frame)
    faces_if = recognizer.app.get(frame)
    if not faces_yolo:
        return None
    bbox = max(faces_yolo, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    return recognizer.get_embedding(frame, [int(x) for x in bbox[:4]], faces_if)


# --------------------------------------------------------------------------
# MODE: capture
# --------------------------------------------------------------------------
def cmd_capture(args):
    sid = str(args.id_karyawan)
    kondisi = args.kondisi
    out_dir = os.path.join(args.probes, sid, kondisi)
    os.makedirs(out_dir, exist_ok=True)

    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
    if not cap.isOpened():
        print("✗ Kamera tidak bisa dibuka (cek CAMERA_INDEX).")
        return

    existing = len(glob.glob(os.path.join(out_dir, "probe_*.jpg")))
    saved = 0
    print(f"\n=== CAPTURE PROBE  subjek id={sid}  kondisi='{kondisi}' → {out_dir} ===")
    print("SPACE = simpan frame  |  q / ESC = selesai")
    print(f"(sudah ada {existing} probe untuk kondisi ini)\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("✗ Gagal baca frame."); break
        view = frame.copy()
        cv2.putText(view, f"id={sid} [{kondisi}]  sesi ini: {saved}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(view, "SPACE=simpan  q=keluar", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.imshow("Capture Probe", view)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), 27):
            break
        if key == 32:
            idx = existing + saved + 1
            stamp = time.strftime("%Y%m%d_%H%M%S")
            path = os.path.join(out_dir, f"probe_{stamp}_{idx:03d}.jpg")
            cv2.imwrite(path, frame)
            saved += 1
            print(f"  ✓ {path}")

    cap.release()
    cv2.destroyAllWindows()
    print(f"\nSelesai. {saved} probe baru (id={sid}, kondisi='{kondisi}', "
          f"total {existing + saved}).")


# --------------------------------------------------------------------------
# Kumpulkan probe per (subjek, kondisi)
# --------------------------------------------------------------------------
def collect_probes(detector, recognizer, probes_dir):
    """Return (probes, skipped). probes: list dict {id, kondisi, path, emb}."""
    probes, skipped = [], []
    subj_dirs = sorted(d for d in glob.glob(os.path.join(probes_dir, "*"))
                       if os.path.isdir(d))
    for sd in subj_dirs:
        sid = os.path.basename(sd)
        # (kondisi, daftar file): subfolder = kondisi; file lepas = 'normal'
        groups = {}
        loose = (glob.glob(os.path.join(sd, "*.jpg")) +
                 glob.glob(os.path.join(sd, "*.jpeg")) +
                 glob.glob(os.path.join(sd, "*.png")))
        if loose:
            groups["normal"] = sorted(loose)
        for kd in sorted(glob.glob(os.path.join(sd, "*"))):
            if os.path.isdir(kd):
                imgs = sorted(glob.glob(os.path.join(kd, "*.jpg")) +
                              glob.glob(os.path.join(kd, "*.jpeg")) +
                              glob.glob(os.path.join(kd, "*.png")))
                if imgs:
                    groups[os.path.basename(kd)] = imgs
        for kondisi, imgs in groups.items():
            for p in imgs:
                frame = cv2.imread(p)
                if frame is None:
                    skipped.append((p, "gagal baca")); continue
                emb = extract_embedding(detector, recognizer, frame)
                if emb is None:
                    skipped.append((p, "wajah tak terdeteksi")); continue
                probes.append({'id': sid, 'kondisi': kondisi, 'path': p, 'emb': emb})
    return probes, skipped


# --------------------------------------------------------------------------
# MODE: eval
# --------------------------------------------------------------------------
def cmd_eval(args):
    templates = get_all_templates()
    if not templates:
        print("✗ Tidak ada template di DB. Enroll subjek dulu (cek DB_NAME).")
        return
    tpl_by_id = {str(t['id_karyawan']): t for t in templates}
    nama_by_id = {str(t['id_karyawan']): t['nama'] for t in templates}
    print(f"Template dimuat: {len(templates)} subjek → {list(tpl_by_id)}")

    detector = FaceDetector()
    recognizer = FaceRecognizer()
    thr_op = config.FACE_SIMILARITY_THRESHOLD

    probes, skipped = collect_probes(detector, recognizer, args.probes)
    if not probes:
        print(f"✗ Tidak ada probe valid di {args.probes}/<id>/<kondisi>/. "
              f"Capture dulu: python scripts/eval_far_frr.py capture <id> --kondisi noglasses")
        for p, why in skipped:
            print(f"  - {p}: {why}")
        return

    os.makedirs(args.out, exist_ok=True)

    # =====================================================================
    # (A) TABEL MULTI-SUBJEK (Fase 3) — identify() argmax, per (subjek,kondisi)
    # =====================================================================
    detail_rows = []          # per probe
    groups = {}               # (id,kondisi) -> list of records
    for pr in probes:
        sid, kondisi, emb = pr['id'], pr['kondisi'], pr['emb']
        own = tpl_by_id.get(sid)
        genuine_sim = recognizer.cosine_similarity(emb, own['embedding']) if own else None
        match = recognizer.identify(emb, templates)  # argmax + threshold operasional
        if match is None:
            outcome, ident_as, ident_score = 'tidak_dikenali', '', 0.0
        elif str(match['id_karyawan']) == sid:
            outcome, ident_as, ident_score = 'benar', str(match['id_karyawan']), match['confidence']
        else:
            outcome, ident_as, ident_score = 'salah', str(match['id_karyawan']), match['confidence']
        rec = {'id': sid, 'nama': nama_by_id.get(sid, '?'), 'kondisi': kondisi,
               'path': pr['path'], 'genuine_sim': genuine_sim,
               'identified_as': ident_as, 'identify_score': ident_score, 'outcome': outcome}
        detail_rows.append(rec)
        groups.setdefault((sid, kondisi), []).append(rec)

    # CSV detail multi-subjek
    ms_detail = os.path.join(args.out, "multisubject_detail.csv")
    with open(ms_detail, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['id_karyawan', 'nama', 'kondisi', 'probe_path',
                    'genuine_similarity', 'identified_as', 'identify_score', 'outcome'])
        for r in detail_rows:
            w.writerow([r['id'], r['nama'], r['kondisi'], r['path'],
                        round(r['genuine_sim'], 4) if r['genuine_sim'] is not None else '',
                        r['identified_as'], round(r['identify_score'], 4), r['outcome']])

    # CSV ringkas multi-subjek per (subjek, kondisi)
    ms_summary = os.path.join(args.out, "multisubject_summary.csv")
    print(f"\n=== (A) TABEL MULTI-SUBJEK (threshold operasional {thr_op}) ===")
    hdr = (f"{'id':>4} {'nama':16} {'kondisi':10} {'N':>3} {'mean_conf':>9} "
           f"{'min_conf':>8} {'benar':>7} {'salah':>5} {'tdk_kenal':>9} {'FRR%':>6}")
    print(hdr); print("-" * len(hdr))
    with open(ms_summary, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['id_karyawan', 'nama', 'kondisi', 'jumlah_uji', 'mean_confidence',
                    'min_confidence', 'dikenali_benar', 'salah_kenal', 'tidak_dikenali',
                    'frr_pct'])
        for (sid, kondisi), recs in sorted(groups.items()):
            n = len(recs)
            gsims = [r['genuine_sim'] for r in recs if r['genuine_sim'] is not None]
            mean_c = sum(gsims) / len(gsims) if gsims else 0.0
            min_c = min(gsims) if gsims else 0.0
            benar = sum(1 for r in recs if r['outcome'] == 'benar')
            salah = sum(1 for r in recs if r['outcome'] == 'salah')
            tdk = sum(1 for r in recs if r['outcome'] == 'tidak_dikenali')
            frr = (n - benar) / n * 100 if n else 0.0   # gagal dikenali sbg diri sendiri
            nama = nama_by_id.get(sid, '?')[:16]
            w.writerow([sid, nama_by_id.get(sid, '?'), kondisi, n, round(mean_c, 4),
                        round(min_c, 4), f"{benar}/{n}", salah, tdk, round(frr, 2)])
            print(f"{sid:>4} {nama:16} {kondisi:10} {n:>3} {mean_c:>9.3f} "
                  f"{min_c:>8.3f} {benar:>4}/{n:<2} {salah:>5} {tdk:>9} {frr:>5.1f}%")

    # =====================================================================
    # (B) FAR/FRR PAIRWISE (Fase 5) — semua probe vs semua template
    # =====================================================================
    pairs = []
    for pr in probes:
        for tid, tpl in tpl_by_id.items():
            sim = recognizer.cosine_similarity(pr['emb'], tpl['embedding'])
            ptype = 'genuine' if pr['id'] == tid else 'impostor'
            pairs.append((pr['path'], pr['id'], tid, ptype, sim))

    genuine = [p for p in pairs if p[3] == 'genuine']
    impostor = [p for p in pairs if p[3] == 'impostor']

    ff_pairs = os.path.join(args.out, "far_frr_pairs.csv")
    with open(ff_pairs, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['probe_path', 'probe_subject', 'template_subject', 'pair_type', 'similarity'])
        for path, sid, tid, ptype, sim in pairs:
            w.writerow([path, sid, tid, ptype, round(sim, 4)])

    ff_summary = os.path.join(args.out, "far_frr_summary.csv")
    print(f"\n=== (B) FAR/FRR PAIRWISE — genuine={len(genuine)}, impostor={len(impostor)} ===")
    print(f"{'Threshold':>9} | {'FRR (genuine ditolak)':>24} | {'FAR (impostor diterima)':>26}")
    print("-" * 68)
    with open(ff_summary, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['threshold', 'genuine_total', 'frr_errors', 'frr_pct',
                    'impostor_total', 'far_errors', 'far_pct'])
        for thr in THRESHOLDS:
            frr_e = sum(1 for p in genuine if p[4] < thr)
            far_e = sum(1 for p in impostor if p[4] >= thr)
            ng, ni = len(genuine), len(impostor)
            frr = frr_e / ng * 100 if ng else 0.0
            far = far_e / ni * 100 if ni else 0.0
            w.writerow([thr, ng, frr_e, round(frr, 2), ni, far_e, round(far, 2)])
            mark = "  <- operasional" if abs(thr - thr_op) < 1e-9 else ""
            print(f"{thr:>9.1f} | {f'{frr_e} dari {ng}  ({frr:5.1f}%)':>24} | "
                  f"{f'{far_e} dari {ni}  ({far:5.1f}%)':>26}{mark}")
    print("-" * 68)

    print(f"\nCSV: {ms_summary}")
    print(f"     {ms_detail}")
    print(f"     {ff_summary}")
    print(f"     {ff_pairs}")
    if skipped:
        print(f"\nProbe dilewati ({len(skipped)}):")
        for p, why in skipped:
            print(f"  - {p}: {why}")
    print("\nCatatan: 'mean_conf' = cosine similarity probe vs template-nya sendiri "
          "(genuine).\n'salah' = dikenali sebagai orang LAIN (false match). "
          "FRR% = (N - benar)/N.\nFAR/FRR ini LEVEL MODUL; pada sistem nyata dilapis "
          "liveness + cooldown.")


def main():
    ap = argparse.ArgumentParser(description="Akurasi pengenalan + FAR/FRR level modul (Bab V)")
    sub = ap.add_subparsers(dest='mode', required=True)

    cap = sub.add_parser('capture', help='rekam probe dari webcam (per subjek & kondisi)')
    cap.add_argument('id_karyawan', help='id_karyawan subjek (sesuai template_wajah)')
    cap.add_argument('--kondisi', default='normal',
                     help="label kondisi, mis. noglasses / glasses (default: normal)")
    cap.add_argument('--probes', default=PROBES_DIR)
    cap.set_defaults(func=cmd_capture)

    ev = sub.add_parser('eval', help='hitung tabel multi-subjek + FAR/FRR')
    ev.add_argument('--probes', default=PROBES_DIR)
    ev.add_argument('--out', default=RESULTS_DIR)
    ev.set_defaults(func=cmd_eval)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
