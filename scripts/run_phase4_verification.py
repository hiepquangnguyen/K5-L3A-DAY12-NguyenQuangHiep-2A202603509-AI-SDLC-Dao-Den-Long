"""Run Phase 4 (Contract v1.3) verification suite and emit proof artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF_DIR = ROOT / "docs" / "proof" / "phase-4"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sim.leaderboard import add_entry  # noqa: E402
from src.soak import run_soak  # noqa: E402


def _run(cmd: list[str], env: dict[str, str] | None = None) -> tuple[subprocess.CompletedProcess[str], float]:
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    return proc, time.perf_counter() - t0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 4 checks and generate proof outputs")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify without modifying docs/proof/phase-4 files (for CI)",
    )
    args = parser.parse_args()

    comp, _ = _run([sys.executable, "-m", "compileall", "-q", "src"])
    if comp.returncode != 0:
        print(comp.stdout, comp.stderr, file=sys.stderr)
        return comp.returncode

    ut, ut_sec = _run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    report_text = "\n".join(
        [
            f"$ {sys.executable} -m unittest discover -s tests -v",
            f"exit_code: {ut.returncode} (elapsed: {ut_sec:.2f}s)",
            "--- stdout ---",
            ut.stdout.strip(),
            "--- stderr ---",
            ut.stderr.strip(),
        ]
    ) + "\n"
    if ut.returncode != 0:
        print(report_text, file=sys.stderr)
        return ut.returncode

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        det_lines: list[str] = []
        perf_lines: list[str] = []

        for night, ticks in ((1, 600), (3, 18000)):
            r1 = td_path / f"n{night}_1.jsonl"
            r2 = td_path / f"n{night}_2.jsonl"
            p1, e1 = _run(
                [
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
                    "--out",
                    str(r1),
                ]
            )
            p2, e2 = _run(
                [
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
                    "--out",
                    str(r2),
                ]
            )
            if p1.returncode != 0 or p2.returncode != 0:
                print(p1.stderr, p2.stderr, file=sys.stderr)
                return 1
            b1 = r1.read_bytes()
            b2 = r2.read_bytes()
            h1 = hashlib.sha256(b1).hexdigest()
            h2 = hashlib.sha256(b2).hexdigest()
            if b1 != b2:
                print(f"Determinism mismatch on Night {night}: {h1} != {h2}", file=sys.stderr)
                return 1
            det_lines.extend(
                [
                    f"=== Night {night} ({ticks} ticks) ===",
                    f"Run 1: {len(b1)} bytes, sha256={h1}, elapsed={e1:.3f}s",
                    f"Run 2: {len(b2)} bytes, sha256={h2}, elapsed={e2:.3f}s",
                    f"Exact match: {b1 == b2}",
                ]
            )
            if night == 3:
                if max(e1, e2) > 30.0:
                    print(f"Night 3 18,000 ticks exceeded 30s: {max(e1, e2):.3f}s", file=sys.stderr)
                    return 1
                perf_lines.extend(
                    [
                        "Command (dawn): python -m src.headless --seed 12345 --night 3 --ticks 18000 --snapshot-every 10",
                        f"Run 1 elapsed : {e1:.3f} s",
                        f"Run 2 elapsed : {e2:.3f} s",
                        "Budget        : <= 30.000 s",
                        f"Result        : PASS ({max(e1, e2):.3f} s <= 30.000 s)",
                    ]
                )

        # Quick 3-night soak check in process
        soak_rep = run_soak(seed=7, nights=3)
        mem_start = soak_rep["mem_start_mb"]
        mem_end = soak_rep["mem_end_mb"]
        if soak_rep["crashes"] != 0 or mem_start is None or mem_end is None or mem_end > 1.2 * mem_start:
            print(f"Soak check failed: {soak_rep}", file=sys.stderr)
            return 1

        # Leaderboard CLI export sample against an isolated temporary JSON store
        tmp_lb = td_path / "sample_lb.json"
        add_entry("Mây_Đêm1", score=890, nights_won=3, seed=42, achieved_at="2026-11-20T18:00:00+07:00", path=tmp_lb)
        add_entry("NgườiGiữĐèn", score=640, nights_won=2, seed=7, achieved_at="2026-11-20T18:15:00+07:00", path=tmp_lb)
        out_lb = td_path / "leaderboard_export_sample.json"
        env = os.environ.copy()
        env["DDL_LEADERBOARD_PATH"] = str(tmp_lb)
        lb_proc, _ = _run([sys.executable, "-m", "src.play", "--export-leaderboard", str(out_lb)], env=env)
        if lb_proc.returncode != 0:
            print(lb_proc.stderr, file=sys.stderr)
            return lb_proc.returncode
        parsed_lb = json.loads(out_lb.read_text(encoding="utf-8"))
        if len(parsed_lb.get("entries", [])) != 2:
            print(f"Unexpected leaderboard sample payload: {parsed_lb}", file=sys.stderr)
            return 1

        if not args.check_only:
            PROOF_DIR.mkdir(parents=True, exist_ok=True)
            (PROOF_DIR / "test_report.txt").write_text(report_text, encoding="utf-8", newline="\n")
            (PROOF_DIR / "determinism_diff.txt").write_text(
                "\n".join(det_lines) + "\n", encoding="utf-8", newline="\n"
            )
            (PROOF_DIR / "perf_night3_dawn.txt").write_text(
                "\n".join(perf_lines) + "\n", encoding="utf-8", newline="\n"
            )
            (PROOF_DIR / "leaderboard_export_sample.json").write_bytes(out_lb.read_bytes())

    print("Phase 4 verification PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
