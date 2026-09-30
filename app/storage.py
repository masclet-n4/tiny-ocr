"""Cliente PocketBase (lazy singleton)."""

import pocketbase

from app.config import PB_URL

_pb = None


def get_pb():
    global _pb
    if _pb is None:
        _pb = pocketbase.Client(PB_URL)
    return _pb