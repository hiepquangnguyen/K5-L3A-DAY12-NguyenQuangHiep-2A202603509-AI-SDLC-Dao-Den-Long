"""Unit tests for GameSim 60Hz simulation rules and Test Contract v1.0 invariants."""

from __future__ import annotations

import math
import unittest

from src.sim.config import DT, load_contract
from src.sim.engine import GameSim, InputState, dist_xz


class TestGameSimUnit(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()
        self.tuning = self.contract["tuning"]

    def test_camera_yaw_rotation_and_normalization(self) -> None:
        speed = float(self.tuning["player_speed"])
        cases = [
            (0.0, [0.0, 1.0], (0.0, 1.0)),
            (90.0, [0.0, 1.0], (1.0, 0.0)),
            (180.0, [0.0, 1.0], (0.0, -1.0)),
            (-45.0, [1.0, 0.0], (math.cos(math.radians(-45.0)), -math.sin(math.radians(-45.0)))),
            (0.0, [1.0, 1.0], (1.0 / math.sqrt(2.0), 1.0 / math.sqrt(2.0))),
        ]
        for yaw_deg, move, (ex, ez) in cases:
            sim = GameSim(
                seed=1,
                scenario={"random_motes": False, "random_shades": False, "motes": [], "shades": []},
                contract=self.contract,
            )
            for _ in range(60):
                sim.step(InputState(move_x=move[0], move_z=move[1], cam_yaw_deg=yaw_deg))
            self.assertAlmostEqual(sim.player.x, ex * speed, places=4)
            self.assertAlmostEqual(sim.player.z, ez * speed, places=4)

    def test_rising_edge_for_interact_and_pulse(self) -> None:
        sim = GameSim(
            seed=2,
            scenario={
                "player": {"pos": [0, 0, 24], "carried": 10, "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "motes": [],
                "shades": [{"id": "S1", "pos": [0, 0, 28]}],
                "lanterns": [{"id": "L1", "pos": [0, 0, 25], "deposited": 0, "lit": False}],
            },
            contract=self.contract,
        )
        # Hold interact=True for 5 ticks -> should deposit only once on tick 1
        all_events = []
        for _ in range(5):
            all_events.extend(sim.step(InputState(interact=True, pulse=True)))

        deposits = [e for e in all_events if e["name"] == "deposit"]
        pulses = [e for e in all_events if e["name"] == "pulse"]
        self.assertEqual(len(deposits), 1)
        self.assertEqual(deposits[0]["tick"], 1)
        self.assertEqual(len(pulses), 1)
        self.assertEqual(pulses[0]["tick"], 1)

        # Wait out pulse cooldown (4s = 240 ticks) while still holding pulse=True -> still no second pulse
        for _ in range(250):
            ev = sim.step(InputState(interact=True, pulse=True))
            self.assertEqual([e for e in ev if e["name"] == "pulse"], [])

        # Drop pulse to False, then raise back to True -> triggers second pulse
        sim.step(InputState(pulse=False))
        ev2 = sim.step(InputState(pulse=True))
        self.assertEqual(len([e for e in ev2 if e["name"] == "pulse"]), 1)

    def test_xz_distance_ignores_jump_height_and_lands_at_zero(self) -> None:
        sim = GameSim(
            seed=3,
            scenario={
                "player": {"pos": [0, 0, 0], "carried": 0, "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "motes": [[0, 0, 1.99]],
                "shades": [],
            },
            contract=self.contract,
        )
        ev_jump = sim.step(InputState(jump=True))
        self.assertGreater(sim.player.y, 0.0)
        # Mote at z=1.99 <= pickup_radius(2.0) is picked despite player being airborne
        self.assertEqual(len([e for e in ev_jump if e["name"] == "mote_picked"]), 1)

        # Step until player lands back at Y = 0
        for _ in range(120):
            sim.step(InputState(jump=False))
        self.assertEqual(sim.player.y, 0.0)
        self.assertEqual(sim.player.vy, 0.0)

    def test_scenario_setup_emits_no_events_or_score(self) -> None:
        sim = GameSim(
            seed=4,
            scenario={
                "random_motes": False,
                "random_shades": False,
                "lanterns": [
                    {"id": "L1", "lit": True},
                    {"id": "L2", "lit": True},
                ],
            },
            contract=self.contract,
        )
        self.assertEqual(sim.score, 0)
        self.assertEqual(sim.tick, 0)
        self.assertTrue(sim.lanterns[0].lit)
        self.assertTrue(sim.lanterns[1].lit)
        self.assertEqual(sim.lanterns[0].deposited, self.tuning["lantern_cost"])

    def test_invuln_window_and_drop_ratio(self) -> None:
        sim = GameSim(
            seed=5,
            scenario={
                "player": {"pos": [0, 0, 0], "carried": 5, "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "motes": [],
                "shades": [{"id": "S1", "pos": [0, 0, 0.5]}],
            },
            contract=self.contract,
        )
        hits = []
        # Step 60 ticks (1.0s < invuln_s=1.5s) -> only 1 hit
        for _ in range(60):
            hits.extend(e for e in sim.step(InputState()) if e["name"] == "player_hit")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["data"]["dropped"], 2)  # floor(5 * 0.5)
        self.assertEqual(sim.player.carried, 3)
        self.assertEqual(sim.player.flames, 2)

        # Step another 40 ticks (total 100 > 90 invuln ticks) -> second hit occurs
        for _ in range(40):
            hits.extend(e for e in sim.step(InputState()) if e["name"] == "player_hit")
        self.assertEqual(len(hits), 2)
        self.assertEqual(sim.player.flames, 1)

    def test_safe_radius_blocks_active_shades_only_for_lit_lanterns(self) -> None:
        safe_r = float(self.tuning["safe_radius"])
        sim = GameSim(
            seed=6,
            scenario={
                "player": {"pos": [0, 0, 25], "carried": 0, "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "motes": [],
                "shades": [{"id": "S1", "pos": [0, 0, 27]}],
                "lanterns": [{"id": "L1", "pos": [0, 0, 25], "lit": True}],
            },
            contract=self.contract,
        )
        for _ in range(30):
            sim.step(InputState())
            d = dist_xz(sim.shades[0].x, sim.shades[0].z, 0.0, 25.0)
            self.assertGreaterEqual(d, safe_r)
        self.assertEqual(sim.player.flames, 3)

    def test_random_shades_deterministic_spawn_event(self) -> None:
        sim = GameSim(
            seed=42,
            scenario={"random_motes": False, "random_shades": True, "shades": []},
            contract=self.contract,
        )
        spawns = []
        for _ in range(1200):
            spawns.extend(e for e in sim.step(InputState()) if e["name"] == "shade_spawned")
        self.assertEqual(len(spawns), 1)
        self.assertEqual(spawns[0]["tick"], 1200)
        self.assertEqual(spawns[0]["data"], {"id": "S1"})

    def test_fractional_time_bonus_partial_deposit_capacity_and_pulse_miss(self) -> None:
        # Fractional time_left_s=1.4 -> 24 ticks -> 1.0s left -> 1 * per_second_left
        sim = GameSim(
            seed=7,
            scenario={
                "player": {"pos": [0, 0, 24], "carried": 3, "flames": 2},
                "random_motes": False,
                "random_shades": False,
                "motes": [],
                "shades": [],
                "lanterns": [
                    {"id": "L1", "pos": [0, 0, 25], "deposited": 2, "lit": False},
                    {"id": "L2", "lit": True},
                    {"id": "L3", "lit": True},
                    {"id": "L4", "lit": True},
                    {"id": "L5", "lit": True},
                ],
                "time_left_s": 1.4,
            },
            contract=self.contract,
        )
        for _ in range(23):
            sim.step(InputState())
        ev = sim.step(InputState(interact=True))
        self.assertEqual(sim.tick, 24)
        self.assertEqual(sim.state, "won")
        self.assertEqual([e["name"] for e in ev], ["deposit", "lantern_lit", "game_over"])
        # 200 (lantern) + 1*2 (time_left_s=1.0) + 2*100 (flames) = 402
        self.assertEqual(sim.score, 402)

        # Carry capacity cap & pulse miss (stunned_ids == [])
        sim2 = GameSim(
            seed=8,
            scenario={
                "player": {"pos": [0, 0, 0], "carried": 10, "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "motes": [{"pos": [0, 0, 0.5]}],
                "shades": [],
            },
            contract=self.contract,
        )
        ev_cap = sim2.step(InputState(pulse=True))
        self.assertEqual([e["name"] for e in ev_cap], ["pulse"])
        self.assertEqual(ev_cap[0]["data"], {"stunned_ids": []})
        # After spending pulse_cost(2) -> carried=8, next tick mote is picked -> carried=9
        ev_pick = sim2.step(InputState(pulse=False))
        self.assertEqual([e["name"] for e in ev_pick], ["mote_picked"])
        self.assertEqual(sim2.player.carried, 9)

    def test_negative_zero_rounding_and_jump_no_auto_rejump(self) -> None:
        sim = GameSim(
            seed=9,
            scenario={"player": {"pos": [-0.0, 0.0, -0.0]}, "random_motes": False, "random_shades": False, "motes": [], "shades": []},
            contract=self.contract,
        )
        snap = sim.snapshot()
        self.assertEqual(snap["player"]["pos"], [0.0, 0.0, 0.0])
        self.assertNotEqual(math.copysign(1.0, snap["player"]["pos"][0]), -1.0)

        sim.step(InputState(jump=True))
        # Hold jump=True all the way past landing -> must NOT auto-jump a second time
        for _ in range(90):
            sim.step(InputState(jump=True))
        self.assertEqual(sim.player.y, 0.0)
        self.assertEqual(sim.player.vy, 0.0)


if __name__ == "__main__":
    unittest.main()
