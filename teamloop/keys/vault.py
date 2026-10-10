"""Key vault: secrets live in workspace/keys.vault, sealed with Windows DPAPI (unlocks with the Windows sign-in).

On other systems it falls back to a user-only file, which is fine for development but not sealed.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
from ctypes import wintypes
from pathlib import Path

from teamloop import config

ENTROPY = b"teamloop key vault v1"


def path() -> Path:
    return Path(os.getenv("TEAMLOOP_VAULT") or config.workspace() / "keys.vault")


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> tuple[_Blob, ctypes.Array]:
    buf = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _dpapi(data: bytes, protect: bool) -> bytes:
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    src, _keep1 = _blob(data)
    ent, _keep2 = _blob(ENTROPY)
    out = _Blob()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(src), None, ctypes.byref(ent), None, None, 0x1, ctypes.byref(out))
    if not ok:
        raise OSError("DPAPI could not " + ("seal" if protect else "open") + " the key vault")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def load() -> dict[str, str]:
    p = path()
    if not p.exists():
        return {}
    raw = p.read_bytes()
    data = _dpapi(raw, protect=False) if sys.platform == "win32" else raw
    return json.loads(data.decode("utf-8"))


def save(values: dict[str, str]) -> None:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(values, sort_keys=True).encode("utf-8")
    p.write_bytes(_dpapi(data, protect=True) if sys.platform == "win32" else data)
    if sys.platform != "win32":
        os.chmod(p, 0o600)


def put(name: str, value: str) -> None:
    values = load()
    values[name] = value
    save(values)
    os.environ[name] = value


def remove(name: str) -> None:
    values = load()
    if values.pop(name, None) is not None:
        save(values)
    os.environ.pop(name, None)


def export_to_env() -> int:
    """Put vault keys into this process's environment (vault wins over nothing, never over a set var)."""
    count = 0
    for name, value in load().items():
        if not os.environ.get(name):
            os.environ[name] = value
            count += 1
    return count
