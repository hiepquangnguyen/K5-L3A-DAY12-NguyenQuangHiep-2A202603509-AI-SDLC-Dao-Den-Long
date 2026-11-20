"""Strict validation for Test Contract v1.0 --inputs and --scenario JSON files."""

from __future__ import annotations

import json
import math
from pathlib import Path


class ContractFormatError(ValueError):
    """Raised when an inputs or scenario file violates Test Contract v1.0 (exit code 2)."""


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_num(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def _load_json(path: Path, kind: str) -> object:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractFormatError(f"Cannot read {kind} file '{path}': {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContractFormatError(f"Invalid JSON in {kind} file '{path}': {exc}") from exc


def _parse_vec3(value: object, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 3 or not all(_is_num(x) for x in value):
        raise ContractFormatError(f"{label} must be a 3-number array [x, y, z]")
    return [float(value[0]), float(value[1]), float(value[2])]


def parse_inputs_file(path: Path) -> list[dict]:
    """Validate and normalize a Test Contract v1.0 inputs JSON file."""
    data = _load_json(path, "inputs")
    if not isinstance(data, dict):
        raise ContractFormatError("Inputs root must be a JSON object")
    if "frames" not in data or not isinstance(data["frames"], list):
        raise ContractFormatError("Inputs object must contain a 'frames' array")

    parsed: list[dict] = []
    prev_tick: int | None = None
    for idx, frame in enumerate(data["frames"]):
        if not isinstance(frame, dict):
            raise ContractFormatError(f"frames[{idx}] must be an object")
        if "tick" not in frame or not _is_int(frame["tick"]) or frame["tick"] < 0:
            raise ContractFormatError(f"frames[{idx}].tick must be a non-negative integer")
        tick = int(frame["tick"])
        if prev_tick is not None and tick <= prev_tick:
            raise ContractFormatError(
                f"frames[{idx}].tick ({tick}) must be strictly greater than previous tick ({prev_tick})"
            )
        prev_tick = tick

        norm: dict = {"tick": tick}
        if "move" in frame:
            mv = frame["move"]
            if not isinstance(mv, list) or len(mv) != 2 or not all(_is_num(x) for x in mv):
                raise ContractFormatError(f"frames[{idx}].move must be [x, z] of finite numbers")
            mx, mz = float(mv[0]), float(mv[1])
            if not (-1.0 <= mx <= 1.0 and -1.0 <= mz <= 1.0):
                raise ContractFormatError(f"frames[{idx}].move components must be within [-1, 1]")
            norm["move"] = [mx, mz]

        if "cam_yaw_deg" in frame:
            if not _is_num(frame["cam_yaw_deg"]):
                raise ContractFormatError(f"frames[{idx}].cam_yaw_deg must be a finite number")
            norm["cam_yaw_deg"] = float(frame["cam_yaw_deg"])

        for btn in ("jump", "interact", "pulse", "dash"):
            if btn in frame:
                if not isinstance(frame[btn], bool):
                    raise ContractFormatError(f"frames[{idx}].{btn} must be a boolean")
                norm[btn] = frame[btn]

        parsed.append(norm)
    return parsed


def _parse_scenario_player(player: object) -> dict:
    if not isinstance(player, dict):
        raise ContractFormatError("scenario.player must be an object")
    out: dict = {}
    if "pos" in player:
        out["pos"] = _parse_vec3(player["pos"], "scenario.player.pos")
    for int_field in ("carried", "flames"):
        if int_field in player:
            if not _is_int(player[int_field]) or player[int_field] < 0:
                raise ContractFormatError(f"scenario.player.{int_field} must be a non-negative integer")
            out[int_field] = int(player[int_field])
    return out


def _parse_scenario_motes(motes: object) -> list[dict]:
    if not isinstance(motes, list):
        raise ContractFormatError("scenario.motes must be an array")
    parsed: list[dict] = []
    for idx, item in enumerate(motes):
        if isinstance(item, list):
            parsed.append({"pos": _parse_vec3(item, f"scenario.motes[{idx}]")})
        elif isinstance(item, dict):
            if "pos" not in item:
                raise ContractFormatError(f"scenario.motes[{idx}] object requires 'pos'")
            entry: dict = {"pos": _parse_vec3(item["pos"], f"scenario.motes[{idx}].pos")}
            if "id" in item:
                if not isinstance(item["id"], str) or not item["id"]:
                    raise ContractFormatError(f"scenario.motes[{idx}].id must be a non-empty string")
                entry["id"] = item["id"]
            parsed.append(entry)
        else:
            raise ContractFormatError(f"scenario.motes[{idx}] must be [x,y,z] or object")
    return parsed


def _parse_scenario_shades(shades: object) -> list[dict]:
    if not isinstance(shades, list):
        raise ContractFormatError("scenario.shades must be an array")
    parsed: list[dict] = []
    for idx, item in enumerate(shades):
        if not isinstance(item, dict) or "pos" not in item:
            raise ContractFormatError(f"scenario.shades[{idx}] must be an object with 'pos'")
        entry: dict = {"pos": _parse_vec3(item["pos"], f"scenario.shades[{idx}].pos")}
        if "id" in item:
            if not isinstance(item["id"], str) or not item["id"]:
                raise ContractFormatError(f"scenario.shades[{idx}].id must be a non-empty string")
            entry["id"] = item["id"]
        if "state" in item:
            if not isinstance(item["state"], str) or not item["state"]:
                raise ContractFormatError(f"scenario.shades[{idx}].state must be a non-empty string")
            entry["state"] = item["state"]
        parsed.append(entry)
    return parsed


def _parse_scenario_lanterns(lanterns: object, valid_lantern_ids: set[str]) -> list[dict]:
    if not isinstance(lanterns, list):
        raise ContractFormatError("scenario.lanterns must be an array")
    parsed: list[dict] = []
    for idx, item in enumerate(lanterns):
        if not isinstance(item, dict):
            raise ContractFormatError(f"scenario.lanterns[{idx}] must be an object")
        lid = item.get("id")
        if not isinstance(lid, str) or lid not in valid_lantern_ids:
            raise ContractFormatError(
                f"scenario.lanterns[{idx}].id must be one of {sorted(valid_lantern_ids)}"
            )
        entry: dict = {"id": lid}
        if "pos" in item:
            entry["pos"] = _parse_vec3(item["pos"], f"scenario.lanterns[{idx}].pos")
        if "deposited" in item:
            if not _is_int(item["deposited"]) or item["deposited"] < 0:
                raise ContractFormatError(
                    f"scenario.lanterns[{idx}].deposited must be a non-negative integer"
                )
            entry["deposited"] = int(item["deposited"])
        if "lit" in item:
            if not isinstance(item["lit"], bool):
                raise ContractFormatError(f"scenario.lanterns[{idx}].lit must be a boolean")
            entry["lit"] = item["lit"]
        parsed.append(entry)
    return parsed


def parse_scenario_file(path: Path, valid_lantern_ids: set[str]) -> dict:
    """Validate and normalize a Test Contract v1.0 scenario JSON file."""
    data = _load_json(path, "scenario")
    if not isinstance(data, dict):
        raise ContractFormatError("Scenario root must be a JSON object")

    parsed: dict = {}
    if "player" in data:
        parsed["player"] = _parse_scenario_player(data["player"])
    for flag in ("random_motes", "random_shades"):
        if flag in data:
            if not isinstance(data[flag], bool):
                raise ContractFormatError(f"scenario.{flag} must be a boolean")
            parsed[flag] = data[flag]
    if "motes" in data:
        parsed["motes"] = _parse_scenario_motes(data["motes"])
    if "shades" in data:
        parsed["shades"] = _parse_scenario_shades(data["shades"])
    if "lanterns" in data:
        parsed["lanterns"] = _parse_scenario_lanterns(data["lanterns"], valid_lantern_ids)
    if "time_left_s" in data:
        if not _is_num(data["time_left_s"]) or float(data["time_left_s"]) < 0.0:
            raise ContractFormatError("scenario.time_left_s must be a non-negative finite number")
        parsed["time_left_s"] = float(data["time_left_s"])

    return parsed
