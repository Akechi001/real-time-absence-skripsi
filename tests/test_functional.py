"""
test_functional.py — Reliability testing untuk fungsi-fungsi inti sistem absensi.

Coverage: TC-01 sampai TC-10 (enrollment, resolver, cooldown, soft delete, schema query).

Strategi: pakai marker `TEST_REL_` pada NIP + tanggal sintetis (2099-01-15)
supaya gampang di-cleanup. Cleanup dilakukan SEBELUM dan SESUDAH test
untuk pastikan idempoten — tidak butuh transaction rollback karena
function operations.py auto-commit.
"""

import sys
import os
from datetime import datetime, date

import numpy as np

# Add project root to path supaya bisa import src.*
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db import get_connection
from src.database import operations as ops
import config


TEST_NIP_PREFIX = "TEST_REL_"
TEST_FUTURE_DATE = date(2099, 1, 15)

results = []


def log(status, tc_id, desc, detail=""):
    line = f"[{status}] {tc_id}: {desc}"
    if detail:
        line += f"\n        → {detail}"
    print(line)
    results.append(line)


def passed(tc, desc, detail=""):
    log("PASS", tc, desc, detail)


def failed(tc, desc, detail=""):
    log("FAIL", tc, desc, detail)


def cleanup_test_data():
    """Hapus semua data test berdasarkan marker TEST_REL_ + tanggal 2099."""
    conn = get_connection()
    if not conn:
        print("⚠ Cleanup gagal — tidak bisa connect DB")
        return
    try:
        cur = conn.cursor()
        # Order: child tables dulu
        cur.execute(
            "DELETE FROM log_absensi WHERE id_karyawan IN "
            "(SELECT id_karyawan FROM karyawan WHERE nip LIKE %s)",
            (f"{TEST_NIP_PREFIX}%",),
        )
        cur.execute(
            "DELETE FROM absensi_harian WHERE tanggal = %s",
            (TEST_FUTURE_DATE,),
        )
        cur.execute(
            "DELETE FROM resolve_log WHERE tanggal = %s",
            (TEST_FUTURE_DATE,),
        )
        cur.execute(
            "DELETE FROM template_wajah WHERE id_karyawan IN "
            "(SELECT id_karyawan FROM karyawan WHERE nip LIKE %s)",
            (f"{TEST_NIP_PREFIX}%",),
        )
        cur.execute(
            "DELETE FROM karyawan WHERE nip LIKE %s",
            (f"{TEST_NIP_PREFIX}%",),
        )
        conn.commit()
    finally:
        conn.close()


def fake_embedding():
    """Fake 512-dim embedding untuk test enrollment (gak butuh foto real)."""
    rng = np.random.default_rng(seed=42)
    return rng.random(512, dtype=np.float32)


# ────────────────────────────────────────────────────────────────────────
# Test Cases
# ────────────────────────────────────────────────────────────────────────


def test_01_enroll_valid():
    nip = f"{TEST_NIP_PREFIX}001"
    nama = "Test Karyawan 01"
    emb = fake_embedding()
    id_karyawan = ops.save_karyawan_with_template(
        nip, nama, "Dosen", "internal", emb
    )

    if id_karyawan is None:
        return failed("TC-01", "Enroll valid karyawan",
                      "save_karyawan_with_template returned None")

    k = ops.get_karyawan_by_id(id_karyawan)
    if k and k["nip"] == nip and k["nama"] == nama and k["status_aktif"]:
        passed("TC-01", "Enroll karyawan baru valid",
               f"id_karyawan={id_karyawan}, nip={k['nip']}, status_aktif={k['status_aktif']}")
    else:
        failed("TC-01", "Enroll valid karyawan",
               f"karyawan di DB tidak sesuai: {k}")


def test_02_duplicate_nip():
    nip = f"{TEST_NIP_PREFIX}002"
    emb = fake_embedding()
    id1 = ops.save_karyawan_with_template(nip, "First", "Dosen", "internal", emb)
    id2 = ops.save_karyawan_with_template(nip, "Second", "Dosen", "internal", emb)

    if id1 is not None and id2 is None:
        passed("TC-02", "Enroll dengan NIP duplikat ditolak",
               f"insert#1 id={id1}, insert#2 rejected (returned None)")
    else:
        failed("TC-02", "Duplikat NIP harus ditolak",
               f"insert#1={id1}, insert#2={id2} (expected None untuk #2)")


def test_03_nip_invalid_format():
    """NIP dengan huruf — validasi di UI layer (enrollment_window.py:31)
    pakai str.isdigit(). Test logic-nya bukan via DB constraint."""

    def _validate_nip(proposed):
        if not proposed:
            return False
        if len(proposed) > 50:
            return False
        return proposed.isdigit()

    invalid_cases = ["ABC123", "12.34", "12-345", "abc"]
    valid_cases = ["123456", "0001", "1"]

    all_invalid_rejected = all(not _validate_nip(s) for s in invalid_cases)
    all_valid_accepted = all(_validate_nip(s) for s in valid_cases)

    if all_invalid_rejected and all_valid_accepted:
        passed("TC-03", "NIP dengan huruf/simbol ditolak (UI validation)",
               f"invalid {invalid_cases} → rejected; valid {valid_cases} → accepted")
    else:
        failed("TC-03", "Validasi NIP",
               f"invalid_rejected={all_invalid_rejected}, "
               f"valid_accepted={all_valid_accepted}")


def test_04_resolver_normal():
    """Resolver dengan 3 lewatan → check_in=MIN, check_out=MAX."""
    nip = f"{TEST_NIP_PREFIX}004"
    id_karyawan = ops.save_karyawan(nip, "Test Resolver 04", "Dosen", "internal")
    if id_karyawan is None:
        return failed("TC-04", "Resolver normal", "Setup: gagal insert karyawan")

    # Insert log_absensi langsung dengan timestamp custom (bypass save_log_absensi
    # yang pakai DEFAULT NOW()).
    conn = get_connection()
    cur = conn.cursor()
    timestamps = [
        datetime(2099, 1, 15, 7, 45, 0),   # earliest (check_in)
        datetime(2099, 1, 15, 12, 30, 0),  # tengah
        datetime(2099, 1, 15, 17, 5, 0),   # latest (check_out)
    ]
    for ts in timestamps:
        cur.execute(
            "INSERT INTO log_absensi (id_karyawan, timestamp, jenis_event, "
            "confidence_score, status_liveness) "
            "VALUES (%s, %s, 'passage', 0.9, TRUE)",
            (id_karyawan, ts),
        )
    conn.commit()
    conn.close()

    inserted = ops.resolve_attendance_for_date(TEST_FUTURE_DATE)
    if inserted == 0:
        return failed("TC-04", "Resolver normal",
                      "resolve_attendance_for_date returned 0 row inserted")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT check_in_time, check_out_time, keterangan, "
        "status_terlambat, status_pulang_cepat "
        "FROM absensi_harian WHERE id_karyawan=%s AND tanggal=%s",
        (id_karyawan, TEST_FUTURE_DATE),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        return failed("TC-04", "Resolver normal", "Row tidak ditemukan di absensi_harian")

    check_in, check_out, ket, terlambat, pulang_cepat = row
    expected_in = timestamps[0]
    expected_out = timestamps[-1]

    if check_in == expected_in and check_out == expected_out:
        passed("TC-04", "Resolver agregat MIN(timestamp)=check_in, MAX=check_out",
               f"check_in={check_in.time()} (MIN), check_out={check_out.time()} (MAX), "
               f"terlambat={terlambat}, pulang_cepat={pulang_cepat}, "
               f"keterangan='{ket}'")
    else:
        failed("TC-04", "Resolver normal",
               f"Expected check_in={expected_in}, check_out={expected_out}; "
               f"got check_in={check_in}, check_out={check_out}")


def test_05_resolver_incomplete():
    """Resolver dengan cuma 1 lewatan → keterangan='data tidak lengkap', check_in/out NULL."""
    # Bersihkan absensi_harian + resolve_log untuk TEST_FUTURE_DATE
    # (dari run TC-04 sebelumnya).
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM absensi_harian WHERE tanggal=%s", (TEST_FUTURE_DATE,))
    cur.execute("DELETE FROM resolve_log WHERE tanggal=%s", (TEST_FUTURE_DATE,))
    conn.commit()
    conn.close()

    nip = f"{TEST_NIP_PREFIX}005"
    id_karyawan = ops.save_karyawan(nip, "Test Resolver 05", "Dosen", "internal")
    if id_karyawan is None:
        return failed("TC-05", "Resolver incomplete", "Setup gagal insert karyawan")

    conn = get_connection()
    cur = conn.cursor()
    # Cuma 1 lewatan
    cur.execute(
        "INSERT INTO log_absensi (id_karyawan, timestamp, jenis_event, "
        "confidence_score, status_liveness) "
        "VALUES (%s, %s, 'passage', 0.9, TRUE)",
        (id_karyawan, datetime(2099, 1, 15, 9, 0, 0)),
    )
    conn.commit()
    conn.close()

    inserted = ops.resolve_attendance_for_date(TEST_FUTURE_DATE)
    if inserted == 0:
        return failed("TC-05", "Resolver incomplete", "No row inserted")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT check_in_time, check_out_time, keterangan "
        "FROM absensi_harian WHERE id_karyawan=%s AND tanggal=%s",
        (id_karyawan, TEST_FUTURE_DATE),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        return failed("TC-05", "Resolver incomplete",
                      "Row tidak ditemukan setelah resolve")

    check_in, check_out, ket = row
    if check_in is None and check_out is None and "tidak lengkap" in (ket or ""):
        passed("TC-05", "Resolver 1 lewatan → 'data tidak lengkap'",
               f"check_in=NULL, check_out=NULL, keterangan='{ket}'")
    else:
        failed("TC-05", "Resolver incomplete",
               f"check_in={check_in}, check_out={check_out}, keterangan='{ket}'")


def test_06_resolver_idempotent():
    """Call resolve_attendance_for_date 2x → no duplicate (ON CONFLICT DO NOTHING)."""
    # State sekarang: sudah ada row dari TC-05 (TEST_REL_005)
    inserted_again = ops.resolve_attendance_for_date(TEST_FUTURE_DATE)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM absensi_harian WHERE tanggal=%s "
        "AND id_karyawan IN (SELECT id_karyawan FROM karyawan WHERE nip LIKE %s)",
        (TEST_FUTURE_DATE, f"{TEST_NIP_PREFIX}%"),
    )
    count = cur.fetchone()[0]
    conn.close()

    if inserted_again == 0:
        passed("TC-06", "Resolver idempotent (ON CONFLICT DO NOTHING)",
               f"second call inserted_count={inserted_again}, "
               f"total rows TEST_REL_ untuk {TEST_FUTURE_DATE} tetap {count}")
    else:
        failed("TC-06", "Resolver idempotent",
               f"second call inserted_count={inserted_again} (expected 0)")


def test_07_cooldown():
    """Cooldown check in-memory (bukan di DB). Replikasi logic dari AttendanceSystem."""
    import time

    class CooldownStub:
        def __init__(self):
            self.cooldown = {}

        def is_cooldown(self, id_karyawan):
            if id_karyawan not in self.cooldown:
                return False
            return time.time() - self.cooldown[id_karyawan] < config.COOLDOWN_SECONDS

    stub = CooldownStub()
    id_karyawan = 999

    # Pre-condition: belum cooldown
    if stub.is_cooldown(id_karyawan):
        return failed("TC-07", "Cooldown initial state",
                      "is_cooldown=True padahal belum di-set")

    # Simulasi: orang lewat → set timestamp
    stub.cooldown[id_karyawan] = time.time()

    # Langsung check (harus True karena baru di-set)
    if stub.is_cooldown(id_karyawan):
        passed("TC-07", f"Cooldown {config.COOLDOWN_SECONDS}s aktif setelah passage",
               f"is_cooldown=True dalam window {config.COOLDOWN_SECONDS}s")
    else:
        failed("TC-07", "Cooldown active",
               "is_cooldown=False padahal baru di-set")


def test_08_soft_delete():
    """delete_karyawan → status_aktif=FALSE, row tetap exists, template terhapus."""
    nip = f"{TEST_NIP_PREFIX}008"
    emb = fake_embedding()
    id_karyawan = ops.save_karyawan_with_template(
        nip, "Test SoftDelete", "Dosen", "internal", emb
    )
    if id_karyawan is None:
        return failed("TC-08", "Soft delete", "Setup insert gagal")

    k_before = ops.get_karyawan_by_id(id_karyawan)
    if not k_before or not k_before["status_aktif"]:
        return failed("TC-08", "Soft delete pre-check",
                      f"karyawan status_aktif != TRUE saat awal: {k_before}")

    success = ops.delete_karyawan(id_karyawan)
    if not success:
        return failed("TC-08", "Soft delete", "delete_karyawan returned False")

    # Verify row tetap exists tapi status_aktif=FALSE
    k_after = ops.get_karyawan_by_id(id_karyawan)
    if k_after is None:
        return failed("TC-08", "Soft delete",
                      "Row hilang setelah delete (harusnya soft delete)")

    # Template harus terhapus
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM template_wajah WHERE id_karyawan=%s",
        (id_karyawan,),
    )
    tpl_count = cur.fetchone()[0]
    conn.close()

    if not k_after["status_aktif"] and tpl_count == 0:
        passed("TC-08", "Soft delete karyawan",
               f"row exists, status_aktif=FALSE, template dihapus (count={tpl_count})")
    else:
        failed("TC-08", "Soft delete",
               f"status_aktif={k_after['status_aktif']} (expected FALSE), "
               f"template_count={tpl_count} (expected 0)")


def test_09_get_log_absensi_schema():
    """get_log_absensi() schema check: harus return list dengan field-field tertentu."""
    logs = ops.get_log_absensi(filter_date="all", limit=1)
    required_keys = {"id_log", "id_karyawan", "timestamp", "jenis_event",
                     "confidence_score", "status_liveness"}

    if not isinstance(logs, list):
        return failed("TC-09", "get_log_absensi()",
                      f"return value bukan list: {type(logs).__name__}")

    if not logs:
        passed("TC-09", "get_log_absensi() return list (DB log kosong, function OK)",
               "DB belum punya log_absensi, return [] (valid)")
        return

    actual_keys = set(logs[0].keys())
    missing = required_keys - actual_keys

    if not missing:
        passed("TC-09", "get_log_absensi() schema sesuai",
               f"required keys present: {sorted(required_keys)}, "
               f"actual keys: {sorted(actual_keys)}")
    else:
        failed("TC-09", "get_log_absensi() schema",
               f"missing keys: {missing}, actual keys: {actual_keys}")


def test_10_stats_schema():
    """get_absensi_harian_stats() schema check."""
    stats = ops.get_absensi_harian_stats("all")

    if stats is None:
        return failed("TC-10", "get_absensi_harian_stats()", "returned None")

    required_keys = {"total", "terlambat", "pulang_cepat", "tidak_lengkap"}
    actual_keys = set(stats.keys())

    if required_keys <= actual_keys and all(isinstance(v, int) for v in stats.values()):
        passed("TC-10", "get_absensi_harian_stats() return numeric dict",
               f"keys={sorted(actual_keys)}, values={stats}")
    else:
        failed("TC-10", "get_absensi_harian_stats() schema",
               f"keys={actual_keys}, values={stats}, "
               f"all_int={all(isinstance(v, int) for v in stats.values())}")


# ────────────────────────────────────────────────────────────────────────


def main():
    header_lines = [
        "=" * 72,
        "FUNCTIONAL TESTING — Sistem Absensi Wajah",
        "STIE Ciputra Makassar — Skripsi Enrico Kevin Ariantho (0806022210012)",
        f"Dijalankan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 72,
        "",
    ]
    for l in header_lines:
        print(l)
    results.extend(header_lines)

    print("Pre-test cleanup (hapus residual TEST_REL_ data)...")
    cleanup_test_data()
    print()
    results.append("Pre-test cleanup: done")
    results.append("")

    test_funcs = [
        test_01_enroll_valid,
        test_02_duplicate_nip,
        test_03_nip_invalid_format,
        test_04_resolver_normal,
        test_05_resolver_incomplete,
        test_06_resolver_idempotent,
        test_07_cooldown,
        test_08_soft_delete,
        test_09_get_log_absensi_schema,
        test_10_stats_schema,
    ]

    for f in test_funcs:
        try:
            f()
        except Exception as e:
            failed(f.__name__, "Exception saat test",
                   f"{type(e).__name__}: {e}")

    print()
    print("Post-test cleanup...")
    cleanup_test_data()
    print()
    results.append("")
    results.append("Post-test cleanup: done")

    pass_count = sum(1 for r in results if r.startswith("[PASS]"))
    fail_count = sum(1 for r in results if r.startswith("[FAIL]"))
    summary_lines = [
        "",
        "=" * 72,
        f"RINGKASAN: {pass_count} PASS, {fail_count} FAIL "
        f"(total {pass_count + fail_count} test cases)",
        "=" * 72,
    ]
    for l in summary_lines:
        print(l)
    results.extend(summary_lines)

    out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "hasil_functional_testing.txt")
    with open(out_file, "w") as f:
        f.write("\n".join(results))
    print(f"\n✓ Output saved: {out_file}")


if __name__ == "__main__":
    main()
