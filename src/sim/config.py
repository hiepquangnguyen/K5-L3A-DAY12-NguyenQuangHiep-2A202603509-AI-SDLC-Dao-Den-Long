"""Configuration and Test Contract v1.2 loader for Đảo Đèn Lồng."""

from __future__ import annotations

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT_DIR / "game.contract.json"

TICK_RATE = 60
DT = 1.0 / TICK_RATE
FUEL_SCALE = 60

JUMP_SPEED = 7.0
GRAVITY = 20.0
SHADE_DEFAULT_Y = 1.0
DRIFTER_DEFAULT_Y = 1.2

NIGHT_DURATION_KEYS: dict[int, str] = {
    1: "night1_duration_s",
    2: "night2_duration_s",
    3: "night3_duration_s",
}

VALID_SHADE_STATES: frozenset[str] = frozenset(
    {"spawning", "wander", "chase", "drain", "recoil", "stunned"}
)
VALID_DRIFTER_STATES: frozenset[str] = frozenset(
    {"idle", "chase", "flee", "removed"}
)


def load_contract(path: Path | None = None) -> dict:
    """Load and return parsed game.contract.json."""
    target = path or CONTRACT_PATH
    with target.open("r", encoding="utf-8") as fh:
        return json.load(fh)
