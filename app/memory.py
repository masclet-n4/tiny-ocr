"""Liberación de memoria entre páginas (OCR_MEMORY_TRIM=1)."""

import ctypes
import gc

from app.config import MEMORY_TRIM

_trim = None
if MEMORY_TRIM:
    try:
        # glibc (imagen python:*-slim). Sin glibc, solo se hace gc.collect().
        _libc = ctypes.CDLL("libc.so.6")
        _libc.malloc_trim.argtypes = [ctypes.c_size_t]
        _libc.malloc_trim.restype = ctypes.c_int
        _trim = _libc.malloc_trim
    except (OSError, AttributeError):
        _trim = None


def release_page_memory():
    gc.collect()
    if _trim is not None:
        _trim(0)
