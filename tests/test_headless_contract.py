"""End-to-end Test Contract v1.2 headless CLI tests."""

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
    def test_snapshot_v1_2_schema_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "schema.jsonl"
            proc = run_headless("--seed", "1", "--night", "2", "--ticks", "0", "--out", str(out))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            snap = parse_jsonl(out)[0]
            for key in (
                "type",
                "tick",
                "sim_tick",
                "night",
                "state",
                "time_left_s",
                "score",
                "wind",
                "player",
                "lanterns",
                "shades",
                "motes_active",
                "motes",
                "drifters",
                "charms",
            ):
                self.assertIn(key, snap)
            self.assertEqual(snap["night"], 2)
            self.assertEqual(snap["time_left_s"], 270.0)
            for pkey in (
                "pos",
                "vel",
                "grounded",
                "flames",
                "carried",
                "capacity",
                "invuln",
                "dash_cd_s",
                "pulse_cd_s",
                "charm_s",
            ):
                self.assertIn(pkey, snap["player"])
            self.assertEqual(snap["player"]["capacity"], 10)
            self.assertEqual(len(snap["lanterns"]), 6)
            for lkey in ("id", "pos", "lit", "deposited", "fuel", "ever_lit", "relit_count"):
                self.assertIn(lkey, snap["lanterns"][0])
            self.assertEqual(snap["lanterns"][0]["fuel"], 0.0)
            self.assertFalse(snap["lanterns"][0]["ever_lit"])
            self.assertEqual(snap["lanterns"][0]["relit_count"], 0)
            self.assertEqual(len(snap["charms"]), 1)
            self.assertIn("kind", snap["motes"][0])
            self.assertIn("ttl_s", snap["motes"][0])

    def test_pickup_deposit_no_early_all_lit_win(self) -> None:
        # Migrated from v1.1 (CHANGELOG 1.2.0): TICKET-03 removed early all_lit win and
        # changed per_mote=5; lighting all 5 lanterns boosts capacity -> 12 and stays playing.
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "no_early_win.jsonl"
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
            self.assertEqual(events[0]["name"], "night_start")
            self.assertEqual(names.count("mote_picked"), 10)
            self.assertIn("deposit", names)
            lit_events = [e for e in events if e["name"] == "lantern_lit"]
            self.assertEqual(len(lit_events), 1)
            self.assertEqual(lit_events[0]["data"], {"lantern_id": "L1", "relight": False})
            self.assertNotIn("game_over", names)

            snaps = {s["tick"]: s for s in rows if s["type"] == "snapshot"}
            self.assertEqual(snaps[110]["player"]["capacity"], 12)
            self.assertAlmostEqual(snaps[110]["lanterns"][0]["fuel"], 99.9, places=1)
            self.assertTrue(snaps[110]["lanterns"][0]["ever_lit"])

            end = rows[-1]
            self.assertEqual(end["type"], "end")
            self.assertEqual(end["state"], "playing")
            self.assertEqual(end["ticks"], 300)
            # v1.2: 10*5 + 100 = 150 (no all_lit win bonus yet)
            self.assertEqual(end["score"], 150)

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
                "220",
                "--out",
                str(out),
                "--snapshot-every",
                "10",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            rows = parse_jsonl(out)
            events = [r for r in rows if r["type"] == "event"]
            self.assertEqual([e["name"] for e in events], ["night_start", "pulse"])
            self.assertEqual(events[1]["tick"], 86)
            self.assertEqual(events[1]["data"], {"stunned_ids": ["S1"]})

            snaps = {s["tick"]: s for s in rows if s["type"] == "snapshot"}
            # Tick 60: shade blocked at safe_radius = 6.0m from L1(0,0,25)
            self.assertGreaterEqual(snaps[60]["shades"][0]["pos"][2], 31.0)
            self.assertEqual(snaps[60]["player"]["flames"], 3)
            # Tick 90 & Tick 200: shade stunned (120 ticks from 86 -> 205)
            self.assertEqual(snaps[90]["shades"][0]["state"], "stunned")
            self.assertEqual(snaps[200]["shades"][0]["state"], "stunned")
            # Tick 210: stun ended
            self.assertNotEqual(snaps[210]["shades"][0]["state"], "stunned")

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
                    ("night_start", {"night": 1}),
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
            self.assertEqual([e["name"] for e in events], ["night_start", "game_over"])
            self.assertEqual(events[1]["tick"], 60)
            self.assertEqual(events[1]["data"], {"result": "lost", "reason": "dawn"})
            self.assertEqual(rows[-1], {"type": "end", "ticks": 60, "state": "lost", "score": 0})

    def test_determinism_identical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            for night in (1, 3):
                out1 = Path(td) / f"d{night}_1.jsonl"
                out2 = Path(td) / f"d{night}_2.jsonl"
                for out in (out1, out2):
                    proc = run_headless(
                        "--seed",
                        "12345",
                        "--night",
                        str(night),
                        "--ticks",
                        "1800",
                        "--out",
                        str(out),
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(out1.read_bytes(), out2.read_bytes())

    def test_invalid_inputs_and_scenario_exit_code_2(self) -> None:
        bad_inputs_cases = [
            '{"frames": [{"tick": 5}, {"tick": 5}]}',
            '{"frames": [{"tick": 10}, {"tick": 3}]}',
            '{"frames": [{"tick": 0, "move": [1.5, 0]}]}',
            '{"frames": [{"tick": 0, "pause": "yes"}]}',
            "{not valid json",
        ]
        bad_scenario_cases = [
            '{"lanterns": [{"id": "L99", "lit": true}]}',
            '{"random_motes": "yes"}',
            '{"player": {"pos": [0, 0]}}',
            '{"shades": [{"pos": [0, 0, 0], "state": "avoid"}]}',
            '{"drifters": [{"pos": [0, 0, 0], "state": "bad"}]}',
            '{"lanterns": [{"id": "L1", "lit": true, "fuel": 105}]}',
            '{"lanterns": [{"id": "L1", "ever_lit": "yes"}]}',
            '{"player": {"successful_lights": -1}}',
            '{"shades": [{"pos": [0, 0, 0], "state": "drain", "target_lantern_id": "L99"}]}',
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

            max_digits_bad = Path(td) / "max_digits.json"
            max_digits_bad.write_text('{"frames":[{"tick":' + ("9" * 5000) + "}]}", encoding="utf-8")
            proc_digits = run_headless(
                "--seed", "1", "--night", "1", "--inputs", str(max_digits_bad), "--ticks", "10", "--out", str(out)
            )
            self.assertEqual(proc_digits.returncode, 2)
            self.assertTrue(proc_digits.stderr.strip())

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
            out = Path(td) / "night4.jsonl"
            proc = run_headless("--seed", "1", "--night", "4", "--ticks", "10", "--out", str(out))
            self.assertNotEqual(proc.returncode, 0)
            self.assertTrue(proc.stderr.strip())


if __name__ == "__main__":
    unittest.main()
