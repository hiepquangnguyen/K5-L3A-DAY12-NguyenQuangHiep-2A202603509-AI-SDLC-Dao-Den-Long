"""Run Phase 2 (Contract v1.1) verification and emit real, unedited proof artifacts."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF_DIR = ROOT / "docs" / "proof" / "phase-2"
SCENARIOS = ROOT / "tests" / "scenarios"


def _run(cmd: list[str]) -> tuple[subprocess.CompletedProcess[str], float]:
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    return proc, time.perf_counter() - t0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 2 checks and generate proof outputs")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify without modifying docs/proof/phase-2 files (for CI)",
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
        perf_text = ""

        for night, ticks in ((1, 1800), (3, 21600)):
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
                    print(f"Night 3 21,600 ticks exceeded 30s: {max(e1, e2):.3f}s", file=sys.stderr)
                    return 1
                perf_text = "\n".join(
                    [
                        "Command: python -m src.headless --seed 12345 --night 3 --ticks 21600 --snapshot-every 10",
                        f"Run 1 elapsed : {e1:.3f} s",
                        f"Run 2 elapsed : {e2:.3f} s",
                        "Budget        : <= 30.000 s",
                        f"Result        : PASS ({max(e1, e2):.3f} s <= 30.000 s)",
                    ]
                ) + "\n"

        sample_n2 = td_path / "sample_night2.jsonl"
        sample_n3 = td_path / "sample_night3.jsonl"
        s2, _ = _run(
            [
                sys.executable,
                "-m",
                "src.headless",
                "--seed",
                "6",
                "--night",
                "2",
                "--scenario",
                str(SCENARIOS / "p2_night2_launch.scenario.json"),
                "--inputs",
                str(SCENARIOS / "p2_night2_launch.inputs.json"),
                "--ticks",
                "120",
                "--snapshot-every",
                "10",
                "--out",
                str(sample_n2),
            ]
        )
        s3, _ = _run(
            [
                sys.executable,
                "-m",
                "src.headless",
                "--seed",
                "7",
                "--night",
                "3",
                "--scenario",
                str(SCENARIOS / "p2_night3_ramp.scenario.json"),
                "--inputs",
                str(SCENARIOS / "p2_night3_ramp.inputs.json"),
                "--ticks",
                "140",
                "--snapshot-every",
                "10",
                "--out",
                str(sample_n3),
            ]
        )
        if s2.returncode != 0 or s3.returncode != 0:
            print(s2.stderr, s3.stderr, file=sys.stderr)
            return 1

        if not args.check_only:
            PROOF_DIR.mkdir(parents=True, exist_ok=True)
            (PROOF_DIR / "test_report.txt").write_text(report_text, encoding="utf-8", newline="\n")
            (PROOF_DIR / "determinism_diff.txt").write_text(
                "\n".join(det_lines) + "\n", encoding="utf-8", newline="\n"
            )
            (PROOF_DIR / "perf_night3_21600.txt").write_text(perf_text, encoding="utf-8", newline="\n")
            (PROOF_DIR / "sample_night2.jsonl").write_bytes(sample_n2.read_bytes())
            (PROOF_DIR / "sample_night3.jsonl").write_bytes(sample_n3.read_bytes())

    print("Phase 2 verification PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
