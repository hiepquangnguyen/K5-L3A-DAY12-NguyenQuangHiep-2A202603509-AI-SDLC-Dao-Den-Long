"""Test Contract v1.2 headless CLI runner for Đảo Đèn Lồng (Nights 1, 2, 3)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.sim.config import load_contract
from src.sim.engine import GameSim, InputState
from src.sim.maps import get_night_map
from src.sim.validation import ContractFormatError, parse_inputs_file, parse_scenario_file


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Headless Test Contract v1.2 runner")
    parser.add_argument("--seed", type=int, required=True, help="Deterministic PRNG seed")
    parser.add_argument("--night", type=int, required=True, help="Night number (1, 2, or 3)")
    parser.add_argument("--scenario", type=Path, default=None, help="Optional scenario JSON path")
    parser.add_argument("--inputs", type=Path, default=None, help="Optional inputs JSON path")
    parser.add_argument("--ticks", type=int, required=True, help="Maximum simulation steps")
    parser.add_argument("--out", type=Path, required=True, help="Output JSONL path")
    parser.add_argument(
        "--snapshot-every",
        type=int,
        default=10,
        help="Snapshot interval in ticks (default: 10)",
    )
    return parser


def _dump_line(obj: dict) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code is None or exc.code == 0:
            return 0
        return int(exc.code) if isinstance(exc.code, int) else 1

    if args.ticks < 0:
        print("Error: --ticks must be >= 0", file=sys.stderr)
        return 1
    if args.snapshot_every < 1:
        print("Error: --snapshot-every must be >= 1", file=sys.stderr)
        return 1
    if args.night not in (1, 2, 3):
        print(f"Error: unsupported --night {args.night}; expected 1, 2, or 3", file=sys.stderr)
        return 1

    night_map = get_night_map(args.night)

    try:
        scenario = (
            parse_scenario_file(args.scenario, set(night_map.valid_lantern_ids))
            if args.scenario is not None
            else None
        )
        frames = parse_inputs_file(args.inputs) if args.inputs is not None else []
    except ContractFormatError as exc:
        print(f"Format error: {exc}", file=sys.stderr)
        return 2

    try:
        contract = load_contract()
        sim = GameSim(seed=args.seed, night=args.night, scenario=scenario, contract=contract)
    except Exception as exc:
        print(f"Simulation initialization error: {exc}", file=sys.stderr)
        return 1

    frames_by_tick = {frame["tick"]: frame for frame in frames}
    inp = InputState()

    try:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8", newline="\n") as out_fh:
            out_fh.write(_dump_line(sim.snapshot()) + "\n")

            for step_tick in range(args.ticks):
                if sim.state in ("won", "lost"):
                    break
                frame = frames_by_tick.get(step_tick)
                if frame is not None:
                    if "move" in frame:
                        inp.move_x, inp.move_z = frame["move"][0], frame["move"][1]
                    if "cam_yaw_deg" in frame:
                        inp.cam_yaw_deg = frame["cam_yaw_deg"]
                    if "jump" in frame:
                        inp.jump = frame["jump"]
                    if "interact" in frame:
                        inp.interact = frame["interact"]
                    if "pulse" in frame:
                        inp.pulse = frame["pulse"]
                    if "dash" in frame:
                        inp.dash = frame["dash"]
                    if "pause" in frame:
                        inp.pause = frame["pause"]

                events = sim.step(inp)
                for ev in events:
                    out_fh.write(_dump_line(ev) + "\n")

                if (step_tick + 1) % args.snapshot_every == 0:
                    out_fh.write(_dump_line(sim.snapshot()) + "\n")

            out_fh.write(_dump_line(sim.end_record()) + "\n")
    except OSError as exc:
        print(f"I/O error writing '{args.out}': {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
