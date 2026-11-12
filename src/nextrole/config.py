"""Paths, settings and config-file loading."""

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

MODEL = os.getenv("NEXTROLE_MODEL", "claude-opus-5-5")
MIN_SCORE = int(os.getenv("NEXTROLE_MIN_SCORE", "70"))
DB_PATH = Path(os.getenv("NEXTROLE_DB", ROOT / "data" / "nextrole.db"))


@lru_cache
def load_companies() -> dict[str, list[str]]:
    return yaml.safe_load((ROOT / "config" / "companies.yaml").read_text()) or {}


@lru_cache
def load_profile() -> dict:
    return yaml.safe_load((ROOT / "config" / "profile.yaml").read_text())


def profile_text() -> str:
    """The profile as text for prompts, without contact details."""
    profile = dict(load_profile())
    for private in ("email", "links", "cv_path"):
        profile.pop(private, None)
    return yaml.safe_dump(profile, sort_keys=False, allow_unicode=True)
