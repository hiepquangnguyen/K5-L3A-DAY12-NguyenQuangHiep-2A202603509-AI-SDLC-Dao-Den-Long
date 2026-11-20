"""Pure 60Hz simulation engine for Đảo Đèn Lồng (Test Contract v1.0)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.sim.config import (
    DEFAULT_ISLAND_RADIUS,
    DEFAULT_LANTERN_POSITIONS,
    DT,
    GRAVITY,
    JUMP_SPEED,
    SHADE_DEFAULT_Y,
    TICK_RATE,
    load_contract,
)
from src.sim.prng import SeededRNG

SAFE_RADIUS_EPS = 0.002


def r3(value: float) -> float:
    """Round to 3 decimal places and normalize -0.0 to 0.0."""
    rounded = round(float(value), 3)
    return 0.0 if rounded == 0.0 else rounded


def dist_xz(x1: float, z1: float, x2: float, z2: float) -> float:
    """Horizontal XZ Euclidean distance."""
    return math.hypot(x1 - x2, z1 - z2)


def _clamp_to_circle(x: float, z: float, radius: float) -> tuple[float, float]:
    dist = math.hypot(x, z)
    if dist <= radius or dist == 0.0:
        return x, z
    scale = radius / dist
    return x * scale, z * scale


def _numeric_suffix(entity_id: str, prefix: str) -> int:
    if entity_id.startswith(prefix) and entity_id[len(prefix) :].isdigit():
        return int(entity_id[len(prefix) :])
    return 0


@dataclass
class InputState:
    move_x: float = 0.0
    move_z: float = 0.0
    cam_yaw_deg: float = 0.0
    jump: bool = False
    interact: bool = False
    pulse: bool = False
    dash: bool = False


@dataclass
class PlayerState:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    vy: float = 0.0
    yaw_deg: float = 0.0
    flames: int = 3
    carried: int = 0


@dataclass
class LanternState:
    id: str
    x: float
    y: float
    z: float
    lit: bool = False
    deposited: int = 0


@dataclass
class MoteState:
    id: str
    x: float
    y: float
    z: float


@dataclass
class ShadeState:
    id: str
    x: float
    y: float
    z: float
    state: str = "chase"
    stun_ticks: int = 0


class GameSim:
    """Deterministic single-source-of-truth simulation for Night 1 (Đảo Bến)."""

    def __init__(
        self,
        seed: int,
        night: int = 1,
        scenario: dict | None = None,
        contract: dict | None = None,
    ) -> None:
        if night != 1:
            raise ValueError(f"Unsupported night={night}; Phase 1 supports night=1 only")

        self.seed = int(seed)
        self.night = night
        self.contract = contract or load_contract()
        self.tuning = self.contract["tuning"]
        self.score_cfg = self.tuning["score"]
        self.rng = SeededRNG(self.seed)

        self.tick = 0
        self.sim_tick = 0
        self.state = "playing"
        self.game_over_reason: str | None = None
        self.score = 0

        self.initial_time_left_s = float(self.tuning["night1_duration_s"])
        self.time_left_s = self.initial_time_left_s

        self.player = PlayerState(flames=int(self.tuning["flames"]), carried=0)
        self.lanterns: list[LanternState] = [
            LanternState(id=lid, x=pos[0], y=pos[1], z=pos[2])
            for lid, pos in DEFAULT_LANTERN_POSITIONS
        ]
        self.motes: list[MoteState] = []
        self.shades: list[ShadeState] = []

        self.invuln_ticks = 0
        self.pulse_cooldown_ticks = 0
        self._prev_jump = False
        self._prev_interact = False
        self._prev_pulse = False

        self._next_mote_num = 1
        self._next_shade_num = 1

        sc = scenario or {}
        self.random_motes = bool(sc.get("random_motes", True))
        self.random_shades = bool(sc.get("random_shades", True))

        self._apply_scenario(sc)
        self.island_radius = self._compute_effective_island_radius()

    def _apply_scenario(self, sc: dict) -> None:
        """Apply scenario overrides without emitting events or awarding score."""
        if "time_left_s" in sc:
            self.initial_time_left_s = float(sc["time_left_s"])
            self.time_left_s = self.initial_time_left_s

        if "player" in sc:
            p = sc["player"]
            if "pos" in p:
                self.player.x, self.player.y, self.player.z = (
                    float(p["pos"][0]),
                    float(p["pos"][1]),
                    float(p["pos"][2]),
                )
            if "carried" in p:
                self.player.carried = int(p["carried"])
            if "flames" in p:
                self.player.flames = int(p["flames"])

        lantern_cost = int(self.tuning["lantern_cost"])
        if "lanterns" in sc:
            by_id = {l.id: l for l in self.lanterns}
            for item in sc["lanterns"]:
                lantern = by_id[item["id"]]
                if "pos" in item:
                    lantern.x, lantern.y, lantern.z = (
                        float(item["pos"][0]),
                        float(item["pos"][1]),
                        float(item["pos"][2]),
                    )
                if "deposited" in item:
                    lantern.deposited = int(item["deposited"])
                if "lit" in item:
                    lantern.lit = bool(item["lit"])
                    if lantern.lit and "deposited" not in item:
                        lantern.deposited = max(lantern.deposited, lantern_cost)
                elif "deposited" in item and lantern.deposited >= lantern_cost:
                    lantern.lit = True

        if "motes" in sc:
            for item in sc["motes"]:
                if isinstance(item, list):
                    mid = f"M{self._next_mote_num}"
                    pos = item
                else:
                    mid = item.get("id") or f"M{self._next_mote_num}"
                    pos = item["pos"]
                self._next_mote_num = max(self._next_mote_num + 1, _numeric_suffix(mid, "M") + 1)
                self.motes.append(
                    MoteState(id=mid, x=float(pos[0]), y=float(pos[1]), z=float(pos[2]))
                )
        elif self.random_motes:
            for _ in range(20):
                self._spawn_random_mote()

        if "shades" in sc:
            stun_default = round(float(self.tuning["pulse_stun_s"]) * TICK_RATE)
            for item in sc["shades"]:
                sid = item.get("id") or f"S{self._next_shade_num}"
                self._next_shade_num = max(self._next_shade_num + 1, _numeric_suffix(sid, "S") + 1)
                pos = item["pos"]
                st = item.get("state", "chase")
                self.shades.append(
                    ShadeState(
                        id=sid,
                        x=float(pos[0]),
                        y=float(pos[1]),
                        z=float(pos[2]),
                        state=st,
                        stun_ticks=stun_default if st == "stunned" else 0,
                    )
                )
        elif self.random_shades:
            for _ in range(2):
                self._spawn_random_shade(min_player_dist=20.0)

    def _compute_effective_island_radius(self) -> float:
        max_r = math.hypot(self.player.x, self.player.z)
        for lantern in self.lanterns:
            max_r = max(max_r, math.hypot(lantern.x, lantern.z))
        for mote in self.motes:
            max_r = max(max_r, math.hypot(mote.x, mote.z))
        for shade in self.shades:
            max_r = max(max_r, math.hypot(shade.x, shade.z))
        return max(DEFAULT_ISLAND_RADIUS, max_r + 15.0)

    def _is_inside_lit_safe_zone(self, x: float, z: float) -> bool:
        safe_r = float(self.tuning["safe_radius"])
        return any(
            lantern.lit and dist_xz(x, z, lantern.x, lantern.z) < safe_r
            for lantern in self.lanterns
        )

    def _spawn_random_mote(self) -> MoteState:
        pickup_r = float(self.tuning["pickup_radius"])
        x, z = 10.0, 10.0
        for _ in range(24):
            angle = self.rng.uniform(0.0, math.tau)
            radius = self.rng.uniform(5.0, min(40.0, self.island_radius if hasattr(self, "island_radius") else 40.0))
            cx = math.cos(angle) * radius
            cz = math.sin(angle) * radius
            if dist_xz(cx, cz, self.player.x, self.player.z) > pickup_r + 1.0:
                x, z = cx, cz
                break
        mid = f"M{self._next_mote_num}"
        self._next_mote_num += 1
        mote = MoteState(id=mid, x=x, y=0.0, z=z)
        self.motes.append(mote)
        return mote

    def _spawn_random_shade(self, min_player_dist: float = 18.0) -> ShadeState:
        max_r = min(38.0, self.island_radius - 2.0) if hasattr(self, "island_radius") else 38.0
        x, z = 30.0, 0.0
        for _ in range(32):
            angle = self.rng.uniform(0.0, math.tau)
            radius = self.rng.uniform(22.0, max(24.0, max_r))
            cx = math.cos(angle) * radius
            cz = math.sin(angle) * radius
            if (
                dist_xz(cx, cz, self.player.x, self.player.z) >= min_player_dist
                and not self._is_inside_lit_safe_zone(cx, cz)
            ):
                x, z = cx, cz
                break
        sid = f"S{self._next_shade_num}"
        self._next_shade_num += 1
        shade = ShadeState(id=sid, x=x, y=SHADE_DEFAULT_Y, z=z, state="chase")
        self.shades.append(shade)
        return shade

    def step(self, inp: InputState) -> list[dict]:
        """Advance simulation by one 1/60s tick (from tick k to k+1)."""
        if self.state != "playing":
            return []

        events: list[dict] = []

        jump_edge = inp.jump and not self._prev_jump
        interact_edge = inp.interact and not self._prev_interact
        pulse_edge = inp.pulse and not self._prev_pulse
        self._prev_jump = inp.jump
        self._prev_interact = inp.interact
        self._prev_pulse = inp.pulse

        self.tick += 1
        self.sim_tick += 1
        self.time_left_s = max(0.0, self.initial_time_left_s - (self.sim_tick / TICK_RATE))

        if self.invuln_ticks > 0:
            self.invuln_ticks -= 1
        if self.pulse_cooldown_ticks > 0:
            self.pulse_cooldown_ticks -= 1
        for shade in self.shades:
            if shade.stun_ticks > 0:
                shade.stun_ticks -= 1
                if shade.stun_ticks == 0 and shade.state == "stunned":
                    shade.state = "chase"

        self._step_player_motion(inp, jump_edge)
        self._step_mote_pickup(events)
        if interact_edge:
            self._step_deposit(events)
        if pulse_edge:
            self._step_pulse(events)

        if all(lantern.lit for lantern in self.lanterns):
            self.state = "won"
            self.game_over_reason = "all_lit"
            self.score += (
                int(math.floor(self.time_left_s + 1e-9)) * int(self.score_cfg["per_second_left"])
                + self.player.flames * int(self.score_cfg["per_flame_left"])
            )
            events.append(
                {"type": "event", "tick": self.tick, "name": "game_over", "data": {"result": "won", "reason": "all_lit"}}
            )
            return events

        self._step_shades(events)

        if self.state == "playing" and self.time_left_s <= 1e-9:
            self.time_left_s = 0.0
            self.state = "lost"
            self.game_over_reason = "dawn"
            events.append(
                {"type": "event", "tick": self.tick, "name": "game_over", "data": {"result": "lost", "reason": "dawn"}}
            )
            return events

        if self.state == "playing":
            self._step_spawners(events)

        return events

    def _step_player_motion(self, inp: InputState, jump_edge: bool) -> None:
        mx = float(inp.move_x)
        mz = float(inp.move_z)
        mag = math.hypot(mx, mz)
        if mag > 1.0:
            mx /= mag
            mz /= mag

        theta = math.radians(float(inp.cam_yaw_deg))
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        wx = mx * cos_t + mz * sin_t
        wz = -mx * sin_t + mz * cos_t

        speed = float(self.tuning["player_speed"])
        self.player.x += wx * speed * DT
        self.player.z += wz * speed * DT
        self.player.x, self.player.z = _clamp_to_circle(
            self.player.x, self.player.z, self.island_radius
        )

        if abs(wx) > 1e-5 or abs(wz) > 1e-5:
            self.player.yaw_deg = math.degrees(math.atan2(wx, wz))

        if jump_edge and self.player.y <= 1e-6:
            self.player.vy = JUMP_SPEED

        if self.player.y > 0.0 or self.player.vy != 0.0:
            self.player.vy -= GRAVITY * DT
            self.player.y += self.player.vy * DT
            if self.player.y <= 0.0:
                self.player.y = 0.0
                self.player.vy = 0.0

    def _step_mote_pickup(self, events: list[dict]) -> None:
        capacity = int(self.tuning["carry_capacity"])
        pickup_r = float(self.tuning["pickup_radius"])
        per_mote = int(self.score_cfg["per_mote"])

        remaining: list[MoteState] = []
        for mote in self.motes:
            if (
                self.player.carried < capacity
                and dist_xz(self.player.x, self.player.z, mote.x, mote.z) <= pickup_r
            ):
                self.player.carried += 1
                self.score += per_mote
                events.append(
                    {
                        "type": "event",
                        "tick": self.tick,
                        "name": "mote_picked",
                        "data": {"carried": self.player.carried},
                    }
                )
            else:
                remaining.append(mote)
        self.motes = remaining

    def _step_deposit(self, events: list[dict]) -> None:
        interact_r = float(self.tuning["interact_radius"])
        lantern_cost = int(self.tuning["lantern_cost"])
        per_lantern = int(self.score_cfg["per_lantern"])

        candidates = [
            (dist_xz(self.player.x, self.player.z, lantern.x, lantern.z), lantern.id, lantern)
            for lantern in self.lanterns
            if not lantern.lit
            and dist_xz(self.player.x, self.player.z, lantern.x, lantern.z) <= interact_r
        ]
        if not candidates:
            return
        candidates.sort(key=lambda item: (item[0], item[1]))
        target = candidates[0][2]

        needed = max(0, lantern_cost - target.deposited)
        if needed == 0:
            target.lit = True
            self.score += per_lantern
            events.append(
                {
                    "type": "event",
                    "tick": self.tick,
                    "name": "lantern_lit",
                    "data": {"lantern_id": target.id},
                }
            )
            return

        if self.player.carried <= 0:
            return

        amount = min(self.player.carried, needed)
        self.player.carried -= amount
        target.deposited += amount
        events.append(
            {
                "type": "event",
                "tick": self.tick,
                "name": "deposit",
                "data": {
                    "lantern_id": target.id,
                    "amount": amount,
                    "deposited": target.deposited,
                },
            }
        )
        if target.deposited >= lantern_cost:
            target.lit = True
            self.score += per_lantern
            events.append(
                {
                    "type": "event",
                    "tick": self.tick,
                    "name": "lantern_lit",
                    "data": {"lantern_id": target.id},
                }
            )

    def _step_pulse(self, events: list[dict]) -> None:
        pulse_cost = int(self.tuning["pulse_cost"])
        if self.pulse_cooldown_ticks > 0 or self.player.carried < pulse_cost:
            return

        pulse_r = float(self.tuning["pulse_radius"])
        push_m = float(self.tuning["pulse_push_m"])
        stun_ticks = round(float(self.tuning["pulse_stun_s"]) * TICK_RATE)
        per_stun = int(self.score_cfg["per_stun"])

        self.player.carried -= pulse_cost
        self.pulse_cooldown_ticks = round(float(self.tuning["pulse_cooldown_s"]) * TICK_RATE)

        stunned_ids: list[str] = []
        for shade in self.shades:
            d = dist_xz(self.player.x, self.player.z, shade.x, shade.z)
            if d <= pulse_r:
                if d > 1e-9:
                    nx = (shade.x - self.player.x) / d
                    nz = (shade.z - self.player.z) / d
                else:
                    nx, nz = 1.0, 0.0
                shade.x += nx * push_m
                shade.z += nz * push_m
                shade.x, shade.z = _clamp_to_circle(shade.x, shade.z, self.island_radius)
                shade.state = "stunned"
                shade.stun_ticks = stun_ticks
                stunned_ids.append(shade.id)
                self.score += per_stun

        events.append(
            {
                "type": "event",
                "tick": self.tick,
                "name": "pulse",
                "data": {"stunned_ids": stunned_ids},
            }
        )

    def _step_shades(self, events: list[dict]) -> None:
        shade_speed = float(self.tuning["shade_speed"])
        safe_r = float(self.tuning["safe_radius"])
        hit_r = float(self.tuning["shade_hit_radius"])
        drop_ratio = float(self.tuning["hit_drop_ratio"])
        invuln_ticks = round(float(self.tuning["invuln_s"]) * TICK_RATE)

        lit_lanterns = [lantern for lantern in self.lanterns if lantern.lit]

        for shade in self.shades:
            if shade.state == "stunned":
                continue

            dx = self.player.x - shade.x
            dz = self.player.z - shade.z
            d = math.hypot(dx, dz)
            step_len = shade_speed * DT
            if d > 1e-9:
                move_len = min(d, step_len)
                shade.x += (dx / d) * move_len
                shade.z += (dz / d) * move_len

            pushed_by_lantern = False
            for _ in range(2):
                for lantern in lit_lanterns:
                    lx = shade.x - lantern.x
                    lz = shade.z - lantern.z
                    ld = math.hypot(lx, lz)
                    if ld < safe_r:
                        pushed_by_lantern = True
                        target_d = safe_r + SAFE_RADIUS_EPS
                        if ld > 1e-9:
                            shade.x = lantern.x + (lx / ld) * target_d
                            shade.z = lantern.z + (lz / ld) * target_d
                        else:
                            shade.x = lantern.x + target_d
                            shade.z = lantern.z

            shade.x, shade.z = _clamp_to_circle(shade.x, shade.z, self.island_radius)
            shade.state = "avoid" if pushed_by_lantern else "chase"

        if self.invuln_ticks > 0:
            return

        for shade in self.shades:
            if shade.state == "stunned":
                continue
            if dist_xz(self.player.x, self.player.z, shade.x, shade.z) <= hit_r:
                self.player.flames = max(0, self.player.flames - 1)
                dropped = int(math.floor(self.player.carried * drop_ratio + 1e-9))
                self.player.carried -= dropped
                self.invuln_ticks = invuln_ticks
                events.append(
                    {
                        "type": "event",
                        "tick": self.tick,
                        "name": "player_hit",
                        "data": {
                            "by": "shade",
                            "flames": self.player.flames,
                            "dropped": dropped,
                        },
                    }
                )
                if self.player.flames <= 0:
                    self.state = "lost"
                    self.game_over_reason = "no_flames"
                    events.append(
                        {
                            "type": "event",
                            "tick": self.tick,
                            "name": "game_over",
                            "data": {"result": "lost", "reason": "no_flames"},
                        }
                    )
                break

    def _step_spawners(self, events: list[dict]) -> None:
        if self.random_motes and self.sim_tick % 180 == 0 and len(self.motes) < 20:
            self._spawn_random_mote()

        if self.random_shades and self.sim_tick % 1200 == 0 and len(self.shades) < 6:
            shade = self._spawn_random_shade(min_player_dist=18.0)
            events.append(
                {
                    "type": "event",
                    "tick": self.tick,
                    "name": "shade_spawned",
                    "data": {"id": shade.id},
                }
            )

    def snapshot(self) -> dict:
        """Return Test Contract v1.0 JSON-serializable snapshot."""
        return {
            "type": "snapshot",
            "tick": self.tick,
            "sim_tick": self.sim_tick,
            "state": self.state,
            "time_left_s": r3(self.time_left_s),
            "score": self.score,
            "player": {
                "pos": [r3(self.player.x), r3(self.player.y), r3(self.player.z)],
                "flames": self.player.flames,
                "carried": self.player.carried,
            },
            "lanterns": [
                {
                    "id": lantern.id,
                    "pos": [r3(lantern.x), r3(lantern.y), r3(lantern.z)],
                    "lit": lantern.lit,
                    "deposited": lantern.deposited,
                }
                for lantern in self.lanterns
            ],
            "shades": [
                {
                    "id": shade.id,
                    "pos": [r3(shade.x), r3(shade.y), r3(shade.z)],
                    "state": shade.state,
                }
                for shade in self.shades
            ],
            "motes_active": len(self.motes),
            "motes": [
                {
                    "id": mote.id,
                    "pos": [r3(mote.x), r3(mote.y), r3(mote.z)],
                }
                for mote in self.motes
            ],
        }

    def end_record(self) -> dict:
        """Return Test Contract v1.0 final JSONL end object."""
        return {
            "type": "end",
            "ticks": self.tick,
            "state": self.state,
            "score": self.score,
        }

    def ui_state(self) -> dict:
        """Return snapshot extended with UI-only fields for the 3D web client."""
        snap = self.snapshot()
        snap["player_yaw_deg"] = r3(self.player.yaw_deg)
        snap["invuln_s"] = r3(self.invuln_ticks / TICK_RATE)
        snap["pulse_cooldown_s"] = r3(self.pulse_cooldown_ticks / TICK_RATE)
        snap["island_radius"] = r3(self.island_radius)
        snap["lit_count"] = sum(1 for lantern in self.lanterns if lantern.lit)
        snap["lantern_total"] = len(self.lanterns)
        snap["game_over_reason"] = self.game_over_reason
        snap["tuning"] = self.tuning
        return snap
