"""Phase 3 (TICKET-03 / Contract v1.2) comprehensive unit and headless regression tests."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.sim.config import FUEL_SCALE, TICK_RATE, load_contract
from src.sim.engine import GameSim, InputState, dist_xz

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
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class TestPhase3ChangeRequest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()
        self.tuning = self.contract["tuning"]

    def test_contract_v1_2_durations_and_tuning_keys(self) -> None:
        self.assertEqual(self.contract["contract_version"], "1.2")
        self.assertEqual(self.tuning["night1_duration_s"], 240.0)
        self.assertEqual(self.tuning["night2_duration_s"], 270.0)
        self.assertEqual(self.tuning["night3_duration_s"], 300.0)
        self.assertEqual(self.tuning["fuel_max"], 100)
        self.assertEqual(self.tuning["fuel_decay_per_s"], 1.0)
        self.assertEqual(self.tuning["fuel_per_mote"], 10)
        self.assertEqual(self.tuning["relight_cost"], 5)
        self.assertEqual(self.tuning["win_ratio"], 0.6)
        self.assertEqual(self.tuning["drain_per_s"], 5)
        self.assertEqual(self.tuning["low_fuel_threshold"], 30)
        self.assertEqual(self.tuning["capacity_max"], 20)

    def test_exact_integer_fuel_decay_threshold_30_and_lantern_out(self) -> None:
        sim = GameSim(
            seed=101,
            night=1,
            scenario={
                "player": {"pos": [0, 0, 25], "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "lanterns": [{"id": "L1", "lit": True}],
                "shades": [{"id": "S1", "pos": [0, 1, 31], "state": "chase"}],
                "time_left_s": 240.0,
            },
            contract=self.contract,
        )
        # Step 60 ticks -> fuel == 99.0 exactly (no float drift)
        for _ in range(60):
            sim.step(InputState())
        self.assertEqual(sim.lanterns[0].fuel_60, 5940)
        self.assertEqual(sim.snapshot()["lanterns"][0]["fuel"], 99.0)

        # Step up to tick 4200 (70s): fuel == 30.0 exactly -> SAFE zone MUST STILL hold
        for _ in range(4140):
            sim.step(InputState())
        self.assertEqual(sim.lanterns[0].fuel_60, 30 * FUEL_SCALE)
        self.assertEqual(sim.snapshot()["lanterns"][0]["fuel"], 30.0)
        self.assertGreaterEqual(dist_xz(sim.shades[0].x, sim.shades[0].z, 0.0, 25.0), 6.0)
        self.assertEqual(sim.player.flames, 3)

        # Step 1 more tick (tick 4201): fuel_60 == 1799 < 1800 -> safe zone lost, S1 chases inside 6m
        sim.step(InputState())
        self.assertLess(sim.lanterns[0].fuel_60, 30 * FUEL_SCALE)
        sim.step(InputState())
        self.assertLess(dist_xz(sim.shades[0].x, sim.shades[0].z, 0.0, 25.0), 6.0)

        # Separate clean run verifying lantern extinguishes at exact tick 6000 (100s)
        sim_out = GameSim(
            seed=102,
            night=1,
            scenario={
                "player": {"pos": [0, 0, 0]},
                "random_motes": False,
                "random_shades": False,
                "lanterns": [{"id": "L1", "lit": True}],
            },
            contract=self.contract,
        )
        for _ in range(5999):
            ev = sim_out.step(InputState())
            self.assertNotIn("lantern_out", [e["name"] for e in ev])
        ev_final = sim_out.step(InputState())
        self.assertEqual(
            [e["data"] for e in ev_final if e["name"] == "lantern_out"],
            [{"lantern_id": "L1"}],
        )
        self.assertFalse(sim_out.lanterns[0].lit)
        self.assertEqual(sim_out.lanterns[0].deposited, 0)
        self.assertEqual(sim_out.lanterns[0].fuel_60, 0)
        self.assertTrue(sim_out.lanterns[0].ever_lit)
        snap_out = sim_out.snapshot()["lanterns"][0]
        self.assertEqual(snap_out["fuel"], 0.0)
        self.assertTrue(snap_out["ever_lit"])

    def test_relight_cost_5_refuel_ceil_skip_full_and_safe_restore_push(self) -> None:
        # 1. Relight costs 5 (vs 10), scores +5/mote + 40, sets fuel=100, relit_count=1
        sim = GameSim(
            seed=103,
            night=1,
            scenario={
                "player": {"pos": [0, 0, 24.5], "carried": 8},
                "random_motes": False,
                "random_shades": False,
                "lanterns": [{"id": "L1", "pos": [0, 0, 25], "lit": False, "ever_lit": True}],
            },
            contract=self.contract,
        )
        ev_re = sim.step(InputState(interact=True))
        self.assertEqual([e["name"] for e in ev_re], ["night_start", "deposit", "lantern_lit"])
        self.assertEqual(ev_re[1]["data"], {"lantern_id": "L1", "amount": 5, "deposited": 5})
        self.assertEqual(ev_re[2]["data"], {"lantern_id": "L1", "relight": True})
        self.assertEqual(sim.player.carried, 3)
        self.assertEqual(sim.lanterns[0].fuel_60, 100 * FUEL_SCALE)
        self.assertEqual(sim.lanterns[0].relit_count, 1)
        self.assertEqual(sim.score, 5 * 5 + 40)  # 65
        self.assertEqual(sim.carry_capacity, 12)

        # 2. Full lantern (used=0) ignored -> no event/score; eligible slightly farther lantern picked
        sim_full = GameSim(
            seed=104,
            night=1,
            scenario={
                "player": {"pos": [0, 0, 24.0], "carried": 5},
                "random_motes": False,
                "random_shades": False,
                "lanterns": [
                    {"id": "L1", "pos": [0, 0, 24.5], "lit": True, "fuel": 100.0},
                    {"id": "L2", "pos": [0, 0, 25.5], "lit": True, "fuel": 90.0},
                ],
            },
            contract=self.contract,
        )
        ev_skip: list[dict] = []
        sim_full._step_deposit(ev_skip)
        self.assertEqual(len(ev_skip), 1)
        self.assertEqual(ev_skip[0]["data"]["lantern_id"], "L2")
        self.assertEqual(sim_full.lanterns[0].fuel_60, 100 * FUEL_SCALE)
        self.assertEqual(sim_full.lanterns[1].fuel_60, 100 * FUEL_SCALE)
        self.assertEqual(sim_full.score, 5)

        sim_no_decay = GameSim(
            seed=105,
            night=1,
            scenario={
                "player": {"pos": [0, 0, 24.0], "carried": 5},
                "random_motes": False,
                "random_shades": False,
                "lanterns": [
                    {"id": "L1", "pos": [0, 0, 24.2], "lit": True, "fuel": 100.0},
                ],
            },
            contract=self.contract,
        )
        events_nd: list[dict] = []
        sim_no_decay._step_deposit(events_nd)
        self.assertEqual(events_nd, [])
        self.assertEqual(sim_no_decay.score, 0)
        self.assertEqual(sim_no_decay.player.carried, 5)

        # Boundary ceil((100 - 89)/10) = 2 motes vs ceil((100 - 90)/10) = 1 mote
        sim_ceil = GameSim(
            seed=106,
            night=1,
            scenario={
                "player": {"pos": [0, 0, 24.5], "carried": 5},
                "random_motes": False,
                "random_shades": False,
                "lanterns": [
                    {"id": "L1", "pos": [0, 0, 25.0], "lit": True, "fuel": 89.0},
                ],
            },
            contract=self.contract,
        )
        ev_c = sim_ceil.step(InputState(interact=True))
        ref_ev = [e for e in ev_c if e["name"] == "refuel"]
        self.assertEqual(len(ref_ev), 1)
        self.assertEqual(ref_ev[0]["data"], {"lantern_id": "L1", "amount": 2, "fuel": 100.0})
        self.assertEqual(sim_ceil.player.carried, 3)
        self.assertEqual(sim_ceil.score, 10)  # 2 * 5

        # 3. Refueling weak lantern from 25 -> >= 30 pushes interior Shade to >= 6m in <= 30 ticks without damage
        sim_push = GameSim(
            seed=107,
            night=1,
            scenario={
                "player": {"pos": [0, 0, 25.0], "carried": 2, "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "lanterns": [{"id": "L1", "pos": [0, 0, 25.0], "lit": True, "fuel": 25.0}],
                "shades": [{"id": "S1", "pos": [0, 1, 26.0], "state": "drain", "target_lantern_id": "L1"}],
            },
            contract=self.contract,
        )
        sim_push.step(InputState(interact=True))
        self.assertGreaterEqual(sim_push.lanterns[0].fuel_60, 30 * FUEL_SCALE)
        for _ in range(30):
            sim_push.step(InputState())
        self.assertEqual(sim_push.player.flames, 3)
        self.assertGreaterEqual(dist_xz(sim_push.shades[0].x, sim_push.shades[0].z, 0.0, 25.0), 6.0)

    def test_shade_drain_targeting_stacking_exits_and_pulse_score(self) -> None:
        # 1. Wander picks nearest weak lantern (<30), tie-break smaller id; chase does NOT divert
        sim = GameSim(
            seed=108,
            night=1,
            scenario={
                "player": {"pos": [0, 0, -30], "flames": 3},  # far from shades (>18m)
                "random_motes": False,
                "random_shades": False,
                "lanterns": [
                    {"id": "L1", "pos": [0, 0, 25], "lit": True, "fuel": 20.0},
                    {"id": "L2", "pos": [10, 0, 25], "lit": True, "fuel": 20.0},
                ],
                "shades": [
                    {"id": "S1", "pos": [5, 1, 25], "state": "wander"},  # equidistant (5m) -> picks L1
                    {"id": "S2", "pos": [0, 1, -20], "state": "chase"},  # 10m from player -> stays chase
                ],
            },
            contract=self.contract,
        )
        sim.step(InputState())
        self.assertEqual(sim.shades[0].state, "wander")
        self.assertEqual(sim.shades[0].target_lantern_id, "L1")
        self.assertLess(sim.shades[0].x, 5.0)
        self.assertEqual(sim.shades[1].state, "chase")

        # 2. Two Shades draining L1 stack (-1 passive - 2*5 drain = -11/s), emit fuel_drain every 60 ticks
        sim_drain = GameSim(
            seed=109,
            night=1,
            scenario={
                "player": {"pos": [0, 0, -20], "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "lanterns": [{"id": "L1", "pos": [0, 0, 25], "lit": True, "fuel": 25.0}],
                "shades": [
                    {"id": "S1", "pos": [0, 1, 26.0], "state": "drain", "target_lantern_id": "L1"},
                    {"id": "S2", "pos": [0, 1, 24.0], "state": "drain", "target_lantern_id": "L1"},
                ],
            },
            contract=self.contract,
        )
        all_ev: list[dict] = []
        for _ in range(60):
            all_ev.extend(sim_drain.step(InputState()))
        # 25.0 - 11.0 = 14.0 exact!
        self.assertEqual(sim_drain.lanterns[0].fuel_60, 14 * FUEL_SCALE)
        fd = [e for e in all_ev if e["name"] == "fuel_drain"]
        self.assertEqual([e["data"]["shade_id"] for e in fd], ["S1", "S2"])
        self.assertTrue(all(e["data"]["fuel"] == 14.0 and e["tick"] == 60 for e in fd))

        # 3. Drain -> stays drain at 8m from player, -> chase when player <= 6m, -> wander if distance > 2m
        sim_exit = GameSim(
            seed=110,
            night=1,
            scenario={
                "player": {"pos": [0, 0, 17.0], "flames": 3},  # 8m from S1(0,1,25)
                "random_motes": False,
                "random_shades": False,
                "lanterns": [{"id": "L1", "pos": [0, 0, 25], "lit": True, "fuel": 25.0}],
                "shades": [{"id": "S1", "pos": [0, 1, 25.0], "state": "drain", "target_lantern_id": "L1"}],
            },
            contract=self.contract,
        )
        sim_exit.step(InputState())
        self.assertEqual(sim_exit.shades[0].state, "drain")
        # Move player inside 6m
        sim_exit.player.z = 19.5
        sim_exit.step(InputState())
        self.assertEqual(sim_exit.shades[0].state, "chase")

        # Distance > 2m exit from drain -> wander
        sim_far = GameSim(
            seed=111,
            night=1,
            scenario={
                "player": {"pos": [0, 0, -25], "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "lanterns": [{"id": "L1", "pos": [0, 0, 25], "lit": True, "fuel": 25.0}],
                "shades": [{"id": "S1", "pos": [0, 1, 27.5], "state": "drain", "target_lantern_id": "L1"}],
            },
            contract=self.contract,
        )
        sim_far.step(InputState())
        self.assertEqual(sim_far.shades[0].state, "wander")

        # 4. Pulse on drain Shade awards +15 total (vs +5 non-drain), and stun ends in wander
        sim_pulse = GameSim(
            seed=112,
            night=1,
            scenario={
                "player": {"pos": [0, 0, 23.0], "carried": 5, "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "lanterns": [{"id": "L1", "pos": [0, 0, 25], "lit": True, "fuel": 20.0}],
                "shades": [
                    {"id": "S1", "pos": [0, 1, 26.0], "state": "drain", "target_lantern_id": "L1"},
                    {"id": "S2", "pos": [0, 1, 21.0], "state": "chase"},
                ],
            },
            contract=self.contract,
        )
        sim_pulse.step(InputState(pulse=True))
        self.assertEqual(sim_pulse.score, 20)  # +15 (drain S1) + 5 (chase S2)
        for _ in range(119):
            sim_pulse.step(InputState())
        self.assertEqual(sim_pulse.shades[0].state, "stunned")
        sim_pulse.step(InputState())  # tick 121: stun ends -> wander
        self.assertEqual(sim_pulse.shades[0].state, "wander")
        self.assertEqual(sim_pulse.shades[1].state, "wander")

    def test_dawn_thresholds_nights_1_2_3_step2_out_and_dawn_score_formula(self) -> None:
        # Thresholds: Night 1 = 3/5, Night 2 = 4/6, Night 3 = 5/7
        cases = [
            (1, 3, "won", "dawn_survived"),
            (1, 2, "lost", "dawn"),
            (2, 4, "won", "dawn_survived"),
            (2, 3, "lost", "dawn"),
            (3, 5, "won", "dawn_survived"),
            (3, 4, "lost", "dawn"),
        ]
        for night, lit_count, expected_state, expected_reason in cases:
            sc_lanterns = [{"id": f"L{i}", "lit": True, "fuel": 50.0} for i in range(1, lit_count + 1)]
            sim = GameSim(
                seed=200 + night,
                night=night,
                scenario={
                    "player": {"pos": [0, 0, 0], "flames": 3},
                    "random_motes": False,
                    "random_shades": False,
                    "random_drifters": False,
                    "wind_enabled": False,
                    "lanterns": sc_lanterns,
                    "time_left_s": 1.0 / TICK_RATE,
                },
                contract=self.contract,
            )
            ev = sim.step(InputState())
            self.assertEqual(sim.state, expected_state)
            self.assertEqual(ev[-1]["data"]["reason"], expected_reason)
            if expected_state == "won":
                # Each lit lantern decayed 1 tick (50 - 1/60 -> floor=49), flames=3
                expected_score = lit_count * (50 + 49) + 3 * 50
                self.assertEqual(sim.score, expected_score)
            else:
                self.assertEqual(sim.score, 0)

        # Lantern hitting fuel <= 0 on dawn tick in Step 2 causes dawn loss (< threshold)
        sim_step2_out = GameSim(
            seed=210,
            night=1,
            scenario={
                "player": {"pos": [0, 0, 0], "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "lanterns": [
                    {"id": "L1", "lit": True, "fuel": 0.0},  # goes out on tick 1 Step 2
                    {"id": "L2", "lit": True, "fuel": 50.0},
                    {"id": "L3", "lit": True, "fuel": 50.0},
                ],
                "time_left_s": 1.0 / TICK_RATE,
            },
            contract=self.contract,
        )
        ev_out = sim_step2_out.step(InputState())
        self.assertIn("lantern_out", [e["name"] for e in ev_out])
        self.assertEqual(sim_step2_out.state, "lost")
        self.assertEqual(ev_out[-1]["data"]["reason"], "dawn")

    def test_progressive_carry_capacity_10_to_20_and_reset(self) -> None:
        # Scenario pre-lit lanterns do NOT add to capacity; relights & lights DO add +2 up to 20
        sim = GameSim(
            seed=300,
            night=1,
            scenario={
                "player": {"pos": [0, 0, 25.0], "carried": 20},
                "random_motes": False,
                "random_shades": False,
                "lanterns": [
                    {"id": "L1", "pos": [0, 0, 25.0], "lit": False, "ever_lit": False, "deposited": 9},
                    {"id": "L2", "pos": [0, 0, 26.5], "lit": False, "ever_lit": True, "deposited": 4},
                    {"id": "L3", "lit": True},
                    {"id": "L4", "lit": True},
                ],
            },
            contract=self.contract,
        )
        self.assertEqual(sim.carry_capacity, 10)
        sim.step(InputState(interact=True))  # lights L1 -> successful_lights=1 -> cap 12
        self.assertEqual(sim.carry_capacity, 12)
        sim.step(InputState(interact=False))
        sim.player.z = 26.5  # walk over to L2
        sim.step(InputState(interact=True))  # relights L2 -> successful_lights=2 -> cap 14
        self.assertEqual(sim.carry_capacity, 14)

        # Scenario successful_lights override and max clamp at 20
        sim_cap = GameSim(
            seed=301,
            night=2,
            scenario={
                "player": {"pos": [0, 0, 0], "carried": 0, "successful_lights": 7},
                "random_motes": False,
                "random_shades": False,
                "motes": [[0, 0, 0.2]] * 22,
            },
            contract=self.contract,
        )
        self.assertEqual(sim_cap.carry_capacity, 20)
        sim_cap.step(InputState())
        self.assertEqual(sim_cap.player.carried, 20)

    def test_headless_cli_phase3_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_dr = Path(td) / "drain_refuel.jsonl"
            p_dr = run_headless(
                "--seed",
                "401",
                "--night",
                "1",
                "--scenario",
                str(SCENARIOS / "p3_drain_and_refuel.scenario.json"),
                "--inputs",
                str(SCENARIOS / "p3_drain_and_refuel.inputs.json"),
                "--ticks",
                "260",
                "--snapshot-every",
                "10",
                "--out",
                str(out_dr),
            )
            self.assertEqual(p_dr.returncode, 0, p_dr.stderr)
            rows_dr = parse_jsonl(out_dr)
            ev_names = [r["name"] for r in rows_dr if r["type"] == "event"]
            self.assertIn("fuel_drain", ev_names)
            self.assertIn("pulse", ev_names)
            self.assertIn("refuel", ev_names)

            out_dw = Path(td) / "dawn_win.jsonl"
            p_dw = run_headless(
                "--seed",
                "402",
                "--night",
                "1",
                "--scenario",
                str(SCENARIOS / "p3_dawn_win.scenario.json"),
                "--inputs",
                str(SCENARIOS / "p3_dawn_win.inputs.json"),
                "--ticks",
                "150",
                "--snapshot-every",
                "10",
                "--out",
                str(out_dw),
            )
            self.assertEqual(p_dw.returncode, 0, p_dw.stderr)
            rows_dw = parse_jsonl(out_dw)
            events_dw = [r for r in rows_dw if r["type"] == "event"]
            self.assertEqual(events_dw[-1]["data"], {"result": "won", "reason": "dawn_survived"})
            self.assertEqual(rows_dw[-1]["ticks"], 120)
            self.assertEqual(rows_dw[-1]["state"], "won")


if __name__ == "__main__":
    unittest.main()
