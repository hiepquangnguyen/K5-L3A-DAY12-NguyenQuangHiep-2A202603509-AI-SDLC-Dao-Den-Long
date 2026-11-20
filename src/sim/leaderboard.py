"""Local persistent Top-10 leaderboard storage & export for Đảo Đèn Lồng (Contract v1.3)."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from src.sim.config import ROOT_DIR

DEFAULT_LEADERBOARD_PATH = ROOT_DIR / "data" / "leaderboard.json"
MAX_ENTRIES = 10


class LeaderboardError(ValueError):
    """Raised when a leaderboard submission fails validation."""


def resolve_leaderboard_path(path: Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    env_override = os.environ.get("DDL_LEADERBOARD_PATH")
    if env_override:
        return Path(env_override)
    return DEFAULT_LEADERBOARD_PATH


def is_valid_player_name(name: str) -> bool:
    """Validate 3-12 chars: ASCII [A-Za-z0-9_] or Vietnamese accented letters."""
    if not isinstance(name, str) or not (3 <= len(name) <= 12):
        return False
    for ch in name:
        if ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ("0" <= ch <= "9") or ch == "_":
            continue
        if ord(ch) >= 0x00C0 and ch.isalpha():
            continue
        return False
    return True


def _parse_iso_timestamp(value: object) -> float:
    if not isinstance(value, str) or not value:
        return float("inf")
    try:
        dt = datetime.fromisoformat(value)
        return dt.timestamp()
    except ValueError:
        return float("inf")


def _sort_and_trim(entries: list[dict]) -> list[dict]:
    indexed = list(enumerate(entries))
    indexed.sort(
        key=lambda pair: (
            -int(pair[1].get("score", 0)),
            _parse_iso_timestamp(pair[1].get("achieved_at")),
            pair[0],
        )
    )
    return [pair[1] for pair in indexed[:MAX_ENTRIES]]


def load_entries(path: Path | None = None) -> list[dict]:
    """Load persisted Top-10 entries cleanly (returns [] if missing/empty)."""
    target = resolve_leaderboard_path(path)
    if not target.is_file():
        return []
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []

    raw_entries = raw.get("entries") if isinstance(raw, dict) else None
    if not isinstance(raw_entries, list):
        return []

    cleaned: list[dict] = []
    for item in raw_entries:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        score = item.get("score")
        nights_won = item.get("nights_won")
        achieved_at = item.get("achieved_at")
        seed = item.get("seed")
        if (
            isinstance(name, str)
            and is_valid_player_name(name)
            and isinstance(score, int)
            and not isinstance(score, bool)
            and isinstance(nights_won, int)
            and not isinstance(nights_won, bool)
            and isinstance(achieved_at, str)
            and isinstance(seed, int)
            and not isinstance(seed, bool)
        ):
            cleaned.append(
                {
                    "name": name,
                    "score": max(0, int(score)),
                    "nights_won": max(0, min(3, int(nights_won))),
                    "achieved_at": achieved_at,
                    "seed": int(seed),
                }
            )
    return _sort_and_trim(cleaned)


def save_entries(entries: list[dict], path: Path | None = None) -> None:
    target = resolve_leaderboard_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"entries": entries}, ensure_ascii=False, indent=2) + "\n"
    tmp_path = target.with_suffix(target.suffix + ".tmp")
    tmp_path.write_text(payload, encoding="utf-8", newline="\n")
    os.replace(tmp_path, target)


def add_entry(
    name: str,
    score: int,
    nights_won: int,
    seed: int,
    achieved_at: str | None = None,
    path: Path | None = None,
) -> tuple[dict, list[dict]]:
    """Validate and record a score entry, retaining sorted Top-10 on disk."""
    if not is_valid_player_name(name):
        raise LeaderboardError(
            "Tên phải dài 3–12 ký tự gồm chữ, số hoặc '_' (hỗ trợ tiếng Việt có dấu, không khoảng trắng)."
        )
    ts = achieved_at or datetime.now().astimezone().isoformat(timespec="seconds")
    entry = {
        "name": name,
        "score": max(0, int(score)),
        "nights_won": max(0, min(3, int(nights_won))),
        "achieved_at": ts,
        "seed": int(seed),
    }
    current = load_entries(path)
    current.append(entry)
    ranked = _sort_and_trim(current)
    save_entries(ranked, path)
    return entry, ranked


def export_leaderboard(out_path: Path, path: Path | None = None) -> dict:
    """Export sorted Top-10 leaderboard JSON object {"entries": [...]} to out_path."""
    entries = load_entries(path)
    payload = {"entries": entries}
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return payload
