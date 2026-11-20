"""Verification gate hook (Contract v1.1): ensures code compiles, contract matches config,
all tests pass, Night 1 & 3 headless runs are byte-for-byte deterministic, and 21,600 ticks <= 30s.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_TUNING_KEYS = {
    "player_speed",
    "carry_capacity",
    "lantern_cost",
    "lantern_count_night1",
    "pickup_radius",
    "interact_radius",
    "pulse_cost",
    "pulse_radius",
    "night1_duration_s",
    "night2_duration_s",
    "night3_duration_s",
    "flames",
    "invuln_s",
    "hit_drop_ratio",
    "pulse_stun_s",
    "pulse_push_m",
    "pulse_cooldown_s",
    "safe_radius",
    "shade_speed",
    "shade_hit_radius",
    "fall_enabled",
    "dash_speed",
    "dash_duration_s",
    "dash_cooldown_s",
    "score",
}


def run_step(label: str, cmd: list[str]) -> float:
    print(f"[gate] {label}: {' '.join(cmd)}")
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=ROOT)
    elapsed = time.perf_counter() - t0
    if proc.returncode != 0:
        raise SystemExit(f"[gate] FAILED at '{label}' (exit {proc.returncode})")
    return elapsed


def check_contract_consistency() -> None:
    print("[gate] Checking game.contract.json v1.1 consistency with src/sim/")
    contract_path = ROOT / "game.contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["contract_version"] == "1.1", "contract_version must be 1.1"
    tuning = contract["tuning"]
    missing = REQUIRED_TUNING_KEYS - set(tuning.keys())
    assert not missing, f"Missing tuning keys: {missing}"
    assert tuning["lantern_count_night1"] == 5, "lantern_count_night1 must be 5"

    sys.path.insert(0, str(ROOT))
    from src.sim.config import load_contract
    from src.sim.maps import get_night_map

    loaded = load_contract()
    assert loaded == contract, "load_contract() mismatch"
    assert len(get_night_map(1).lantern_positions) == tuning["lantern_count_night1"]
    assert len(get_night_map(2).lantern_positions) == 6
    assert len(get_night_map(3).lantern_positions) == 7


def check_determinism_and_perf() -> None:
    print("[gate] Checking headless determinism (Night 1 & Night 3) and 21,600-tick performance")
    with tempfile.TemporaryDirectory() as td:
        for night, ticks in ((1, 600), (3, 21600)):
            out1 = Path(td) / f"n{night}_1.jsonl"
            out2 = Path(td) / f"n{night}_2.jsonl"
            base_cmd = [
                sys.executable,
                "-m",
                "src.headless",
                "--seed",
                "12345",
                "--night",
                str(night),
                "--ticks",
                str(ticks),
                "--snapshot-every",
                "10",
            ]
            e1 = run_step(f"headless night {night} run 1", [*base_cmd, "--out", str(out1)])
            e2 = run_step(f"headless night {night} run 2", [*base_cmd, "--out", str(out2)])
            b1 = out1.read_bytes()
            b2 = out2.read_bytes()
            h1 = hashlib.sha256(b1).hexdigest()
            h2 = hashlib.sha256(b2).hexdigest()
            if b1 != b2:
                raise SystemExit(f"[gate] Night {night} determinism mismatch: {h1} != {h2}")
            print(f"[gate] Night {night} ({ticks} ticks) OK in {e1:.2f}s / {e2:.2f}s (sha256={h1[:16]}...)")
            if ticks == 21600 and max(e1, e2) > 30.0:
                raise SystemExit(f"[gate] Night 3 21,600-tick perf exceeded 30s: {max(e1, e2):.2f}s")


def main() -> int:
    run_step("compileall", [sys.executable, "-m", "compileall", "-q", "src"])
    check_contract_consistency()
    run_step("unittest", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    check_determinism_and_perf()
    print("[gate] ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
