# src/utils/onnx_patch.py - Mitigasi memory leak ONNX Runtime CPU
#
# Root cause memory leak yang aku alami:
# - InsightFace pakai ONNX Runtime sebagai inference engine
# - ONNX Runtime default pakai BFCArena memory allocator
# - Arena pool TIDAK shrink di CPU backend (cuma extend)
# - Setiap inference allocate from pool → pool terus tumbuh
# - Untuk attendance subprocess yang inference ratusan frame/menit,
#   pool grow tanpa bound → swap usage menggunung 1.5 GB/menit
#
# Fix: monkey-patch onnxruntime.InferenceSession.__init__ supaya
# selalu disable CPU arena pool + memory pattern caching.
#
# Setting yang di-disable:
# - enable_cpu_mem_arena = False
#     → pakai default malloc/free yang langsung release ke OS
# - enable_mem_pattern = False
#     → tidak cache pola allocation antar-inference
#
# Tradeoff: ~10-20% slower inference karena gak ada pool optimization.
# Untuk attendance dengan FPS_SAMPLING = 20, masih cukup cepat.
# Worth it karena: memory stable vs slightly slower.
#
# IMPORTANT: harus di-import SEBELUM insightface (atau library lain yang
# manggil onnxruntime.InferenceSession). Pattern: import patch lalu import
# library yang pakai ONNX.

import onnxruntime as ort

_original_init = ort.InferenceSession.__init__
_patched = False


def _patched_init(self, path_or_bytes, sess_options=None, providers=None,
                  provider_options=None, **kwargs):
    """Wrapped __init__ yang inject SessionOptions tanpa arena pool."""
    if sess_options is None:
        sess_options = ort.SessionOptions()

    # Disable arena memory pool — penyebab utama leak di CPU backend
    sess_options.enable_cpu_mem_arena = False
    # Disable memory pattern caching — accumulator sekunder
    sess_options.enable_mem_pattern = False

    return _original_init(
        self, path_or_bytes,
        sess_options=sess_options,
        providers=providers,
        provider_options=provider_options,
        **kwargs,
    )


def apply():
    """Apply monkey-patch. Idempotent — aman dipanggil berkali-kali."""
    global _patched
    if _patched:
        return
    ort.InferenceSession.__init__ = _patched_init
    _patched = True
    print("✓ ONNX patch applied: CPU arena pool & mem pattern disabled")


# Auto-apply saat module di-import
apply()
