"""End-to-end Test Contract v1.0 headless CLI tests."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "tests" / "scenarios"


def run_headless(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "src.headless", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def parse_jsonl(path: Path) -> list[dict]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


class TestHeadlessContract(unittest.TestCase):
    def test_pickup_deposit_win_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "win.jsonl"
            proc = run_headless(
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
                "--out",
                str(out),
                "--snapshot-every",
                "10",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            rows = parse_jsonl(out)

            self.assertEqual(rows[0]["type"], "snapshot")
            self.assertEqual(rows[0]["tick"], 0)
            self.assertEqual(rows[0]["score"], 0)

            events = [r for r in rows if r["type"] == "event"]
            names = [e["name"] for e in events]
            self.assertEqual(names.count("mote_picked"), 5)
            self.assertIn("deposit", names)
            self.assertIn("lantern_lit", names)
            self.assertEqual(events[-1]["name"], "game_over")
            self.assertEqual(events[-1]["data"], {"result": "won", "reason": "all_lit"})
            self.assertEqual(events[-1]["tick"], 61)

            end = rows[-1]
            self.assertEqual(end["type"], "end")
            self.assertEqual(end["state"], "won")
            self.assertEqual(end["ticks"], 61)
            # 5*10 + 200 + floor(300 - 61/60)*2 + 3*100 = 50 + 200 + 298*2 + 300 = 1146
            self.assertEqual(end["score"], 1146)

    def test_pulse_and_safe_radius_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "pulse.jsonl"
            proc = run_headless(
                "--seed",
                "11",
                "--night",
                "1",
                "--scenario",
                str(SCENARIOS / "pulse_and_safe_radius.scenario.json"),
                "--inputs",
                str(SCENARIOS / "pulse_and_safe_radius.inputs.json"),
                "--ticks",
                "260",
                "--out",
                str(out),
                "--snapshot-every",
                "10",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            rows = parse_jsonl(out)
            events = [r for r in rows if r["type"] == "event"]
            self.assertEqual([e["name"] for e in events], ["pulse"])
            self.assertEqual(events[0]["tick"], 61)
            self.assertEqual(events[0]["data"], {"stunned_ids": ["S1"]})

            snaps = {s["tick"]: s for s in rows if s["type"] == "snapshot"}
            # Tick 60 (pre-pulse): shade blocked by safe_radius at state "avoid"
            self.assertEqual(snaps[60]["shades"][0]["state"], "avoid")
            # Tick 70 & Tick 240: shade stunned
            self.assertEqual(snaps[70]["shades"][0]["state"], "stunned")
            self.assertEqual(snaps[240]["shades"][0]["state"], "stunned")
            # Tick 250: stun (3s = 180 ticks, ended at tick 241) has ended
            self.assertNotEqual(snaps[250]["shades"][0]["state"], "stunned")

    def test_shade_hit_and_no_flames_loss(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "loss.jsonl"
            proc = run_headless(
                "--seed",
                "12",
                "--night",
                "1",
                "--scenario",
                str(SCENARIOS / "shade_hit_and_loss.scenario.json"),
                "--inputs",
                str(SCENARIOS / "shade_hit_and_loss.inputs.json"),
                "--ticks",
                "120",
                "--out",
                str(out),
                "--snapshot-every",
                "10",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            rows = parse_jsonl(out)
            events = [r for r in rows if r["type"] == "event"]
            self.assertEqual(
                [(e["name"], e["data"]) for e in events],
                [
                    ("player_hit", {"by": "shade", "flames": 0, "dropped": 2}),
                    ("game_over", {"result": "lost", "reason": "no_flames"}),
                ],
            )
            self.assertEqual(rows[-1]["type"], "end")
            self.assertEqual(rows[-1]["state"], "lost")

    def test_dawn_timeout_loss(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "dawn.jsonl"
            proc = run_headless(
                "--seed",
                "13",
                "--night",
                "1",
                "--scenario",
                str(SCENARIOS / "dawn_timeout.scenario.json"),
                "--ticks",
                "120",
                "--out",
                str(out),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            rows = parse_jsonl(out)
            events = [r for r in rows if r["type"] == "event"]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["tick"], 60)
            self.assertEqual(events[0]["name"], "game_over")
            self.assertEqual(events[0]["data"], {"result": "lost", "reason": "dawn"})
            self.assertEqual(rows[-1], {"type": "end", "ticks": 60, "state": "lost", "score": 0})

    def test_determinism_identical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out1 = Path(td) / "d1.jsonl"
            out2 = Path(td) / "d2.jsonl"
            for out in (out1, out2):
                proc = run_headless(
                    "--seed",
                    "12345",
                    "--night",
                    "1",
                    "--ticks",
                    "1500",
                    "--out",
                    str(out),
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(out1.read_bytes(), out2.read_bytes())

    def test_invalid_inputs_and_scenario_exit_code_2(self) -> None:
        bad_inputs_cases = [
            '{"frames": [{"tick": 5}, {"tick": 5}]}',  # duplicate tick
            '{"frames": [{"tick": 10}, {"tick": 3}]}',  # decreasing tick
            '{"frames": [{"tick": 0, "move": [1.5, 0]}]}',  # move out of [-1, 1]
            "{not valid json",
        ]
        bad_scenario_cases = [
            '{"lanterns": [{"id": "L99", "lit": true}]}',
            '{"random_motes": "yes"}',
            '{"player": {"pos": [0, 0]}}',
        ]
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "bad.jsonl"
            for idx, payload in enumerate(bad_inputs_cases):
                inp = Path(td) / f"bad_in_{idx}.json"
                inp.write_text(payload, encoding="utf-8")
                proc = run_headless(
                    "--seed", "1", "--night", "1", "--inputs", str(inp), "--ticks", "10", "--out", str(out)
                )
                self.assertEqual(proc.returncode, 2, f"Expected exit 2 for bad input #{idx}")
                self.assertTrue(proc.stderr.strip())

            for idx, payload in enumerate(bad_scenario_cases):
                sc = Path(td) / f"bad_sc_{idx}.json"
                sc.write_text(payload, encoding="utf-8")
                proc = run_headless(
                    "--seed", "1", "--night", "1", "--scenario", str(sc), "--ticks", "10", "--out", str(out)
                )
                self.assertEqual(proc.returncode, 2, f"Expected exit 2 for bad scenario #{idx}")
                self.assertTrue(proc.stderr.strip())

            # Non-UTF-8 bytes & huge integer overflow (10**400) -> exit code 2
            bin_bad = Path(td) / "binary.json"
            bin_bad.write_bytes(b"\xff\xfe\x00\x80")
            proc_bin = run_headless(
                "--seed", "1", "--night", "1", "--inputs", str(bin_bad), "--ticks", "10", "--out", str(out)
            )
            self.assertEqual(proc_bin.returncode, 2)
            self.assertTrue(proc_bin.stderr.strip())

            huge_bad = Path(td) / "huge.json"
            huge_bad.write_text('{"frames":[{"tick":0,"cam_yaw_deg":' + ("9" * 400) + "}]}", encoding="utf-8")
            proc_huge = run_headless(
                "--seed", "1", "--night", "1", "--inputs", str(huge_bad), "--ticks", "10", "--out", str(out)
            )
            self.assertEqual(proc_huge.returncode, 2)
            self.assertTrue(proc_huge.stderr.strip())

    def test_ticks_zero_and_help_exit_zero(self) -> None:
        help_proc = run_headless("--help")
        self.assertEqual(help_proc.returncode, 0)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "zero.jsonl"
            proc = run_headless("--seed", "1", "--night", "1", "--ticks", "0", "--out", str(out))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            rows = parse_jsonl(out)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["type"], "snapshot")
            self.assertEqual(rows[0]["tick"], 0)
            self.assertEqual(rows[1], {"type": "end", "ticks": 0, "state": "playing", "score": 0})

    def test_unsupported_night_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "night2.jsonl"
            proc = run_headless("--seed", "1", "--night", "2", "--ticks", "10", "--out", str(out))
            self.assertNotEqual(proc.returncode, 0)
            self.assertTrue(proc.stderr.strip())


if __name__ == "__main__":
    unittest.main()
