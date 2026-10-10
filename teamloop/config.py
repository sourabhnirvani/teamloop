"""Paths and settings. Loads .env from the repo root once, on first import."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def workspace() -> Path:
    path = Path(os.getenv("TEAMLOOP_WORKSPACE") or ROOT / "workspace")
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return Path(os.getenv("TEAMLOOP_DB") or workspace() / "teamloop.db")


def port() -> int:
    return int(os.getenv("TEAMLOOP_PORT", "8765"))
