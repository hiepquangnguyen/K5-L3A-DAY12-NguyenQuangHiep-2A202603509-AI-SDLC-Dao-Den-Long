"""Phase 2 (Ticket-02 / Contract v1.1) headless scenario, feature, and performance tests."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from src.sim.config import load_contract
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


class TestPhase2Features(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def test_dash_air_altitude_hold_and_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "dash.jsonl"
            proc = run_headless(
                "--seed",
                "1",
                "--night",
                "1",
                "--scenario",
                str(SCENARIOS / "p2_dash_and_air.scenario.json"),
                "--inputs",
                str(SCENARIOS / "p2_dash_and_air.inputs.json"),
                "--ticks",
                "30",
                "--snapshot-every",
                "1",
                "--out",
                str(out),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            rows = parse_jsonl(out)
            events = [r for r in rows if r["type"] == "event"]
            self.assertIn(("dash", {}), [(e["name"], e["data"]) for e in events])

            snaps = {s["tick"]: s for s in rows if s["type"] == "snapshot"}
            # Tick 1 jumped; Tick 2 started dash -> holds Y constant for 12 ticks (tick 2..13)
            y_at_dash = snaps[2]["player"]["pos"][1]
            self.assertGreater(y_at_dash, 0.0)
            for t in range(3, 14):
                self.assertAlmostEqual(snaps[t]["player"]["pos"][1], y_at_dash, places=3)
            # Moved ~2.8m along +Z (facing direction)
            self.assertAlmostEqual(snaps[13]["player"]["pos"][2], 2.8, places=2)
            # Cooldown started at 1.5s from tick 2
            self.assertGreater(snaps[2]["player"]["dash_cd_s"], 1.3)

    def test_fall_off_island_ignores_invuln_respawns_and_loses_on_last_flame(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "fall.jsonl"
            proc = run_headless(
                "--seed",
                "2",
                "--night",
                "1",
                "--scenario",
                str(SCENARIOS / "p2_fall_and_respawn.scenario.json"),
                "--inputs",
                str(SCENARIOS / "p2_fall_and_respawn.inputs.json"),
                "--ticks",
                "160",
                "--snapshot-every",
                "10",
                "--out",
                str(out),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            rows = parse_jsonl(out)
            events = [r for r in rows if r["type"] == "event"]
            hits = [e for e in events if e["name"] == "player_hit"]
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0]["data"], {"by": "fall", "flames": 1, "dropped": 0, "lost": 6})

            snaps = {s["tick"]: s for s in rows if s["type"] == "snapshot"}
            # After 60-tick respawn delay, back at (0,0,0) with invuln=True and carried=0
            self.assertEqual(snaps[150]["player"]["pos"], [0.0, 0.0, 0.0])
            self.assertTrue(snaps[150]["player"]["invuln"])
            self.assertEqual(snaps[150]["player"]["carried"], 0)

        # Last flame fall ends immediately without respawn
        sim = GameSim(
            seed=3,
            night=1,
            scenario={"player": {"pos": [0, -10.5, 42], "flames": 1, "carried": 4}, "random_motes": False, "random_shades": False},
            contract=self.contract,
        )
        ev = sim.step(InputState())
        self.assertEqual(sim.state, "lost")
        self.assertEqual([e["name"] for e in ev], ["night_start", "player_hit", "game_over"])
        self.assertEqual(ev[1]["data"]["lost"], 4)
        self.assertEqual(ev[2]["data"], {"result": "lost", "reason": "no_flames"})

    def test_pause_freezes_sim_tick_timers_and_ttl(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "pause.jsonl"
            proc = run_headless(
                "--seed",
                "4",
                "--night",
                "1",
                "--scenario",
                str(SCENARIOS / "p2_pause_resume.scenario.json"),
                "--inputs",
                str(SCENARIOS / "p2_pause_resume.inputs.json"),
                "--ticks",
                "90",
                "--snapshot-every",
                "10",
                "--out",
                str(out),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            rows = parse_jsonl(out)
            events = [r for r in rows if r["type"] == "event"]
            self.assertIn(("paused", {}), [(e["name"], e["data"]) for e in events])
            self.assertIn(("resumed", {}), [(e["name"], e["data"]) for e in events])

            snaps = {s["tick"]: s for s in rows if s["type"] == "snapshot"}
            self.assertEqual(snaps[20]["state"], "paused")
            self.assertEqual(snaps[50]["state"], "paused")
            self.assertEqual(snaps[20]["sim_tick"], 10)
            self.assertEqual(snaps[50]["sim_tick"], 10)
            self.assertEqual(snaps[50]["time_left_s"], snaps[20]["time_left_s"])
            self.assertEqual(snaps[50]["player"]["dash_cd_s"], snaps[20]["player"]["dash_cd_s"])
            self.assertEqual(snaps[50]["motes"][0]["ttl_s"], snaps[20]["motes"][0]["ttl_s"])
            self.assertEqual(snaps[80]["state"], "playing")
            self.assertGreater(snaps[80]["sim_tick"], 10)

    def test_night2_bridge_and_launch_pad(self) -> None:
        # 1. Bamboo bridge x in [26, 44], z in [-2, 2]
        sim_bridge = GameSim(
            seed=5,
            night=2,
            scenario={"player": {"pos": [25, 0, 0]}, "random_motes": False, "random_shades": False, "random_drifters": False},
            contract=self.contract,
        )
        for _ in range(200):
            sim_bridge.step(InputState(move_x=1.0, move_z=0.0))
        self.assertGreater(sim_bridge.player.x, 44.0)
        self.assertEqual(sim_bridge.player.y, 0.0)
        self.assertEqual(sim_bridge.player.flames, 3)

        # 2. Launch pad (20,0,18) launches to Island B (70,0) ignoring opposite input
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "n2_launch.jsonl"
            proc = run_headless(
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
                str(out),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            snaps = [r for r in parse_jsonl(out) if r["type"] == "snapshot"]
            final_pos = snaps[-1]["player"]["pos"]
            self.assertLess(math.hypot(final_pos[0] - 70.0, final_pos[2]), 28.0)
            self.assertEqual(final_pos[1], 0.0)

    def test_night3_ramp_cliffs_launch_bell_tower_and_wind(self) -> None:
        # 1. Climb 30-degree ramp smoothly onto Tier 1 (Y=3)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "n3_ramp.jsonl"
            proc = run_headless(
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
                str(out),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            snaps = [r for r in parse_jsonl(out) if r["type"] == "snapshot"]
            self.assertEqual(snaps[-1]["player"]["pos"][1], 3.0)

        # 2. Vertical cliff blocks walking directly onto Tier 1 without ramp
        sim_cliff = GameSim(
            seed=8,
            night=3,
            scenario={"player": {"pos": [0, 0, 26]}, "random_motes": False, "random_shades": False, "random_drifters": False, "wind_enabled": False},
            contract=self.contract,
        )
        for _ in range(60):
            sim_cliff.step(InputState(move_z=-1.0))
        self.assertEqual(sim_cliff.player.y, 0.0)
        self.assertGreaterEqual(sim_cliff.player.z, 24.0)

        # 3. Launch pad (0,3,13) lands on Tier 2 (Y=6), and Bell Tower blocks center r < 2
        sim_pad = GameSim(
            seed=9,
            night=3,
            scenario={"player": {"pos": [0, 3, 14.5]}, "random_motes": False, "random_shades": False, "random_drifters": False, "wind_enabled": False},
            contract=self.contract,
        )
        for _ in range(25):
            sim_pad.step(InputState(move_z=-1.0))
        for _ in range(75):
            sim_pad.step(InputState())
        self.assertEqual(sim_pad.player.y, 6.0)
        self.assertLessEqual(math.hypot(sim_pad.player.x, sim_pad.player.z), 8.0)
        # Walk toward Bell Tower center (0, 6, 0) -> blocked at r >= 2.0
        for _ in range(120):
            sim_pad.step(InputState(move_z=-1.0))
        self.assertGreaterEqual(math.hypot(sim_pad.player.x, sim_pad.player.z), 2.0 - 1e-4)

        # 4. Wind activates at sim_tick 1800 and pushes stationary player 2.0 m/s
        sim_wind = GameSim(
            seed=10,
            night=3,
            scenario={"player": {"pos": [0, 0, -10]}, "random_motes": False, "random_shades": False, "random_drifters": False, "wind_enabled": True},
            contract=self.contract,
        )
        for _ in range(1799):
            sim_wind.step(InputState())
        self.assertFalse(sim_wind.wind_active)
        self.assertTrue(sim_wind.wind_warning)
        sim_wind.step(InputState())
        self.assertTrue(sim_wind.wind_active)
        p0 = (sim_wind.player.x, sim_wind.player.z)
        for _ in range(60):
            sim_wind.step(InputState())
        moved = math.hypot(sim_wind.player.x - p0[0], sim_wind.player.z - p0[1])
        self.assertAlmostEqual(moved, 2.0, places=2)

    def test_drifter_steal_ignores_invuln_safe_zone_and_pulse_drops(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "drifter.jsonl"
            proc = run_headless(
                "--seed",
                "11",
                "--night",
                "2",
                "--scenario",
                str(SCENARIOS / "p2_drifter_steal_drop.scenario.json"),
                "--inputs",
                str(SCENARIOS / "p2_drifter_steal_drop.inputs.json"),
                "--ticks",
                "220",
                "--snapshot-every",
                "10",
                "--out",
                str(out),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            rows = parse_jsonl(out)
            events = [r for r in rows if r["type"] == "event"]
            names = [e["name"] for e in events]
            self.assertIn("drifter_steal", names)
            self.assertIn("drifter_drop", names)

            steal = next(e for e in events if e["name"] == "drifter_steal")
            self.assertEqual(steal["data"], {"drifter_id": "D1", "amount": 3, "carried": 4})

            drop = next(e for e in events if e["name"] == "drifter_drop")
            self.assertEqual(drop["data"], {"drifter_id": "D1", "amount": 3})

            snaps = {s["tick"]: s for s in rows if s["type"] == "snapshot"}
            # Dropped motes created at tick 56, still present at tick 60 with kind="dropped"
            dropped_motes = [m for m in snaps[60]["motes"] if m["kind"] == "dropped"]
            self.assertEqual(len(dropped_motes), 3)
            # Drifter removed 120 ticks after pulse drop (56 + 120 = 176)
            self.assertEqual(snaps[180]["drifters"], [])

        # Pulse during chase sends drifter to flee without stealing
        sim_c = GameSim(
            seed=12,
            night=2,
            scenario={
                "player": {"pos": [0, 0, 0], "carried": 6},
                "random_motes": False,
                "random_shades": False,
                "random_drifters": False,
                "drifters": [{"id": "D1", "pos": [0, 1.2, 4.0], "state": "chase"}],
            },
            contract=self.contract,
        )
        ev = sim_c.step(InputState(pulse=True))
        self.assertEqual([e["name"] for e in ev], ["night_start", "pulse"])
        self.assertEqual(sim_c.drifters[0].state, "flee")
        self.assertEqual(sim_c.drifters[0].stolen, 0)

    def test_charm_boosts_speed_removes_dash_cooldown_and_respawns(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "charm.jsonl"
            proc = run_headless(
                "--seed",
                "13",
                "--night",
                "2",
                "--scenario",
                str(SCENARIOS / "p2_charm_wind.scenario.json"),
                "--inputs",
                str(SCENARIOS / "p2_charm_wind.inputs.json"),
                "--ticks",
                "650",
                "--snapshot-every",
                "10",
                "--out",
                str(out),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            rows = parse_jsonl(out)
            events = [r for r in rows if r["type"] == "event"]
            self.assertIn("charm_picked", [e["name"] for e in events])
            # Dashed twice rapidly at tick 20 and tick 35 (only 15 ticks apart < 90 cooldown!)
            dashes = [e for e in events if e["name"] == "dash"]
            self.assertEqual(len(dashes), 2)

            snaps = {s["tick"]: s for s in rows if s["type"] == "snapshot"}
            self.assertGreater(snaps[30]["player"]["charm_s"], 0.0)
            self.assertEqual(snaps[30]["player"]["dash_cd_s"], 0.0)
            # Expired by tick 630
            self.assertEqual(snaps[630]["player"]["charm_s"], 0.0)

    def test_safe_push_30_ticks_and_obstacle_knockback_stop(self) -> None:
        # 1. Lighting a lantern pushes an interior shade out <= 30 ticks without dealing damage
        sim = GameSim(
            seed=14,
            night=1,
            scenario={
                "player": {"pos": [0, 0, 25], "carried": 10, "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "shades": [{"id": "S1", "pos": [0, 0, 26], "state": "chase"}],
            },
            contract=self.contract,
        )
        sim.step(InputState(interact=True))
        self.assertTrue(sim.lanterns[0].lit)
        for _ in range(30):
            sim.step(InputState())
        self.assertEqual(sim.player.flames, 3)
        self.assertGreaterEqual(dist_xz(sim.shades[0].x, sim.shades[0].z, 0.0, 25.0), 6.0)

        # 2. Knockback stops on Bell Tower obstacle (Night 3 Tier 2)
        sim_obs = GameSim(
            seed=15,
            night=3,
            scenario={
                "player": {"pos": [0, 6, 4], "carried": 5, "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "random_drifters": False,
                "wind_enabled": False,
                "shades": [{"id": "S1", "pos": [0, 7, 3], "state": "chase"}],
            },
            contract=self.contract,
        )
        sim_obs.step(InputState(pulse=True))
        for _ in range(15):
            sim_obs.step(InputState())
        self.assertGreaterEqual(math.hypot(sim_obs.shades[0].x, sim_obs.shades[0].z), 2.0 - 1e-4)

    def test_night3_full_21600_ticks_under_30s_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out1 = Path(td) / "perf1.jsonl"
            out2 = Path(td) / "perf2.jsonl"
            t0 = time.perf_counter()
            p1 = run_headless("--seed", "777", "--night", "3", "--ticks", "21600", "--out", str(out1))
            elapsed = time.perf_counter() - t0
            self.assertEqual(p1.returncode, 0, p1.stderr)
            self.assertLessEqual(elapsed, 30.0, f"Night 3 21,600 ticks took {elapsed:.2f}s > 30s")

            p2 = run_headless("--seed", "777", "--night", "3", "--ticks", "21600", "--out", str(out2))
            self.assertEqual(p2.returncode, 0, p2.stderr)
            self.assertEqual(out1.read_bytes(), out2.read_bytes())

    def test_audit_regressions_ramp_side_idle_drifter_charm_speed_and_outcome_order(self) -> None:
        # 1. Night 3 ramp side-wall blocks entering underneath from Tier 0 (s=26, t=1.6 -> t<1.5)
        r_ang = math.radians(30.0)
        ux, uz = math.cos(r_ang), math.sin(r_ang)
        tx, tz = -math.sin(r_ang), math.cos(r_ang)
        start_x, start_z = 26.0 * ux + 2.0 * tx, 26.0 * uz + 2.0 * tz
        sim_ramp = GameSim(
            seed=16,
            night=3,
            scenario={"player": {"pos": [start_x, 0, start_z]}, "random_motes": False, "random_shades": False, "random_drifters": False, "wind_enabled": False},
            contract=self.contract,
        )
        for _ in range(30):
            sim_ramp.step(InputState(move_x=-tx, move_z=-tz))
        self.assertEqual(sim_ramp.player.y, 0.0)
        # Verify player remained outside ramp side wall (|t| > 1.5)
        t_after = -sim_ramp.player.x * math.sin(r_ang) + sim_ramp.player.z * math.cos(r_ang)
        self.assertGreater(abs(t_after), 1.49)

        # 2. Idle drifter does NOT steal when carried < 5
        sim_idle = GameSim(
            seed=17,
            night=2,
            scenario={
                "player": {"pos": [0, 0, 0], "carried": 3},
                "random_motes": False,
                "random_shades": False,
                "random_drifters": False,
                "drifters": [{"id": "D1", "pos": [0, 1.2, 0.5], "state": "idle"}],
            },
            contract=self.contract,
        )
        ev_idle = sim_idle.step(InputState())
        self.assertNotIn("drifter_steal", [e["name"] for e in ev_idle])
        self.assertEqual(sim_idle.player.carried, 3)

        # 3. Charm speed 7.2 m/s and 2700-tick respawn
        sim_charm = GameSim(
            seed=18,
            night=2,
            scenario={
                "player": {"pos": [34.5, 0, 0], "carried": 0},
                "random_motes": False,
                "random_shades": False,
                "random_drifters": False,
                "charms": [{"id": "C1", "pos": [35, 0, 0], "available": True}],
            },
            contract=self.contract,
        )
        sim_charm.step(InputState())  # pick C1
        self.assertFalse(sim_charm.charms[0].available)
        x0 = sim_charm.player.x
        for _ in range(60):
            sim_charm.step(InputState(move_x=-1.0, move_z=0.0))
        self.assertAlmostEqual(x0 - sim_charm.player.x, 7.2, places=3)
        for _ in range(2639):
            sim_charm.step(InputState())
        self.assertFalse(sim_charm.charms[0].available)
        sim_charm.step(InputState())  # tick 2701 -> 2700 ticks elapsed since pickup at tick 1
        self.assertTrue(sim_charm.charms[0].available)

        # 4. Same-tick win/loss precedence: no_flames > all_lit > dawn
        sim_prec = GameSim(
            seed=19,
            night=1,
            scenario={
                "player": {"pos": [0, 0, 25], "carried": 10, "flames": 1},
                "random_motes": False,
                "random_shades": False,
                "lanterns": [
                    {"id": "L1", "pos": [0, 0, 25], "deposited": 0, "lit": False},
                    {"id": "L2", "lit": True},
                    {"id": "L3", "lit": True},
                    {"id": "L4", "lit": True},
                    {"id": "L5", "lit": True},
                ],
                "shades": [{"id": "S1", "pos": [0, 0, 31], "state": "chase"}],
                "time_left_s": 1.0 / 60.0,
            },
            contract=self.contract,
        )
        # All lit on same tick as dawn -> won (all_lit > dawn)
        ev_won = sim_prec.step(InputState(interact=True))
        self.assertEqual(sim_prec.state, "won")
        self.assertEqual(ev_won[-1]["data"], {"result": "won", "reason": "all_lit"})


if __name__ == "__main__":
    unittest.main()
