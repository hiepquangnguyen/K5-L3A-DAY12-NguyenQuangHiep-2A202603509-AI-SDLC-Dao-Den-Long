"""Unit tests for GameSim 60Hz rules & Test Contract v1.2 (updated Phase 1-2 regressions)."""

from __future__ import annotations

import math
import unittest

from src.sim.config import load_contract
from src.sim.engine import GameSim, InputState, dist_xz


class TestGameSimUnit(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()
        self.tuning = self.contract["tuning"]

    def test_camera_yaw_rotation_and_normalization(self) -> None:
        speed = float(self.tuning["player_speed"])  # 6.0 m/s
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
        # Hold interact=True and pulse=True across multiple ticks -> each triggers only once
        sim = GameSim(
            seed=2,
            scenario={
                "player": {"pos": [0, 0, 24], "carried": 10, "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "motes": [],
                "shades": [{"id": "S1", "pos": [0, 0, 27], "state": "chase"}],
                "lanterns": [{"id": "L1", "pos": [0, 0, 25], "deposited": 4, "lit": False}],
            },
            contract=self.contract,
        )
        # First tick: interact deposits 6 (needed=6, carried=10 -> 4 left), pulse spends 3 -> 1 left
        # Use separate test with carried=10 and lit L1 or partial deposit of 4 so carried remains >= 3
        sim2 = GameSim(
            seed=2,
            scenario={
                "player": {"pos": [0, 0, 24], "carried": 10, "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "motes": [],
                "shades": [{"id": "S1", "pos": [0, 0, 27], "state": "chase"}],
                "lanterns": [{"id": "L1", "pos": [0, 0, 25], "deposited": 8, "lit": False}],
            },
            contract=self.contract,
        )
        all_events = []
        for _ in range(5):
            all_events.extend(sim2.step(InputState(interact=True, pulse=True)))

        deposits = [e for e in all_events if e["name"] == "deposit"]
        pulses = [e for e in all_events if e["name"] == "pulse"]
        self.assertEqual(len(deposits), 1)
        self.assertEqual(deposits[0]["tick"], 1)
        self.assertEqual(len(pulses), 1)
        self.assertEqual(pulses[0]["tick"], 1)

        # Wait out pulse cooldown (3s = 180 ticks) while holding pulse=True -> no second pulse
        for _ in range(190):
            ev = sim2.step(InputState(interact=True, pulse=True))
            self.assertEqual([e for e in ev if e["name"] == "pulse"], [])

        # Release and re-press pulse -> carried is 10 - 2 - 3 = 5 >= 3, triggers second pulse
        sim2.step(InputState(pulse=False))
        ev2 = sim2.step(InputState(pulse=True))
        self.assertEqual(len([e for e in ev2 if e["name"] == "pulse"]), 1)

    def test_pickup_radius_and_height_tolerance_and_landing(self) -> None:
        # pickup_radius = 1.0m, |py - my| <= 1.5m; jump v0=7.0 -> max height = 1.225m <= 1.5m
        sim = GameSim(
            seed=3,
            scenario={
                "player": {"pos": [0, 0, 0], "carried": 0, "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "motes": [[0, 0, 0.99]],
                "shades": [],
            },
            contract=self.contract,
        )
        ev_jump = sim.step(InputState(jump=True))
        self.assertGreater(sim.player.y, 0.0)
        self.assertFalse(sim.player.grounded)
        self.assertEqual(len([e for e in ev_jump if e["name"] == "mote_picked"]), 1)
        # Standardized scoring: pickup itself awards 0 points
        self.assertEqual(sim.score, 0)

        for _ in range(120):
            sim.step(InputState(jump=False))
        self.assertEqual(sim.player.y, 0.0)
        self.assertTrue(sim.player.grounded)

    def test_scenario_setup_emits_no_events_or_score(self) -> None:
        sim = GameSim(
            seed=4,
            scenario={
                "random_motes": False,
                "random_shades": False,
                "lanterns": [{"id": "L1", "lit": True}, {"id": "L2", "lit": True}],
            },
            contract=self.contract,
        )
        self.assertEqual(sim.score, 0)
        self.assertEqual(sim.tick, 0)
        self.assertTrue(sim.lanterns[0].lit)
        self.assertTrue(sim.lanterns[1].lit)
        self.assertEqual(sim.lanterns[0].deposited, self.tuning["lantern_cost"])

    def test_invuln_window_drop_ratio_and_recoil(self) -> None:
        sim = GameSim(
            seed=5,
            scenario={
                "player": {"pos": [0, 0, 0], "carried": 5, "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "motes": [],
                "shades": [{"id": "S1", "pos": [0, 0, 0.5], "state": "chase"}],
            },
            contract=self.contract,
        )
        hits = []
        for _ in range(60):
            hits.extend(e for e in sim.step(InputState()) if e["name"] == "player_hit")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["data"]["dropped"], 2)  # floor(5 * 0.5)
        self.assertEqual(sim.player.carried, 3)
        self.assertEqual(sim.player.flames, 2)
        self.assertEqual(sim.shades[0].state, "recoil")
        # 2 dropped motes exist on ground
        dropped = [m for m in sim.motes if m.kind == "dropped"]
        self.assertEqual(len(dropped), 2)

    def test_safe_radius_blocks_active_shades_only_for_lit_lanterns(self) -> None:
        safe_r = float(self.tuning["safe_radius"])  # 6.0m
        sim = GameSim(
            seed=6,
            scenario={
                "player": {"pos": [0, 0, 25], "carried": 0, "flames": 3},
                "random_motes": False,
                "random_shades": False,
                "motes": [],
                "shades": [{"id": "S1", "pos": [0, 0, 32], "state": "chase"}],
                "lanterns": [{"id": "L1", "pos": [0, 0, 25], "lit": True}],
            },
            contract=self.contract,
        )
        for _ in range(40):
            sim.step(InputState())
            d = dist_xz(sim.shades[0].x, sim.shades[0].z, 0.0, 25.0)
            self.assertGreaterEqual(d, safe_r)
        self.assertEqual(sim.player.flames, 3)

    def test_random_shades_spawn_at_tick_300_deterministically(self) -> None:
        sim = GameSim(
            seed=42,
            night=1,
            scenario={"random_motes": False, "random_shades": True},
            contract=self.contract,
        )
        spawns = []
        for _ in range(300):
            spawns.extend(e for e in sim.step(InputState()) if e["name"] == "shade_spawned")
        self.assertEqual(len(spawns), 2)
        self.assertEqual([s["tick"] for s in spawns], [300, 300])
        self.assertEqual([s["data"]["id"] for s in spawns], ["S1", "S2"])
        self.assertEqual(sim.shades[0].state, "spawning")

    def test_partial_deposit_dawn_win_scoring_capacity_and_pulse_miss(self) -> None:
        # Migrated from v1.1 (CHANGELOG 1.2.0): TICKET-03 removed early all_lit win and per_second_left.
        # Lighting L1 keeps playing until dawn (sim_tick=84, time_left_s=0.0), then wins with dawn_survived.
        sim = GameSim(
            seed=7,
            scenario={
                "player": {"pos": [0, 0, 24], "carried": 3, "flames": 2},
                "random_motes": False,
                "random_shades": False,
                "motes": [],
                "shades": [],
                "lanterns": [
                    {"id": "L1", "pos": [0, 0, 25], "deposited": 7, "lit": False},
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
        self.assertEqual(sim.state, "playing")
        self.assertEqual([e["name"] for e in ev], ["deposit", "lantern_lit"])
        self.assertEqual(ev[1]["data"], {"lantern_id": "L1", "relight": False})
        self.assertEqual(sim.carry_capacity, 12)
        # 3*5 (deposited) + 100 (first light) = 115
        self.assertEqual(sim.score, 115)

        for _ in range(59):
            sim.step(InputState())
        ev_dawn = sim.step(InputState())
        self.assertEqual(sim.tick, 84)
        self.assertEqual(sim.state, "won")
        self.assertEqual(ev_dawn[-1]["data"], {"result": "won", "reason": "dawn_survived"})
        # L1 decayed 60 ticks (5940 -> floor=99); L2..L5 decayed 84 ticks (5916 -> floor=98 each)
        # Dawn bonus: 5*50 + (99 + 4*98) + 2*50 = 250 + 491 + 100 = 841; total = 115 + 841 = 956
        self.assertEqual(sim.score, 956)

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
        self.assertEqual([e["name"] for e in ev_cap], ["night_start", "pulse"])
        self.assertEqual(ev_cap[1]["data"], {"stunned_ids": []})
        # carried is now 10 - 3 = 7, next tick picks mote -> 8
        ev_pick = sim2.step(InputState(pulse=False))
        self.assertEqual([e["name"] for e in ev_pick], ["mote_picked"])
        self.assertEqual(sim2.player.carried, 8)

    def test_negative_zero_rounding_and_jump_no_auto_rejump(self) -> None:
        sim = GameSim(
            seed=9,
            scenario={
                "player": {"pos": [-0.0, 0.0, -0.0]},
                "random_motes": False,
                "random_shades": False,
                "motes": [],
                "shades": [],
            },
            contract=self.contract,
        )
        snap = sim.snapshot()
        self.assertEqual(snap["player"]["pos"], [0.0, 0.0, 0.0])
        self.assertNotEqual(math.copysign(1.0, snap["player"]["pos"][0]), -1.0)

        sim.step(InputState(jump=True))
        for _ in range(90):
            sim.step(InputState(jump=True))
        self.assertEqual(sim.player.y, 0.0)
        self.assertEqual(sim.player.vy, 0.0)


if __name__ == "__main__":
    unittest.main()
