"""Configuration and Test Contract loader for Đảo Đèn Lồng."""

from __future__ import annotations

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT_DIR / "game.contract.json"

TICK_RATE = 60
DT = 1.0 / TICK_RATE

DEFAULT_ISLAND_RADIUS = 45.0
JUMP_SPEED = 7.5
GRAVITY = 20.0
SHADE_DEFAULT_Y = 1.0

DEFAULT_LANTERN_POSITIONS: tuple[tuple[str, tuple[float, float, float]], ...] = (
    ("L1", (0.0, 0.0, 25.0)),
    ("L2", (23.776, 0.0, 7.725)),
    ("L3", (14.695, 0.0, -20.225)),
    ("L4", (-14.695, 0.0, -20.225)),
    ("L5", (-23.776, 0.0, 7.725)),
)

VALID_LANTERN_IDS: frozenset[str] = frozenset(lid for lid, _ in DEFAULT_LANTERN_POSITIONS)


def load_contract(path: Path | None = None) -> dict:
    """Load and return parsed game.contract.json."""
    target = path or CONTRACT_PATH
    with target.open("r", encoding="utf-8") as fh:
        return json.load(fh)
