"""Pure 60Hz deterministic simulation engine for Đảo Đèn Lồng (Test Contract v1.2)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.sim.config import (
    DRIFTER_DEFAULT_Y,
    DT,
    FUEL_SCALE,
    GRAVITY,
    JUMP_SPEED,
    NIGHT_DURATION_KEYS,
    SHADE_DEFAULT_Y,
    TICK_RATE,
    load_contract,
)
from src.sim.maps import NightMap, get_night_map
from src.sim.prng import SeededRNG

SAFE_RADIUS_EPS = 0.002


def r1(value: float) -> float:
    """Round to 1 decimal place and normalize -0.0 to 0.0."""
    rounded = round(float(value), 1)
    return 0.0 if rounded == 0.0 else rounded


def r3(value: float) -> float:
    """Round to 3 decimal places and normalize -0.0 to 0.0."""
    rounded = round(float(value), 3)
    return 0.0 if rounded == 0.0 else rounded


def dist_xz(x1: float, z1: float, x2: float, z2: float) -> float:
    """Horizontal XZ Euclidean distance."""
    return math.hypot(x1 - x2, z1 - z2)


def dist_3d(x1: float, y1: float, z1: float, x2: float, y2: float, z2: float) -> float:
    """3D Euclidean distance."""
    dx = x1 - x2
    dy = y1 - y2
    dz = z1 - z2
    return math.sqrt(dx * dx + dy * dy + dz * dz)


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
    pause: bool = False


@dataclass
class PlayerState:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    grounded: bool = True
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
    fuel_60: int = 0
    ever_lit: bool = False
    relit_count: int = 0


@dataclass
class MoteState:
    id: str
    x: float
    y: float
    z: float
    kind: str = "random"  # "random" | "dropped"
    ttl_ticks: int | None = None
    pickup_delay_ticks: int = 0


@dataclass
class ShadeState:
    id: str
    x: float
    y: float
    z: float
    home_x: float = 0.0
    home_z: float = 0.0
    state: str = "chase"  # spawning | wander | chase | drain | recoil | stunned
    state_ticks_left: int = 0
    knockback_ticks: int = 0
    kb_vx: float = 0.0
    kb_vz: float = 0.0
    recoil_vx: float = 0.0
    recoil_vz: float = 0.0
    safe_push_ticks: int = 0
    wander_x: float = 0.0
    wander_z: float = 0.0
    wander_timer: int = 0
    target_lantern_id: str | None = None
    drain_ticks: int = 0
    just_recovered_stun: bool = False


@dataclass
class DrifterState:
    id: str
    x: float
    y: float
    z: float
    home_x: float = 0.0
    home_z: float = 0.0
    state: str = "idle"  # idle | chase | flee | removed
    stolen: int = 0
    flee_ticks_left: int = 0
    has_stolen: bool = False
    wander_angle: float = 0.0


@dataclass
class CharmState:
    id: str
    x: float
    y: float
    z: float
    available: bool = True
    respawn_ticks: int = 0


class GameSim:
    """Deterministic 60Hz single-source-of-truth simulation for Nights 1, 2, and 3."""

    def __init__(
        self,
        seed: int,
        night: int = 1,
        scenario: dict | None = None,
        contract: dict | None = None,
    ) -> None:
        if night not in NIGHT_DURATION_KEYS:
            raise ValueError(f"Unsupported night={night}; expected 1, 2, or 3")

        self.seed = int(seed)
        self.night = int(night)
        self.night_map: NightMap = get_night_map(self.night)
        self.contract = contract or load_contract()
        self.tuning = self.contract["tuning"]
        self.score_cfg = self.tuning["score"]
        self.rng = SeededRNG(self.seed + self.night * 1009)

        self.tick = 0
        self.sim_tick = 0
        self.state = "playing"
        self.game_over_reason: str | None = None
        self.score = 0
        self.successful_lights = 0

        # Exact integer fixed-point fuel constants (1/60 units) to eliminate float drift
        self._fuel_max_60 = round(float(self.tuning["fuel_max"]) * FUEL_SCALE)
        self._fuel_decay_60 = round(float(self.tuning["fuel_decay_per_s"]) * FUEL_SCALE / TICK_RATE)
        self._drain_60 = round(float(self.tuning["drain_per_s"]) * FUEL_SCALE / TICK_RATE)
        self._fuel_per_mote_60 = round(float(self.tuning["fuel_per_mote"]) * FUEL_SCALE)
        self._low_fuel_60 = round(float(self.tuning["low_fuel_threshold"]) * FUEL_SCALE)

        dur_key = NIGHT_DURATION_KEYS[self.night]
        self.initial_time_left_s = float(self.tuning[dur_key])
        self.time_left_s = self.initial_time_left_s

        sx, sy, sz = self.night_map.spawn_pos
        self.player = PlayerState(
            x=sx,
            y=sy,
            z=sz,
            grounded=True,
            yaw_deg=self.night_map.spawn_yaw_deg,
            flames=int(self.tuning["flames"]),
            carried=0,
        )

        self.lanterns: list[LanternState] = [
            LanternState(id=lid, x=pos[0], y=pos[1], z=pos[2])
            for lid, pos in self.night_map.lantern_positions
        ]
        self.win_threshold = math.ceil(float(self.tuning["win_ratio"]) * len(self.lanterns) - 1e-9)
        self.motes: list[MoteState] = []
        self.shades: list[ShadeState] = []
        self.drifters: list[DrifterState] = []
        self.charms: list[CharmState] = [
            CharmState(id=cid, x=pos[0], y=pos[1], z=pos[2], available=True, respawn_ticks=0)
            for cid, pos in self.night_map.charms
        ]

        # Timers
        self.invuln_ticks = 0
        self.pulse_cooldown_ticks = 0
        self.dash_cooldown_ticks = 0
        self.dash_ticks_left = 0
        self.dash_vx = 0.0
        self.dash_vz = 0.0
        self.charm_ticks = 0
        self.respawn_ticks = 0
        self.launched_airborne = False
        self.launch_vx = 0.0
        self.launch_vz = 0.0

        # Wind (Night 3 default enabled)
        self.wind_enabled = self.night_map.wind_enabled_default
        self.wind_active = False
        self.wind_warning = False
        self.wind_dir_deg = 0.0
        self.wind_ticks_left = 0
        self.wind_next_tick = 1800

        # Input edge memory
        self._prev_jump = False
        self._prev_interact = False
        self._prev_pulse = False
        self._prev_dash = False
        self._prev_pause = False

        # Spawn ID counters
        self._next_mote_num = 1
        self._next_shade_num = 1
        self._next_drifter_num = 1
        self._next_charm_num = 1 + len(self.charms)

        sc = scenario or {}
        self.random_motes = bool(sc.get("random_motes", True))
        self.random_shades = bool(sc.get("random_shades", True))
        self.random_drifters = bool(sc.get("random_drifters", self.night_map.drifter_max > 0))
        if "wind_enabled" in sc:
            self.wind_enabled = bool(sc["wind_enabled"])

        self._apply_scenario(sc)

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
                ground = self.night_map.surface_height(self.player.x, self.player.z, self.player.y)
                self.player.grounded = ground is not None and abs(self.player.y - ground) <= 0.05
            if "carried" in p:
                self.player.carried = int(p["carried"])
            if "flames" in p:
                self.player.flames = int(p["flames"])
            if "invuln_ticks" in p:
                self.invuln_ticks = int(p["invuln_ticks"])
            if "dash_cd_ticks" in p:
                self.dash_cooldown_ticks = int(p["dash_cd_ticks"])
            if "pulse_cd_ticks" in p:
                self.pulse_cooldown_ticks = int(p["pulse_cd_ticks"])
            if "charm_ticks" in p:
                self.charm_ticks = int(p["charm_ticks"])
            if "successful_lights" in p:
                self.successful_lights = int(p["successful_lights"])

        lantern_cost = int(self.tuning["lantern_cost"])
        relight_cost = int(self.tuning["relight_cost"])
        if "lanterns" in sc:
            by_id = {lantern.id: lantern for lantern in self.lanterns}
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
                elif "fuel" in item and float(item["fuel"]) > 0.0:
                    lantern.lit = True
                elif "deposited" in item:
                    req = relight_cost if item.get("ever_lit", False) else lantern_cost
                    if lantern.deposited >= req:
                        lantern.lit = True

                if "ever_lit" in item:
                    lantern.ever_lit = bool(item["ever_lit"])
                elif lantern.lit:
                    lantern.ever_lit = True

                if lantern.lit:
                    if "fuel" in item:
                        lantern.fuel_60 = round(float(item["fuel"]) * FUEL_SCALE)
                    else:
                        lantern.fuel_60 = self._fuel_max_60
                    if "deposited" not in item:
                        lantern.deposited = max(lantern.deposited, lantern_cost)
                else:
                    lantern.fuel_60 = 0

        if "motes" in sc:
            for item in sc["motes"]:
                if isinstance(item, list):
                    mid = f"M{self._next_mote_num}"
                    pos = item
                    kind = "random"
                    ttl_ticks = None
                else:
                    mid = item.get("id") or f"M{self._next_mote_num}"
                    pos = item["pos"]
                    kind = item.get("kind", "random")
                    if "ttl_ticks" in item:
                        ttl_ticks = int(item["ttl_ticks"])
                    elif "ttl_s" in item and item["ttl_s"] is not None:
                        ttl_ticks = round(float(item["ttl_s"]) * TICK_RATE)
                    else:
                        ttl_ticks = 480 if kind == "dropped" else None
                self._next_mote_num = max(self._next_mote_num + 1, _numeric_suffix(mid, "M") + 1)
                self.motes.append(
                    MoteState(
                        id=mid,
                        x=float(pos[0]),
                        y=float(pos[1]),
                        z=float(pos[2]),
                        kind=kind,
                        ttl_ticks=ttl_ticks,
                    )
                )
        elif self.random_motes:
            self._spawn_initial_motes()

        if "shades" in sc:
            for item in sc["shades"]:
                sid = item.get("id") or f"S{self._next_shade_num}"
                self._next_shade_num = max(self._next_shade_num + 1, _numeric_suffix(sid, "S") + 1)
                pos = item["pos"]
                px, py, pz = float(pos[0]), float(pos[1]), float(pos[2])
                if "state" in item:
                    st = item["state"]
                else:
                    st = "chase" if dist_xz(px, pz, self.player.x, self.player.z) <= 12.0 else "wander"
                ticks_left = item.get("state_ticks_left")
                if ticks_left is None:
                    if st == "stunned":
                        ticks_left = round(float(self.tuning["pulse_stun_s"]) * TICK_RATE)
                    elif st == "recoil":
                        ticks_left = 60
                    elif st == "spawning":
                        ticks_left = 30
                    else:
                        ticks_left = 0
                target_lid = item.get("target_lantern_id")
                if st == "drain" and target_lid is None:
                    nearby_lit = [
                        (dist_xz(px, pz, l.x, l.z), _numeric_suffix(l.id, "L"), l.id)
                        for l in self.lanterns
                        if l.lit and dist_xz(px, pz, l.x, l.z) <= 2.0 + 1e-9
                    ]
                    if nearby_lit:
                        nearby_lit.sort()
                        target_lid = nearby_lit[0][2]
                self.shades.append(
                    ShadeState(
                        id=sid,
                        x=px,
                        y=py,
                        z=pz,
                        home_x=px,
                        home_z=pz,
                        state=st,
                        state_ticks_left=int(ticks_left),
                        wander_x=px,
                        wander_z=pz,
                        target_lantern_id=target_lid,
                    )
                )

        if "drifters" in sc:
            for item in sc["drifters"]:
                did = item.get("id") or f"D{self._next_drifter_num}"
                self._next_drifter_num = max(
                    self._next_drifter_num + 1, _numeric_suffix(did, "D") + 1
                )
                pos = item["pos"]
                dx, dy, dz = float(pos[0]), float(pos[1]), float(pos[2])
                st = item.get("state", "idle")
                stolen = int(item.get("stolen", 0))
                flee_ticks = int(item.get("flee_ticks_left", 240 if st == "flee" else 0))
                self.drifters.append(
                    DrifterState(
                        id=did,
                        x=dx,
                        y=dy,
                        z=dz,
                        home_x=dx,
                        home_z=dz,
                        state=st,
                        stolen=stolen,
                        flee_ticks_left=flee_ticks,
                        has_stolen=(stolen > 0 or st == "flee"),
                        wander_angle=self.rng.uniform(0.0, math.tau),
                    )
                )

        if "charms" in sc:
            new_charms: list[CharmState] = []
            by_id = {c.id: c for c in self.charms}
            for idx, item in enumerate(sc["charms"]):
                cid = item.get("id") or f"C{idx + 1}"
                base = by_id.get(cid)
                pos = item.get("pos")
                if pos is not None:
                    cx, cy, cz = float(pos[0]), float(pos[1]), float(pos[2])
                elif base is not None:
                    cx, cy, cz = base.x, base.y, base.z
                else:
                    cx, cy, cz = 0.0, 0.0, 0.0
                if "respawn_ticks" in item:
                    rticks = int(item["respawn_ticks"])
                elif "respawn_s" in item:
                    rticks = round(float(item["respawn_s"]) * TICK_RATE)
                else:
                    rticks = None
                if "available" in item:
                    avail = bool(item["available"])
                    if rticks is None:
                        rticks = 0 if avail else 2700
                else:
                    if rticks is not None and rticks > 0:
                        avail = False
                    else:
                        avail = True
                        rticks = 0
                new_charms.append(
                    CharmState(id=cid, x=cx, y=cy, z=cz, available=avail, respawn_ticks=rticks)
                )
            self.charms = new_charms

    def _spawn_initial_motes(self) -> None:
        pool = list(self.night_map.mote_spawns)
        # Fisher-Yates deterministic shuffle
        for i in range(len(pool) - 1, 0, -1):
            j = self.rng.randint(0, i)
            pool[i], pool[j] = pool[j], pool[i]
        for x, y, z in pool[:20]:
            mid = f"M{self._next_mote_num}"
            self._next_mote_num += 1
            self.motes.append(MoteState(id=mid, x=x, y=y, z=z, kind="random"))

    @property
    def carry_capacity(self) -> int:
        base_cap = int(self.tuning["carry_capacity"])
        cap_max = int(self.tuning["capacity_max"])
        return min(cap_max, base_cap + 2 * self.successful_lights)

    def _is_safe_lantern(self, lantern: LanternState) -> bool:
        return lantern.lit and lantern.fuel_60 >= self._low_fuel_60

    def _is_inside_lit_safe_zone(self, x: float, z: float) -> bool:
        safe_r = float(self.tuning["safe_radius"])
        return any(
            self._is_safe_lantern(lantern) and dist_xz(x, z, lantern.x, lantern.z) < safe_r
            for lantern in self.lanterns
        )

    def _resolve_shade_move(self, sx: float, sz: float, sy: float, nx: float, nz: float) -> tuple[float, float, bool]:
        rx, rz, hit = self.night_map.resolve_horizontal_move(
            sx, sz, sy, nx, nz, allow_void=False
        )
        return rx, rz, hit

    def step(self, inp: InputState) -> list[dict]:
        """Advance simulation by one tick following Ticket-02 mandatory 12-step order."""
        if self.state in ("won", "lost"):
            return []

        # 1. Read input (process pause edge first)
        pause_edge = inp.pause and not self._prev_pause
        jump_edge = inp.jump and not self._prev_jump
        interact_edge = inp.interact and not self._prev_interact
        pulse_edge = inp.pulse and not self._prev_pulse
        dash_edge = inp.dash and not self._prev_dash
        self._prev_pause = inp.pause
        self._prev_jump = inp.jump
        self._prev_interact = inp.interact
        self._prev_pulse = inp.pulse
        self._prev_dash = inp.dash

        if self.state == "paused":
            self.tick += 1
            if not pause_edge:
                return []
            self.state = "playing"
            events: list[dict] = [
                {"type": "event", "tick": self.tick, "name": "resumed", "data": {}}
            ]
        else:
            if pause_edge:
                self.tick += 1
                self.state = "paused"
                return [{"type": "event", "tick": self.tick, "name": "paused", "data": {}}]
            self.tick += 1
            events = []

        # 2. Increment sim_tick & decrement timers
        self.sim_tick += 1
        if self.sim_tick == 1:
            events.append(
                {
                    "type": "event",
                    "tick": self.tick,
                    "name": "night_start",
                    "data": {"night": self.night},
                }
            )

        self.time_left_s = max(0.0, self.initial_time_left_s - (self.sim_tick / TICK_RATE))

        if self.invuln_ticks > 0:
            self.invuln_ticks -= 1
        if self.pulse_cooldown_ticks > 0:
            self.pulse_cooldown_ticks -= 1
        if self.dash_cooldown_ticks > 0:
            self.dash_cooldown_ticks -= 1
        if self.dash_ticks_left > 0:
            self.dash_ticks_left -= 1
        if self.charm_ticks > 0:
            self.charm_ticks -= 1

        if self.respawn_ticks > 0:
            self.respawn_ticks -= 1
            if self.respawn_ticks == 0:
                sx, sy, sz = self.night_map.spawn_pos
                self.player.x, self.player.y, self.player.z = sx, sy, sz
                self.player.vx, self.player.vy, self.player.vz = 0.0, 0.0, 0.0
                self.player.grounded = True
                self.player.yaw_deg = self.night_map.spawn_yaw_deg
                self.launched_airborne = False
                self.dash_ticks_left = 0
                self.invuln_ticks = round(float(self.tuning["invuln_s"]) * TICK_RATE)

        # Decrement dropped motes TTL & pickup delay
        kept_motes: list[MoteState] = []
        for mote in self.motes:
            if mote.pickup_delay_ticks > 0:
                mote.pickup_delay_ticks -= 1
            if mote.ttl_ticks is not None:
                mote.ttl_ticks -= 1
                if mote.ttl_ticks <= 0:
                    continue
            kept_motes.append(mote)
        self.motes = kept_motes

        # Charm respawn countdown
        for charm in self.charms:
            if not charm.available and charm.respawn_ticks > 0:
                charm.respawn_ticks -= 1
                if charm.respawn_ticks == 0:
                    charm.available = True

        # Shade state timers (Ticket-03: stun recovery always exits to wander)
        for shade in self.shades:
            shade.just_recovered_stun = False
            if shade.state_ticks_left > 0:
                shade.state_ticks_left -= 1
                if shade.state_ticks_left == 0:
                    if shade.state == "stunned":
                        shade.state = "wander"
                        shade.target_lantern_id = None
                        shade.drain_ticks = 0
                        shade.just_recovered_stun = True
                    elif shade.state in ("spawning", "recoil"):
                        d_pl = dist_xz(shade.x, shade.z, self.player.x, self.player.z)
                        shade.state = "chase" if (self.respawn_ticks == 0 and d_pl <= 12.0) else "wander"

        # Step 2 (v1.2): Deduct lantern fuel (passive decay + active Shades draining), extinguish <= 0
        self._step_lantern_fuel(events)

        # Drifter flee timers
        kept_drifters: list[DrifterState] = []
        for drifter in self.drifters:
            if drifter.state == "flee" and drifter.flee_ticks_left > 0:
                drifter.flee_ticks_left -= 1
                if drifter.flee_ticks_left == 0:
                    drifter.state = "removed"
                    continue
            if drifter.state != "removed":
                kept_drifters.append(drifter)
        self.drifters = kept_drifters

        # Wind cycle (Night 3)
        self._step_wind_timer()

        # 3. Move Mây (dash, run, jump, launch pads, wind) + fall check
        self._step_player_motion(inp, jump_edge, dash_edge, events)

        # 4. Pickup motes & charms (skip if waiting to respawn from fall)
        if self.respawn_ticks == 0:
            self._step_mote_pickup(events)
            self._step_charm_pickup(events)

        # 5. Interact with lanterns
        if interact_edge and self.respawn_ticks == 0:
            self._step_deposit(events)

        # 6. Update safe zones (push shades within 6m of lit lanterns)
        self._step_safe_zones()

        # 7. Pulse (Tỏa Sáng)
        if pulse_edge and self.respawn_ticks == 0:
            self._step_pulse(events)

        # 8. Move Shades & Drifters
        self._step_shades_movement()
        self._step_drifters_movement()

        # 9. Collisions: Drifters steal FIRST, then Shades hit (by ascending id)
        if self.respawn_ticks == 0:
            self._step_collisions(events)

        # 10. Scheduled spawns
        self._step_spawners(events)

        # 11. Win/Loss evaluation
        self._evaluate_outcome(events)

        return events

    def _step_lantern_fuel(self, events: list[dict]) -> None:
        draining_by_lantern: dict[str, list[ShadeState]] = {}
        for shade in sorted(self.shades, key=lambda s: (_numeric_suffix(s.id, "S"), s.id)):
            if shade.state == "drain" and shade.target_lantern_id is not None:
                draining_by_lantern.setdefault(shade.target_lantern_id, []).append(shade)

        for lantern in self.lanterns:
            if not lantern.lit:
                continue
            drainers = draining_by_lantern.get(lantern.id, [])
            active_drainers = [
                s
                for s in drainers
                if lantern.fuel_60 < self._low_fuel_60
                and dist_xz(s.x, s.z, lantern.x, lantern.z) <= 2.0 + 1e-9
            ]
            total_deduct = self._fuel_decay_60 + len(active_drainers) * self._drain_60
            lantern.fuel_60 = max(0, lantern.fuel_60 - total_deduct)
            fuel_display = r1(lantern.fuel_60 / FUEL_SCALE)

            for shade in active_drainers:
                shade.drain_ticks += 1
                if shade.drain_ticks % 60 == 0:
                    events.append(
                        {
                            "type": "event",
                            "tick": self.tick,
                            "name": "fuel_drain",
                            "data": {
                                "lantern_id": lantern.id,
                                "shade_id": shade.id,
                                "fuel": fuel_display,
                            },
                        }
                    )

            if lantern.fuel_60 <= 0:
                lantern.lit = False
                lantern.deposited = 0
                lantern.fuel_60 = 0
                lantern.ever_lit = True
                events.append(
                    {
                        "type": "event",
                        "tick": self.tick,
                        "name": "lantern_out",
                        "data": {"lantern_id": lantern.id},
                    }
                )
                for shade in drainers:
                    shade.state = "wander"
                    shade.target_lantern_id = None
                    shade.drain_ticks = 0

    def _step_wind_timer(self) -> None:
        if not self.wind_enabled:
            self.wind_active = False
            self.wind_warning = False
            return

        if self.wind_active:
            self.wind_ticks_left -= 1
            if self.wind_ticks_left <= 0:
                self.wind_active = False
                self.wind_next_tick += 1800

        if not self.wind_active:
            if self.sim_tick >= self.wind_next_tick:
                self.wind_active = True
                self.wind_warning = False
                self.wind_ticks_left = 300  # 5 seconds
                self.wind_dir_deg = self.rng.uniform(0.0, 360.0)
            elif self.sim_tick >= self.wind_next_tick - 120:
                self.wind_warning = True
            else:
                self.wind_warning = False

    def _step_player_motion(
        self, inp: InputState, jump_edge: bool, dash_edge: bool, events: list[dict]
    ) -> None:
        if self.respawn_ticks > 0:
            self.player.vx = 0.0
            self.player.vy = 0.0
            self.player.vz = 0.0
            return

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

        if abs(wx) > 1e-5 or abs(wz) > 1e-5:
            facing_yaw = math.degrees(math.atan2(wx, wz))
            self.player.yaw_deg = facing_yaw

        # Dash activation
        charm_active = self.charm_ticks > 0
        if (
            dash_edge
            and self.dash_ticks_left == 0
            and (charm_active or self.dash_cooldown_ticks == 0)
        ):
            dash_speed = float(self.tuning["dash_speed"])
            dash_dur = round(float(self.tuning["dash_duration_s"]) * TICK_RATE)
            dash_cd = 0 if charm_active else round(float(self.tuning["dash_cooldown_s"]) * TICK_RATE)
            if abs(wx) > 1e-5 or abs(wz) > 1e-5:
                dnorm = math.hypot(wx, wz)
                dx, dz = wx / dnorm, wz / dnorm
            else:
                yaw_r = math.radians(self.player.yaw_deg)
                dx, dz = math.sin(yaw_r), math.cos(yaw_r)

            self.dash_ticks_left = dash_dur
            self.dash_cooldown_ticks = dash_cd
            self.dash_vx = dx * dash_speed
            self.dash_vz = dz * dash_speed
            self.launched_airborne = False
            events.append({"type": "event", "tick": self.tick, "name": "dash", "data": {}})

        # Horizontal velocity
        if self.dash_ticks_left > 0:
            vx, vz = self.dash_vx, self.dash_vz
        elif self.launched_airborne:
            vx, vz = self.launch_vx, self.launch_vz
        else:
            speed = 7.2 if charm_active else float(self.tuning["player_speed"])
            vx, vz = wx * speed, wz * speed

        if self.wind_active:
            w_rad = math.radians(self.wind_dir_deg)
            vx += math.cos(w_rad) * 2.0
            vz += math.sin(w_rad) * 2.0

        self.player.vx = vx
        self.player.vz = vz

        nx = self.player.x + vx * DT
        nz = self.player.z + vz * DT
        rx, rz, _ = self.night_map.resolve_horizontal_move(
            self.player.x, self.player.z, self.player.y, nx, nz, allow_void=True
        )
        rx, rz = self.night_map.push_out_of_obstacles(rx, rz, self.player.y)
        self.player.x, self.player.z = rx, rz

        # Vertical motion (dash on air keeps altitude Y constant)
        prev_y = self.player.y
        if self.dash_ticks_left > 0 and not self.player.grounded:
            self.player.vy = 0.0
        else:
            if jump_edge and self.player.grounded:
                self.player.vy = JUMP_SPEED
                self.player.grounded = False

            ground_h = self.night_map.surface_height(
                self.player.x, self.player.z, current_y=self.player.y
            )
            if self.player.grounded and ground_h is not None and abs(ground_h - prev_y) <= 0.55:
                # Stay snapped on flat terrain or ramp
                self.player.y = ground_h
                self.player.vy = 0.0
                self.player.grounded = True
            else:
                self.player.grounded = False
                self.player.vy -= GRAVITY * DT
                self.player.y += self.player.vy * DT

                if (
                    ground_h is not None
                    and self.player.vy <= 0.0
                    and prev_y >= ground_h - 0.55
                    and self.player.y <= ground_h
                ):
                    self.player.y = ground_h
                    self.player.vy = 0.0
                    self.player.grounded = True
                    self.launched_airborne = False

        # Launch pad trigger (checked after motion)
        if not self.launched_airborne and self.dash_ticks_left == 0:
            for pad in self.night_map.launch_pads:
                if (
                    dist_xz(self.player.x, self.player.z, pad.x, pad.z) <= pad.radius
                    and abs(self.player.y - pad.y) <= 1.2
                ):
                    self.launched_airborne = True
                    self.launch_vx = pad.vx
                    self.launch_vz = pad.vz
                    self.player.vx = pad.vx
                    self.player.vy = pad.vy
                    self.player.vz = pad.vz
                    self.player.grounded = False
                    break

        # Fall off island (Y < -10): ignores invuln, triggers once, loses carried & 1 flame
        if (
            bool(self.tuning.get("fall_enabled", True))
            and self.player.y < -10.0
            and self.respawn_ticks == 0
        ):
            self.player.flames = max(0, self.player.flames - 1)
            lost = self.player.carried
            self.player.carried = 0
            self.launched_airborne = False
            self.dash_ticks_left = 0
            events.append(
                {
                    "type": "event",
                    "tick": self.tick,
                    "name": "player_hit",
                    "data": {
                        "by": "fall",
                        "flames": self.player.flames,
                        "dropped": 0,
                        "lost": lost,
                    },
                }
            )
            if self.player.flames > 0:
                self.respawn_ticks = 60

    def _step_mote_pickup(self, events: list[dict]) -> None:
        capacity = self.carry_capacity
        pickup_r = float(self.tuning["pickup_radius"])

        remaining: list[MoteState] = []
        for mote in self.motes:
            if (
                mote.pickup_delay_ticks == 0
                and self.player.carried < capacity
                and dist_xz(self.player.x, self.player.z, mote.x, mote.z) <= pickup_r
                and abs(self.player.y - mote.y) <= 1.5
            ):
                self.player.carried += 1
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

    def _step_charm_pickup(self, events: list[dict]) -> None:
        pickup_r = float(self.tuning["pickup_radius"])
        for charm in self.charms:
            if not charm.available:
                continue
            if (
                dist_xz(self.player.x, self.player.z, charm.x, charm.z) <= pickup_r
                and abs(self.player.y - charm.y) <= 1.5
            ):
                charm.available = False
                charm.respawn_ticks = 2700
                self.charm_ticks = 600
                self.dash_cooldown_ticks = 0
                events.append(
                    {
                        "type": "event",
                        "tick": self.tick,
                        "name": "charm_picked",
                        "data": {"charm_id": charm.id, "charm_ticks": 600},
                    }
                )

    def _push_shades_out_of_lantern(self, target: LanternState, safe_r: float) -> None:
        for shade in self.shades:
            if shade.state == "drain" and shade.target_lantern_id == target.id:
                shade.state = "wander"
                shade.target_lantern_id = None
                shade.drain_ticks = 0
            if dist_xz(shade.x, shade.z, target.x, target.z) < safe_r:
                shade.safe_push_ticks = 30

    def _step_deposit(self, events: list[dict]) -> None:
        if self.player.carried <= 0:
            return

        interact_r = float(self.tuning["interact_radius"])
        lantern_cost = int(self.tuning["lantern_cost"])
        relight_cost = int(self.tuning["relight_cost"])
        per_mote = int(self.score_cfg["per_mote"])
        per_lantern = int(self.score_cfg["per_lantern"])
        per_relight = int(self.score_cfg["per_relight"])
        safe_r = float(self.tuning["safe_radius"])

        candidates = [
            (
                dist_xz(self.player.x, self.player.z, lantern.x, lantern.z),
                _numeric_suffix(lantern.id, "L"),
                lantern.id,
                lantern,
            )
            for lantern in self.lanterns
            if (not lantern.lit or lantern.fuel_60 < self._fuel_max_60)
            and dist_xz(self.player.x, self.player.z, lantern.x, lantern.z) <= interact_r
        ]
        if not candidates:
            return
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        target = candidates[0][3]

        if not target.lit:
            is_relight = target.ever_lit
            req_cost = relight_cost if is_relight else lantern_cost
            needed = max(0, req_cost - target.deposited)
            if needed > 0:
                amount = min(self.player.carried, needed)
                self.player.carried -= amount
                target.deposited += amount
                self.score += amount * per_mote
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

            if target.deposited >= req_cost:
                target.lit = True
                target.ever_lit = True
                target.fuel_60 = self._fuel_max_60
                self.successful_lights += 1
                if is_relight:
                    target.relit_count += 1
                    self.score += per_relight
                else:
                    self.score += per_lantern
                events.append(
                    {
                        "type": "event",
                        "tick": self.tick,
                        "name": "lantern_lit",
                        "data": {"lantern_id": target.id, "relight": is_relight},
                    }
                )
                self._push_shades_out_of_lantern(target, safe_r)
        else:
            missing_60 = self._fuel_max_60 - target.fuel_60
            if missing_60 <= 0:
                return
            needed = (missing_60 + self._fuel_per_mote_60 - 1) // self._fuel_per_mote_60
            amount = min(self.player.carried, needed)
            if amount <= 0:
                return
            was_weak = target.fuel_60 < self._low_fuel_60
            self.player.carried -= amount
            target.fuel_60 = min(
                self._fuel_max_60,
                target.fuel_60 + amount * self._fuel_per_mote_60,
            )
            self.score += amount * per_mote
            events.append(
                {
                    "type": "event",
                    "tick": self.tick,
                    "name": "refuel",
                    "data": {
                        "lantern_id": target.id,
                        "amount": amount,
                        "fuel": r1(target.fuel_60 / FUEL_SCALE),
                    },
                }
            )
            if was_weak and target.fuel_60 >= self._low_fuel_60:
                self._push_shades_out_of_lantern(target, safe_r)

    def _step_safe_zones(self) -> None:
        safe_r = float(self.tuning["safe_radius"])
        safe_lanterns = [lantern for lantern in self.lanterns if self._is_safe_lantern(lantern)]
        if not safe_lanterns:
            for shade in self.shades:
                shade.safe_push_ticks = 0
            return

        for shade in self.shades:
            if shade.safe_push_ticks > 0:
                # Find closest safe lit lantern (fuel >= 30) within safe_r
                inside = [
                    (dist_xz(shade.x, shade.z, l.x, l.z), l)
                    for l in safe_lanterns
                    if dist_xz(shade.x, shade.z, l.x, l.z) < safe_r + SAFE_RADIUS_EPS
                ]
                if not inside:
                    shade.safe_push_ticks = 0
                    continue
                inside.sort(key=lambda item: item[0])
                d, lantern = inside[0]
                target_d = safe_r + SAFE_RADIUS_EPS
                rem = max(0.0, target_d - d)
                step_d = rem / shade.safe_push_ticks
                if d > 1e-9:
                    nx, nz = (shade.x - lantern.x) / d, (shade.z - lantern.z) / d
                else:
                    nx, nz = 1.0, 0.0
                cx, cz, _ = self._resolve_shade_move(
                    shade.x, shade.z, max(0.0, shade.y - 1.0), shade.x + nx * step_d, shade.z + nz * step_d
                )
                shade.x, shade.z = cx, cz
                gh = self.night_map.surface_height(shade.x, shade.z, max(0.0, shade.y - SHADE_DEFAULT_Y))
                if gh is not None:
                    shade.y = gh + SHADE_DEFAULT_Y
                shade.safe_push_ticks -= 1

    def _step_pulse(self, events: list[dict]) -> None:
        pulse_cost = int(self.tuning["pulse_cost"])
        if self.pulse_cooldown_ticks > 0 or self.player.carried < pulse_cost:
            return

        pulse_r = float(self.tuning["pulse_radius"])
        push_m = float(self.tuning["pulse_push_m"])
        stun_ticks = round(float(self.tuning["pulse_stun_s"]) * TICK_RATE)
        per_stun = int(self.score_cfg["per_stun"])
        per_stun_draining = int(self.score_cfg["per_stun_draining"])

        self.player.carried -= pulse_cost
        self.pulse_cooldown_ticks = round(float(self.tuning["pulse_cooldown_s"]) * TICK_RATE)

        origin_x, origin_y, origin_z = self.player.x, self.player.y + 0.8, self.player.z

        stunned_ids: list[str] = []
        for shade in self.shades:
            if shade.state == "spawning":
                continue
            if dist_3d(origin_x, origin_y, origin_z, shade.x, shade.y, shade.z) <= pulse_r:
                was_draining = shade.state == "drain"
                dx = shade.x - self.player.x
                dz = shade.z - self.player.z
                dh = math.hypot(dx, dz)
                if dh > 1e-9:
                    nx, nz = dx / dh, dz / dh
                else:
                    nx, nz = 1.0, 0.0
                shade.state = "stunned"
                shade.state_ticks_left = stun_ticks
                shade.safe_push_ticks = 0
                shade.target_lantern_id = None
                shade.drain_ticks = 0
                shade.knockback_ticks = 15
                shade.kb_vx = nx * (push_m / 15.0)
                shade.kb_vz = nz * (push_m / 15.0)
                stunned_ids.append(shade.id)
                self.score += per_stun_draining if was_draining else per_stun

        # Pulse affects Drifters too (3D distance <= 5m)
        for drifter in self.drifters:
            if drifter.state == "removed":
                continue
            if dist_3d(origin_x, origin_y, origin_z, drifter.x, drifter.y, drifter.z) <= pulse_r:
                if drifter.state == "chase":
                    drifter.state = "flee"
                    drifter.flee_ticks_left = 240
                elif drifter.state == "flee" and drifter.stolen > 0:
                    drop_amt = drifter.stolen
                    drifter.stolen = 0
                    drifter.flee_ticks_left = 120
                    gh = self.night_map.surface_height(drifter.x, drifter.z, drifter.y)
                    drop_y = gh if gh is not None else 0.0
                    for _ in range(drop_amt):
                        mid = f"M{self._next_mote_num}"
                        self._next_mote_num += 1
                        self.motes.append(
                            MoteState(
                                id=mid,
                                x=drifter.x,
                                y=drop_y,
                                z=drifter.z,
                                kind="dropped",
                                ttl_ticks=480,
                                pickup_delay_ticks=1,
                            )
                        )
                    events.append(
                        {
                            "type": "event",
                            "tick": self.tick,
                            "name": "drifter_drop",
                            "data": {"drifter_id": drifter.id, "amount": drop_amt},
                        }
                    )

        events.append(
            {
                "type": "event",
                "tick": self.tick,
                "name": "pulse",
                "data": {"stunned_ids": stunned_ids},
            }
        )

    def _clamp_shade_out_of_safe_zones(
        self, sx: float, sz: float, sy: float, lit_lanterns: list[LanternState]
    ) -> tuple[float, float]:
        safe_r = float(self.tuning["safe_radius"])
        nx, nz = sx, sz
        for _ in range(2):
            for lantern in lit_lanterns:
                lx = nx - lantern.x
                lz = nz - lantern.z
                ld = math.hypot(lx, lz)
                if ld < safe_r:
                    target_d = safe_r + SAFE_RADIUS_EPS
                    if ld > 1e-9:
                        cand_x = lantern.x + (lx / ld) * target_d
                        cand_z = lantern.z + (lz / ld) * target_d
                    else:
                        cand_x = lantern.x + target_d
                        cand_z = lantern.z
                    nx, nz, _ = self._resolve_shade_move(nx, nz, max(0.0, sy - 1.0), cand_x, cand_z)
        return nx, nz

    def _step_shades_movement(self) -> None:
        shade_speed = 4.5 if self.night == 3 else float(self.tuning["shade_speed"])
        safe_lanterns = [lantern for lantern in self.lanterns if self._is_safe_lantern(lantern)]
        lantern_by_id = {lantern.id: lantern for lantern in self.lanterns}
        weak_lanterns = [
            lantern for lantern in self.lanterns if lantern.lit and lantern.fuel_60 < self._low_fuel_60
        ]
        unlit_lanterns = [lantern for lantern in self.lanterns if not lantern.lit]

        for shade in self.shades:
            if shade.state == "spawning":
                continue
            if shade.safe_push_ticks > 0:
                if shade.state == "drain":
                    shade.state = "wander"
                    shade.target_lantern_id = None
                    shade.drain_ticks = 0
                continue

            ground_ref = max(0.0, shade.y - SHADE_DEFAULT_Y)

            if shade.state == "stunned":
                if shade.knockback_ticks > 0:
                    shade.knockback_ticks -= 1
                    rx, rz, hit = self._resolve_shade_move(
                        shade.x,
                        shade.z,
                        ground_ref,
                        shade.x + shade.kb_vx,
                        shade.z + shade.kb_vz,
                    )
                    shade.x, shade.z = rx, rz
                    gh = self.night_map.surface_height(shade.x, shade.z, ground_ref)
                    if gh is not None:
                        shade.y = gh + SHADE_DEFAULT_Y
                    if hit:
                        shade.knockback_ticks = 0
                continue

            if shade.state == "recoil":
                rx, rz, _ = self._resolve_shade_move(
                    shade.x,
                    shade.z,
                    ground_ref,
                    shade.x + shade.recoil_vx,
                    shade.z + shade.recoil_vz,
                )
                shade.x, shade.z = rx, rz
                shade.x, shade.z = self._clamp_shade_out_of_safe_zones(
                    shade.x, shade.z, shade.y, safe_lanterns
                )
                gh = self.night_map.surface_height(shade.x, shade.z, ground_ref)
                if gh is not None:
                    shade.y = gh + SHADE_DEFAULT_Y
                continue

            d_player = dist_xz(shade.x, shade.z, self.player.x, self.player.z)

            if shade.state == "drain":
                target_l = (
                    lantern_by_id.get(shade.target_lantern_id)
                    if shade.target_lantern_id is not None
                    else None
                )
                if (
                    target_l is None
                    or not target_l.lit
                    or target_l.fuel_60 >= self._low_fuel_60
                    or dist_xz(shade.x, shade.z, target_l.x, target_l.z) > 2.0 + 1e-9
                ):
                    shade.state = "wander"
                    shade.target_lantern_id = None
                    shade.drain_ticks = 0
                elif self.respawn_ticks == 0 and d_player <= 6.0:
                    shade.state = "chase"
                    shade.target_lantern_id = None
                    shade.drain_ticks = 0
                else:
                    continue

            # Transition between wander and chase (detect 12m, drop 18m)
            if self.respawn_ticks > 0:
                shade.state = "wander"
                shade.target_lantern_id = None
                shade.drain_ticks = 0
            elif shade.state == "wander" and not shade.just_recovered_stun and d_player <= 12.0:
                shade.state = "chase"
                shade.target_lantern_id = None
                shade.drain_ticks = 0
            elif shade.state == "chase" and d_player > 18.0:
                shade.state = "wander"

            weak_target: LanternState | None = None
            if shade.state == "chase":
                tx, tz = self.player.x, self.player.z
                step_len = shade_speed * DT
            else:
                if weak_lanterns:
                    weak_ranked = [
                        (dist_xz(shade.x, shade.z, l.x, l.z), _numeric_suffix(l.id, "L"), l.id, l)
                        for l in weak_lanterns
                    ]
                    weak_ranked.sort(key=lambda item: (item[0], item[1], item[2]))
                    d_weak, _, _, weak_target = weak_ranked[0]
                    shade.target_lantern_id = weak_target.id
                    if d_weak <= 2.0 and not shade.just_recovered_stun:
                        shade.state = "drain"
                        shade.drain_ticks = 0
                        continue
                    tx, tz = weak_target.x, weak_target.z
                    step_len = shade_speed * DT
                elif unlit_lanterns:
                    unlit_ranked = [
                        (dist_xz(shade.x, shade.z, l.x, l.z), _numeric_suffix(l.id, "L"), l.id, l)
                        for l in unlit_lanterns
                    ]
                    unlit_ranked.sort(key=lambda item: (item[0], item[1], item[2]))
                    d_unlit, _, _, unlit_target = unlit_ranked[0]
                    shade.target_lantern_id = None
                    if d_unlit > 2.0:
                        tx, tz = unlit_target.x, unlit_target.z
                    else:
                        if (
                            shade.wander_timer <= 0
                            or dist_xz(shade.x, shade.z, shade.wander_x, shade.wander_z) < 0.5
                        ):
                            ang = self.rng.uniform(0.0, math.tau)
                            rad = self.rng.uniform(1.5, 4.5)
                            shade.wander_x = unlit_target.x + math.cos(ang) * rad
                            shade.wander_z = unlit_target.z + math.sin(ang) * rad
                            shade.wander_timer = 120
                        shade.wander_timer -= 1
                        tx, tz = shade.wander_x, shade.wander_z
                    step_len = (shade_speed * 0.5) * DT
                else:
                    shade.target_lantern_id = None
                    if (
                        shade.wander_timer <= 0
                        or dist_xz(shade.x, shade.z, shade.wander_x, shade.wander_z) < 0.5
                    ):
                        ang = self.rng.uniform(0.0, math.tau)
                        rad = self.rng.uniform(3.0, 9.0)
                        shade.wander_x = shade.home_x + math.cos(ang) * rad
                        shade.wander_z = shade.home_z + math.sin(ang) * rad
                        shade.wander_timer = 120
                    shade.wander_timer -= 1
                    tx, tz = shade.wander_x, shade.wander_z
                    step_len = (shade_speed * 0.5) * DT

            dx, dz = tx - shade.x, tz - shade.z
            d = math.hypot(dx, dz)
            if d > 1e-9:
                ml = min(d, step_len)
                cand_x = shade.x + (dx / d) * ml
                cand_z = shade.z + (dz / d) * ml
                rx, rz, hit = self._resolve_shade_move(shade.x, shade.z, ground_ref, cand_x, cand_z)
                shade.x, shade.z = rx, rz
                if hit and shade.state == "wander" and weak_target is None:
                    shade.wander_timer = 0

            shade.x, shade.z = self._clamp_shade_out_of_safe_zones(
                shade.x, shade.z, shade.y, safe_lanterns
            )
            gh = self.night_map.surface_height(shade.x, shade.z, ground_ref)
            if gh is not None:
                shade.y = gh + SHADE_DEFAULT_Y

            if (
                weak_target is not None
                and shade.state == "wander"
                and not shade.just_recovered_stun
                and dist_xz(shade.x, shade.z, weak_target.x, weak_target.z) <= 2.0
            ):
                shade.state = "drain"
                shade.target_lantern_id = weak_target.id
                shade.drain_ticks = 0

    def _step_drifters_movement(self) -> None:
        for drifter in self.drifters:
            if drifter.state == "removed":
                continue

            d_player = dist_xz(drifter.x, drifter.z, self.player.x, self.player.z)
            if drifter.state == "idle":
                if not drifter.has_stolen and self.player.carried >= 5 and d_player <= 15.0 and self.respawn_ticks == 0:
                    drifter.state = "chase"
            elif drifter.state == "chase":
                if drifter.has_stolen or self.player.carried < 5 or d_player > 15.0 or self.respawn_ticks > 0:
                    drifter.state = "idle"

            if drifter.state == "chase":
                dx, dz = self.player.x - drifter.x, self.player.z - drifter.z
                d = math.hypot(dx, dz)
                if d > 1e-9:
                    ml = min(d, 7.0 * DT)
                    drifter.x += (dx / d) * ml
                    drifter.z += (dz / d) * ml
            elif drifter.state == "flee":
                dx, dz = drifter.x - self.player.x, drifter.z - self.player.z
                d = math.hypot(dx, dz)
                if d > 1e-9:
                    nx, nz = dx / d, dz / d
                else:
                    nx, nz = 1.0, 0.0
                drifter.x += nx * (7.0 * DT)
                drifter.z += nz * (7.0 * DT)
            else:
                # idle slow drift (2.0 m/s) around home point
                drifter.wander_angle += 0.02
                tx = drifter.home_x + math.cos(drifter.wander_angle) * 6.0
                tz = drifter.home_z + math.sin(drifter.wander_angle) * 6.0
                dx, dz = tx - drifter.x, tz - drifter.z
                d = math.hypot(dx, dz)
                if d > 1e-9:
                    ml = min(d, 2.0 * DT)
                    drifter.x += (dx / d) * ml
                    drifter.z += (dz / d) * ml

    def _step_collisions(self, events: list[dict]) -> None:
        # 1. Drifters steal FIRST (natural ascending id; ignores invuln & safe_radius)
        for drifter in sorted(self.drifters, key=lambda d: (_numeric_suffix(d.id, "D"), d.id)):
            if drifter.state != "chase" or drifter.has_stolen or self.player.carried <= 0:
                continue
            if dist_xz(self.player.x, self.player.z, drifter.x, drifter.z) <= 1.2:
                amount = min(3, self.player.carried)
                self.player.carried -= amount
                drifter.stolen = amount
                drifter.has_stolen = True
                drifter.state = "flee"
                drifter.flee_ticks_left = 240
                events.append(
                    {
                        "type": "event",
                        "tick": self.tick,
                        "name": "drifter_steal",
                        "data": {
                            "drifter_id": drifter.id,
                            "amount": amount,
                            "carried": self.player.carried,
                        },
                    }
                )

        # 2. Shades hit SECOND (natural ascending id; max 1 flame lost per tick)
        if self.invuln_ticks > 0:
            return

        hit_r = float(self.tuning["shade_hit_radius"])
        drop_ratio = float(self.tuning["hit_drop_ratio"])
        invuln_ticks = round(float(self.tuning["invuln_s"]) * TICK_RATE)

        for shade in sorted(self.shades, key=lambda s: (_numeric_suffix(s.id, "S"), s.id)):
            if (
                shade.state in ("spawning", "stunned", "recoil")
                or shade.safe_push_ticks > 0
                or self._is_inside_lit_safe_zone(shade.x, shade.z)
            ):
                continue
            ground_diff = abs(self.player.y - (shade.y - SHADE_DEFAULT_Y))
            if (
                dist_xz(self.player.x, self.player.z, shade.x, shade.z) <= hit_r
                and ground_diff <= 1.5
            ):
                self.player.flames = max(0, self.player.flames - 1)
                dropped = int(math.floor(self.player.carried * drop_ratio + 1e-9))
                self.player.carried -= dropped
                self.invuln_ticks = invuln_ticks

                # Spawn dropped motes on ring 1.5-2.5m (pickable from next tick)
                for _ in range(dropped):
                    self._spawn_dropped_mote_near_player()

                # Shade recoils 2m over 60 ticks
                dx, dz = shade.x - self.player.x, shade.z - self.player.z
                dh = math.hypot(dx, dz)
                if dh > 1e-9:
                    rx, rz = dx / dh, dz / dh
                else:
                    rx, rz = 1.0, 0.0
                shade.state = "recoil"
                shade.state_ticks_left = 60
                shade.recoil_vx = rx * (2.0 / 60.0)
                shade.recoil_vz = rz * (2.0 / 60.0)

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
                break

    def _spawn_dropped_mote_near_player(self) -> None:
        mx, my, mz = self.player.x, self.player.y, self.player.z
        for _ in range(12):
            ang = self.rng.uniform(0.0, math.tau)
            rad = self.rng.uniform(1.5, 2.5)
            cx = self.player.x + math.cos(ang) * rad
            cz = self.player.z + math.sin(ang) * rad
            h = self.night_map.surface_height(cx, cz, current_y=self.player.y + 0.5)
            if (
                h is not None
                and abs(h - self.player.y) <= 1.5
                and not self.night_map.is_blocked(cx, cz, self.player.y, allow_void=False)
            ):
                mx, my, mz = cx, h, cz
                break
        mid = f"M{self._next_mote_num}"
        self._next_mote_num += 1
        self.motes.append(
            MoteState(
                id=mid,
                x=mx,
                y=my,
                z=mz,
                kind="dropped",
                ttl_ticks=480,
                pickup_delay_ticks=1,
            )
        )

    def _step_spawners(self, events: list[dict]) -> None:
        # Motes: tick 240, 480, ... if < 30 at an empty spawn point
        if self.random_motes and self.sim_tick % 240 == 0 and len(self.motes) < 30:
            empty_points = [
                pt
                for pt in self.night_map.mote_spawns
                if not any(
                    dist_xz(m.x, m.z, pt[0], pt[2]) < 0.5 and abs(m.y - pt[1]) < 0.5
                    for m in self.motes
                )
            ]
            if empty_points:
                idx = self.rng.randint(0, len(empty_points) - 1)
                sx, sy, sz = empty_points[idx]
                mid = f"M{self._next_mote_num}"
                self._next_mote_num += 1
                self.motes.append(MoteState(id=mid, x=sx, y=sy, z=sz, kind="random"))

        # Shades: 2 at tick 300, then 1 every shade_interval_ticks (300 + k*interval)
        if self.random_shades and self.sim_tick >= 300:
            interval = self.night_map.shade_interval_ticks
            if self.sim_tick == 300:
                spawn_count = min(2, self.night_map.shade_max - len(self.shades))
            elif (self.sim_tick - 300) % interval == 0 and len(self.shades) < self.night_map.shade_max:
                spawn_count = 1
            else:
                spawn_count = 0

            for _ in range(spawn_count):
                valid_pts = [
                    pt
                    for pt in self.night_map.shade_spawns
                    if dist_xz(pt[0], pt[2], self.player.x, self.player.z) >= 15.0
                    and not self._is_inside_lit_safe_zone(pt[0], pt[2])
                    and not any(dist_xz(s.x, s.z, pt[0], pt[2]) < 1.5 for s in self.shades)
                ]
                if not valid_pts:
                    break
                idx = self.rng.randint(0, len(valid_pts) - 1)
                sx, sy, sz = valid_pts[idx]
                sid = f"S{self._next_shade_num}"
                self._next_shade_num += 1
                self.shades.append(
                    ShadeState(
                        id=sid,
                        x=sx,
                        y=sy + SHADE_DEFAULT_Y,
                        z=sz,
                        home_x=sx,
                        home_z=sz,
                        state="spawning",
                        state_ticks_left=30,
                        wander_x=sx,
                        wander_z=sz,
                    )
                )
                events.append(
                    {
                        "type": "event",
                        "tick": self.tick,
                        "name": "shade_spawned",
                        "data": {"id": sid},
                    }
                )

        # Drifters (Night 2 & 3): tick 1200, 2400, ... max 2
        if (
            self.random_drifters
            and self.night_map.drifter_max > 0
            and self.sim_tick % 1200 == 0
            and len(self.drifters) < self.night_map.drifter_max
        ):
            pts = self.night_map.drifter_spawns
            if pts:
                idx = self.rng.randint(0, len(pts) - 1)
                dx, dy, dz = pts[idx]
                did = f"D{self._next_drifter_num}"
                self._next_drifter_num += 1
                self.drifters.append(
                    DrifterState(
                        id=did,
                        x=dx,
                        y=dy,
                        z=dz,
                        home_x=dx,
                        home_z=dz,
                        state="idle",
                        wander_angle=self.rng.uniform(0.0, math.tau),
                    )
                )

    def _evaluate_outcome(self, events: list[dict]) -> None:
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
            return

        if self.time_left_s <= 1e-9:
            self.time_left_s = 0.0
            lit_lanterns = [lantern for lantern in self.lanterns if lantern.lit]
            if len(lit_lanterns) >= self.win_threshold:
                self.state = "won"
                self.game_over_reason = "dawn_survived"
                per_dawn_lantern = int(self.score_cfg["per_dawn_lit_lantern"])
                per_flame_left = int(self.score_cfg["per_flame_left"])
                for lantern in lit_lanterns:
                    self.score += per_dawn_lantern + (lantern.fuel_60 // FUEL_SCALE)
                self.score += self.player.flames * per_flame_left
                events.append(
                    {
                        "type": "event",
                        "tick": self.tick,
                        "name": "game_over",
                        "data": {"result": "won", "reason": "dawn_survived"},
                    }
                )
            else:
                self.state = "lost"
                self.game_over_reason = "dawn"
                events.append(
                    {
                        "type": "event",
                        "tick": self.tick,
                        "name": "game_over",
                        "data": {"result": "lost", "reason": "dawn"},
                    }
                )

    def snapshot(self) -> dict:
        """Return Test Contract v1.2 JSON-serializable snapshot."""
        return {
            "type": "snapshot",
            "tick": self.tick,
            "sim_tick": self.sim_tick,
            "night": self.night,
            "state": self.state,
            "time_left_s": r3(self.time_left_s),
            "score": self.score,
            "wind": {
                "active": self.wind_active,
                "dir_deg": r3(self.wind_dir_deg),
            },
            "player": {
                "pos": [r3(self.player.x), r3(self.player.y), r3(self.player.z)],
                "vel": [r3(self.player.vx), r3(self.player.vy), r3(self.player.vz)],
                "grounded": self.player.grounded,
                "flames": self.player.flames,
                "carried": self.player.carried,
                "capacity": self.carry_capacity,
                "invuln": self.invuln_ticks > 0,
                "dash_cd_s": r3(self.dash_cooldown_ticks / TICK_RATE),
                "pulse_cd_s": r3(self.pulse_cooldown_ticks / TICK_RATE),
                "charm_s": r3(self.charm_ticks / TICK_RATE),
            },
            "lanterns": [
                {
                    "id": lantern.id,
                    "pos": [r3(lantern.x), r3(lantern.y), r3(lantern.z)],
                    "lit": lantern.lit,
                    "deposited": lantern.deposited,
                    "fuel": r1(lantern.fuel_60 / FUEL_SCALE) if lantern.lit else 0.0,
                    "ever_lit": lantern.ever_lit,
                    "relit_count": lantern.relit_count,
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
                    "kind": mote.kind,
                    "ttl_s": None if mote.ttl_ticks is None else r3(mote.ttl_ticks / TICK_RATE),
                }
                for mote in self.motes
            ],
            "drifters": [
                {
                    "id": drifter.id,
                    "pos": [r3(drifter.x), r3(drifter.y), r3(drifter.z)],
                    "state": drifter.state,
                    "stolen": drifter.stolen,
                }
                for drifter in self.drifters
            ],
            "charms": [
                {
                    "id": charm.id,
                    "available": charm.available,
                    "respawn_s": r3(charm.respawn_ticks / TICK_RATE),
                }
                for charm in self.charms
            ],
        }

    def end_record(self) -> dict:
        """Return Test Contract v1.2 final JSONL end object."""
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
        snap["respawn_s"] = r3(self.respawn_ticks / TICK_RATE)
        snap["wind_warning"] = self.wind_warning
        snap["island_name"] = self.night_map.name
        snap["island_quote"] = self.night_map.quote
        snap["lit_count"] = sum(1 for lantern in self.lanterns if lantern.lit)
        snap["lantern_total"] = len(self.lanterns)
        snap["win_threshold"] = self.win_threshold
        snap["successful_lights"] = self.successful_lights
        snap["game_over_reason"] = self.game_over_reason
        snap["charm_positions"] = {
            charm.id: [r3(charm.x), r3(charm.y), r3(charm.z)] for charm in self.charms
        }
        snap["launch_pads"] = [
            {"pos": [r3(p.x), r3(p.y), r3(p.z)], "radius": r3(p.radius)}
            for p in self.night_map.launch_pads
        ]
        snap["tuning"] = self.tuning
        return snap
