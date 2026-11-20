"""Consecutive multi-night headless soak test for Đảo Đèn Lồng (Test Contract v1.3)."""

from __future__ import annotations

import argparse
import gc
import json
import math
import sys
import time
from pathlib import Path

from src.sim.config import TICK_RATE, load_contract
from src.sim.engine import GameSim, InputState
from src.sim.prng import SeededRNG
from src.sim.sysmem import get_rss_mb


def run_soak(seed: int, nights: int, out_path: Path | None = None) -> dict:
    """Run N consecutive Nights cycling 1->2->3 in one process and report RSS & stability."""
    if nights < 1:
        raise ValueError("--nights must be >= 1")

    contract = load_contract()
    results: list[str] = []
    crashes = 0
    mem_start_mb: float | None = None
    mem_end_mb: float | None = None
    t_start = time.perf_counter()

    for idx in range(nights):
        night_num = (idx % 3) + 1
        night_seed = int(seed) + idx
        inp_rng = SeededRNG((night_seed ^ 0x5A5A5A) & 0xFFFFFFFF)

        sim: GameSim | None = None
        try:
            sim = GameSim(seed=night_seed, night=night_num, contract=contract)
            if idx == 0:
                mem_start_mb = get_rss_mb()

            max_ticks = round(sim.initial_time_left_s * TICK_RATE) + 120
            move_x, move_z = 0.0, 0.0

            for tick_idx in range(max_ticks):
                if sim.state in ("won", "lost"):
                    break
                if tick_idx % 30 == 0:
                    ang = inp_rng.uniform(0.0, math.tau)
                    move_x = math.cos(ang)
                    move_z = math.sin(ang)

                inp = InputState(
                    move_x=move_x,
                    move_z=move_z,
                    cam_yaw_deg=0.0,
                    jump=inp_rng.random() < 0.05,
                    dash=inp_rng.random() < 0.03,
                    pulse=inp_rng.random() < 0.02,
                    interact=inp_rng.random() < 0.10,
                    pause=False,
                )
                sim.step(inp)

            results.append(sim.state if sim.state in ("won", "lost") else "lost")
        except Exception as exc:
            crashes += 1
            results.append("crashed")
            print(f"[soak] Night {idx + 1} (night={night_num}, seed={night_seed}) crashed: {exc}", file=sys.stderr)
        finally:
            sim = None
            gc.collect()

    mem_end_mb = get_rss_mb()
    duration_s = round(time.perf_counter() - t_start, 2)

    report = {
        "nights": int(nights),
        "crashes": int(crashes),
        "results": results,
        "mem_start_mb": mem_start_mb,
        "mem_end_mb": mem_end_mb,
        "duration_s": duration_s,
    }

    if out_path is not None:
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")

    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Headless Contract v1.3 multi-night soak test")
    parser.add_argument("--seed", type=int, default=7, help="Base PRNG seed (default: 7)")
    parser.add_argument("--nights", type=int, default=10, help="Consecutive nights to simulate (default: 10)")
    parser.add_argument("--out", type=Path, required=True, help="Output JSON path (e.g. soak.json)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        report = run_soak(seed=args.seed, nights=args.nights, out_path=args.out)
    except Exception as exc:
        print(f"Soak error: {exc}", file=sys.stderr)
        return 1

    print(
        f"[soak] nights={report['nights']} crashes={report['crashes']} "
        f"mem={report['mem_start_mb']}->{report['mem_end_mb']} MiB "
        f"duration={report['duration_s']}s results={report['results']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
