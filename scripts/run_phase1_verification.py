"""Run Phase 1 verification and emit real, unedited proof artifacts."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF_DIR = ROOT / "docs" / "proof" / "phase-1"
SCENARIOS = ROOT / "tests" / "scenarios"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 1 checks and generate proof outputs")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify without modifying docs/proof/phase-1 files (for CI)",
    )
    args = parser.parse_args()

    comp = _run([sys.executable, "-m", "compileall", "-q", "src"])
    if comp.returncode != 0:
        print(comp.stdout, comp.stderr, file=sys.stderr)
        return comp.returncode

    ut = _run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    report_text = "\n".join(
        [
            f"$ {sys.executable} -m unittest discover -s tests -v",
            f"exit_code: {ut.returncode}",
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
        run1 = td_path / "det1.jsonl"
        run2 = td_path / "det2.jsonl"
        win_out = td_path / "sample_win.jsonl"

        for target in (run1, run2):
            det = _run(
                [
                    sys.executable,
                    "-m",
                    "src.headless",
                    "--seed",
                    "12345",
                    "--night",
                    "1",
                    "--ticks",
                    "1500",
                    "--snapshot-every",
                    "10",
                    "--out",
                    str(target),
                ]
            )
            if det.returncode != 0:
                print(det.stderr, file=sys.stderr)
                return det.returncode

        b1 = run1.read_bytes()
        b2 = run2.read_bytes()
        h1 = hashlib.sha256(b1).hexdigest()
        h2 = hashlib.sha256(b2).hexdigest()
        if b1 != b2:
            print(f"Determinism check failed: {h1} != {h2}", file=sys.stderr)
            return 1

        win_proc = _run(
            [
                sys.executable,
                "-m",
                "src.headless",
                "--seed",
                "10",
                "--night",
                "1",
                "--scenario",
                str(SCENARIOS / "pickup_and_deposit_win.scenario.json"),
                "--inputs",
                str(SCENARIOS / "pickup_and_deposit_win.inputs.json"),
                "--ticks",
                "300",
                "--snapshot-every",
                "10",
                "--out",
                str(win_out),
            ]
        )
        if win_proc.returncode != 0:
            print(win_proc.stderr, file=sys.stderr)
            return win_proc.returncode

        det_summary = "\n".join(
            [
                "Command: python -m src.headless --seed 12345 --night 1 --ticks 1500 --snapshot-every 10",
                f"Run 1 bytes : {len(b1)}",
                f"Run 1 sha256: {h1}",
                f"Run 2 bytes : {len(b2)}",
                f"Run 2 sha256: {h2}",
                f"Exact match : {b1 == b2}",
            ]
        ) + "\n"

        if not args.check_only:
            PROOF_DIR.mkdir(parents=True, exist_ok=True)
            (PROOF_DIR / "test_report.txt").write_text(report_text, encoding="utf-8", newline="\n")
            (PROOF_DIR / "determinism_diff.txt").write_text(det_summary, encoding="utf-8", newline="\n")
            (PROOF_DIR / "sample_win.jsonl").write_bytes(win_out.read_bytes())

    print("Phase 1 verification PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
