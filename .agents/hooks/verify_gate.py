"""Verification gate hook: ensures code compiles, contract matches config,
all tests pass, and headless simulation is byte-for-byte deterministic.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_step(label: str, cmd: list[str]) -> None:
    print(f"[gate] {label}: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode != 0:
        raise SystemExit(f"[gate] FAILED at '{label}' (exit {proc.returncode})")


def check_contract_consistency() -> None:
    print("[gate] Checking game.contract.json consistency with src/sim/config.py")
    contract_path = ROOT / "game.contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["contract_version"] == "1.0", "contract_version must be 1.0"
    tuning = contract["tuning"]
    assert tuning["lantern_count_night1"] == 5, "lantern_count_night1 must be 5"

    sys.path.insert(0, str(ROOT))
    from src.sim.config import DEFAULT_LANTERN_POSITIONS, load_contract

    loaded = load_contract()
    assert loaded == contract, "load_contract() mismatch"
    assert len(DEFAULT_LANTERN_POSITIONS) == tuning["lantern_count_night1"]


def check_determinism() -> None:
    print("[gate] Checking headless determinism across 2 independent runs")
    with tempfile.TemporaryDirectory() as td:
        out1 = Path(td) / "run1.jsonl"
        out2 = Path(td) / "run2.jsonl"
        base_cmd = [
            sys.executable,
            "-m",
            "src.headless",
            "--seed",
            "12345",
            "--night",
            "1",
            "--ticks",
            "600",
            "--snapshot-every",
            "10",
        ]
        run_step("headless run 1", [*base_cmd, "--out", str(out1)])
        run_step("headless run 2", [*base_cmd, "--out", str(out2)])
        b1 = out1.read_bytes()
        b2 = out2.read_bytes()
        h1 = hashlib.sha256(b1).hexdigest()
        h2 = hashlib.sha256(b2).hexdigest()
        if b1 != b2:
            raise SystemExit(f"[gate] Determinism mismatch: {h1} != {h2}")
        print(f"[gate] Determinism OK (sha256={h1[:16]}...)")


def main() -> int:
    run_step("compileall", [sys.executable, "-m", "compileall", "-q", "src"])
    check_contract_consistency()
    run_step("unittest", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    check_determinism()
    print("[gate] ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
