"""Canonical map geometry, ramps, bridges, launch pads, and spawn tables for Nights 1-3."""

from __future__ import annotations

import math
from dataclasses import dataclass


def polar_xz(
    radius: float, deg: float, cx: float = 0.0, cz: float = 0.0
) -> tuple[float, float]:
    """Convert polar coordinates (CCW from +X on XZ plane) to (x, z)."""
    rad = math.radians(deg)
    return cx + radius * math.cos(rad), cz + radius * math.sin(rad)


@dataclass(frozen=True)
class LaunchPad:
    x: float
    y: float
    z: float
    radius: float
    vx: float
    vy: float
    vz: float


class NightMap:
    """Terrain height queries, obstacles, launch pads, and spawn points for a Night."""

    def __init__(
        self,
        night: int,
        name: str,
        quote: str,
        spawn_pos: tuple[float, float, float],
        spawn_yaw_deg: float,
        lantern_positions: tuple[tuple[str, tuple[float, float, float]], ...],
        mote_spawns: tuple[tuple[float, float, float], ...],
        shade_spawns: tuple[tuple[float, float, float], ...],
        shade_interval_ticks: int,
        shade_max: int,
        shade_speed: float,
        drifter_spawns: tuple[tuple[float, float, float], ...],
        drifter_max: int,
        charms: tuple[tuple[str, tuple[float, float, float]], ...],
        launch_pads: tuple[LaunchPad, ...],
        wind_enabled_default: bool,
        bounds_radius: float,
    ) -> None:
        self.night = night
        self.name = name
        self.quote = quote
        self.spawn_pos = spawn_pos
        self.spawn_yaw_deg = spawn_yaw_deg
        self.lantern_positions = lantern_positions
        self.valid_lantern_ids: frozenset[str] = frozenset(
            lid for lid, _ in lantern_positions
        )
        self.mote_spawns = mote_spawns
        self.shade_spawns = shade_spawns
        self.shade_interval_ticks = shade_interval_ticks
        self.shade_max = shade_max
        self.shade_speed = shade_speed
        self.drifter_spawns = drifter_spawns
        self.drifter_max = drifter_max
        self.charms = charms
        self.launch_pads = launch_pads
        self.wind_enabled_default = wind_enabled_default
        self.bounds_radius = bounds_radius

    def surface_height(self, x: float, z: float, current_y: float = 999.0) -> float | None:
        """Return walkable ground height Y at (x, z), or None if over cloud-sea void."""
        if self.night == 1:
            return 0.0 if (x * x + z * z) <= 40.0 * 40.0 + 1e-6 else None

        if self.night == 2:
            if (x * x + z * z) <= 28.0 * 28.0 + 1e-6:
                return 0.0
            dx_b = x - 70.0
            if (dx_b * dx_b + z * z) <= 28.0 * 28.0 + 1e-6:
                return 0.0
            if (26.0 - 1e-6 <= x <= 44.0 + 1e-6) and (-2.0 - 1e-6 <= z <= 2.0 + 1e-6):
                return 0.0
            return None

        # Night 3 — Đảo Chuông
        r = math.hypot(x, z)
        if r > 45.0 + 1e-6:
            return None

        best_h = 0.0
        if r <= 8.0 + 1e-6:
            best_h = 6.0
        elif 12.0 - 1e-6 <= r <= 24.0 + 1e-6 and z > 0.0:
            best_h = 3.0

        for deg in (30.0, 150.0):
            rad = math.radians(deg)
            ca, sa = math.cos(rad), math.sin(rad)
            s = x * ca + z * sa
            t = -x * sa + z * ca
            if 23.6 <= s <= 30.0 + 1e-6 and abs(t) <= 1.5 + 1e-6:
                ramp_h = 3.0 * min(1.0, max(0.0, (30.0 - s) / 6.0))
                if ramp_h > best_h and ramp_h <= current_y + 1.0:
                    best_h = ramp_h
        return best_h

    def is_blocked(self, x: float, z: float, y: float, allow_void: bool = True) -> bool:
        """Return True if (x, z) at altitude y hits Bell Tower, cliff face, or disallowed void."""
        if self.night == 3:
            r = math.hypot(x, z)
            if r < 2.0 - 1e-6 and y < 14.0:
                return True

        h = self.surface_height(x, z, current_y=y)
        if h is None:
            return not allow_void
        if h > y + 0.55:
            return True
        return False

    def push_out_of_obstacles(self, x: float, z: float, y: float) -> tuple[float, float]:
        """Ensure (x, z) is clear of the solid Bell Tower cylinder on Night 3."""
        if self.night == 3 and y < 14.0:
            r = math.hypot(x, z)
            if r < 2.0:
                if r > 1e-9:
                    scale = 2.002 / r
                    return x * scale, z * scale
                return 0.0, 2.002
        return x, z

    def resolve_horizontal_move(
        self,
        x0: float,
        z0: float,
        y: float,
        x1: float,
        z1: float,
        allow_void: bool = True,
    ) -> tuple[float, float, bool]:
        """Attempt move (x0, z0) -> (x1, z1) at height y; slide along cliffs/Bell Tower."""
        if not self.is_blocked(x1, z1, y, allow_void=allow_void):
            return x1, z1, False

        # Try axis slides for smooth wall sliding
        if not self.is_blocked(x1, z0, y, allow_void=allow_void):
            return x1, z0, True
        if not self.is_blocked(x0, z1, y, allow_void=allow_void):
            return x0, z1, True

        # Try circular tangent slide around Bell Tower / circular cliff edges on Night 3
        if self.night == 3:
            r0 = math.hypot(x0, z0)
            if r0 > 1e-6:
                tx, tz = -z0 / r0, x0 / r0
                dx, dz = x1 - x0, z1 - z0
                proj = dx * tx + dz * tz
                sx, sz = x0 + tx * proj, z0 + tz * proj
                if not self.is_blocked(sx, sz, y, allow_void=allow_void):
                    return sx, sz, True

        return x0, z0, True


def _build_night_1() -> NightMap:
    motes: list[tuple[float, float, float]] = []
    for i in range(8):
        x, z = polar_xz(12.0, i * 45.0)
        motes.append((x, 0.0, z))
    for i in range(16):
        x, z = polar_xz(33.0, i * 22.5)
        motes.append((x, 0.0, z))

    shades = tuple(
        (polar_xz(37.0, 15.0 + i * 30.0)[0], 0.0, polar_xz(37.0, 15.0 + i * 30.0)[1])
        for i in range(12)
    )
    lanterns = (
        ("L1", (0.0, 0.0, 25.0)),
        ("L2", (23.8, 0.0, 7.7)),
        ("L3", (14.7, 0.0, -20.2)),
        ("L4", (-14.7, 0.0, -20.2)),
        ("L5", (-23.8, 0.0, 7.7)),
    )
    return NightMap(
        night=1,
        name="Đảo Bến",
        quote="Ông Đăng: \"Đêm nay sương đen vừa kéo về Đảo Bến. Mây hãy gom đom đóm thắp lại 5 ngọn đèn cổ.\"",
        spawn_pos=(0.0, 0.0, 0.0),
        spawn_yaw_deg=0.0,
        lantern_positions=lanterns,
        mote_spawns=tuple(motes),
        shade_spawns=shades,
        shade_interval_ticks=480,
        shade_max=6,
        shade_speed=4.0,
        drifter_spawns=(),
        drifter_max=0,
        charms=(),
        launch_pads=(),
        wind_enabled_default=False,
        bounds_radius=40.0,
    )


def _build_night_2() -> NightMap:
    motes: list[tuple[float, float, float]] = []
    shades: list[tuple[float, float, float]] = []
    for cx in (0.0, 70.0):
        for i in range(4):
            x, z = polar_xz(10.0, i * 90.0, cx=cx)
            motes.append((x, 0.0, z))
        for i in range(8):
            x, z = polar_xz(22.0, i * 45.0, cx=cx)
            motes.append((x, 0.0, z))
        for i in range(8):
            x, z = polar_xz(26.0, 22.5 + i * 45.0, cx=cx)
            shades.append((x, 0.0, z))

    lanterns = (
        ("L1", (0.0, 0.0, 20.0)),
        ("L2", (17.0, 0.0, -10.0)),
        ("L3", (-17.0, 0.0, -10.0)),
        ("L4", (70.0, 0.0, 20.0)),
        ("L5", (87.0, 0.0, -10.0)),
        ("L6", (53.0, 0.0, -10.0)),
    )

    # Pad 1: (20,0,18) -> toward B (70,0); Pad 2: (50,0,-18) -> toward A (0,0)
    d1 = math.hypot(50.0, -18.0)
    d2 = math.hypot(-50.0, 18.0)
    pads = (
        LaunchPad(20.0, 0.0, 18.0, 1.0, 24.0 * 50.0 / d1, 14.0, 24.0 * (-18.0) / d1),
        LaunchPad(50.0, 0.0, -18.0, 1.0, 24.0 * (-50.0) / d2, 14.0, 24.0 * 18.0 / d2),
    )
    drifters = (
        (12.0, 1.2, -16.0),
        (58.0, 1.2, 16.0),
        (35.0, 1.2, 8.0),
        (35.0, 1.2, -8.0),
        (-15.0, 1.2, 14.0),
        (85.0, 1.2, -14.0),
    )
    return NightMap(
        night=2,
        name="Đảo Cau",
        quote="Ông Đăng: \"Cầu tre nối hai bờ Đảo Cau giữa biển mây. Coi chừng Gió Lạc rình rập và tận dụng Bùa Gió!\"",
        spawn_pos=(0.0, 0.0, 0.0),
        spawn_yaw_deg=0.0,
        lantern_positions=lanterns,
        mote_spawns=tuple(motes),
        shade_spawns=tuple(shades),
        shade_interval_ticks=420,
        shade_max=8,
        shade_speed=4.0,
        drifter_spawns=drifters,
        drifter_max=2,
        charms=(("C1", (35.0, 0.0, 0.0)),),
        launch_pads=pads,
        wind_enabled_default=False,
        bounds_radius=100.0,
    )


def _build_night_3() -> NightMap:
    motes: list[tuple[float, float, float]] = []
    # Tier 0: 18 points r=34 every 20 deg
    for i in range(18):
        x, z = polar_xz(34.0, i * 20.0)
        motes.append((x, 0.0, z))
    # Tier 1: 8 points r=18 (20..160 deg) at Y=3
    for i in range(1, 9):
        x, z = polar_xz(18.0, i * 20.0)
        motes.append((x, 3.0, z))
    # Tier 2: 4 points r=5 (45, 135, 225, 315) at Y=6
    for deg in (45.0, 135.0, 225.0, 315.0):
        x, z = polar_xz(5.0, deg)
        motes.append((x, 6.0, z))

    shades = tuple(
        (polar_xz(43.0, i * 22.5)[0], 0.0, polar_xz(43.0, i * 22.5)[1])
        for i in range(16)
    )
    lanterns = (
        ("L1", (0.0, 6.0, 6.0)),
        ("L2", (18.0, 3.0, 10.0)),
        ("L3", (-18.0, 3.0, 10.0)),
        ("L4", (35.0, 0.0, -10.0)),
        ("L5", (-35.0, 0.0, -10.0)),
        ("L6", (20.0, 0.0, -35.0)),
        ("L7", (-20.0, 0.0, -35.0)),
    )
    pads = (LaunchPad(0.0, 3.0, 13.0, 1.0, 0.0, 12.0, -8.0),)
    drifters = (
        (0.0, 4.2, 18.0),
        (25.0, 1.2, -15.0),
        (-25.0, 1.2, -15.0),
        (28.0, 1.2, 18.0),
        (-28.0, 1.2, 18.0),
        (0.0, 7.2, 5.0),
    )
    return NightMap(
        night=3,
        name="Đảo Chuông",
        quote="Ông Đăng: \"Đêm cuối trên Đảo Chuông ba tầng! Hãy giữ vững ngọn lửa qua cơn gió mạnh tới bình minh!\"",
        spawn_pos=(0.0, 0.0, -10.0),
        spawn_yaw_deg=0.0,
        lantern_positions=lanterns,
        mote_spawns=tuple(motes),
        shade_spawns=shades,
        shade_interval_ticks=360,
        shade_max=10,
        shade_speed=4.5,
        drifter_spawns=drifters,
        drifter_max=2,
        charms=(("C1", (30.0, 0.0, 25.0)), ("C2", (-30.0, 0.0, 25.0))),
        launch_pads=pads,
        wind_enabled_default=True,
        bounds_radius=45.0,
    )


_MAPS: dict[int, NightMap] = {
    1: _build_night_1(),
    2: _build_night_2(),
    3: _build_night_3(),
}


def get_night_map(night: int) -> NightMap:
    """Return canonical NightMap for night 1, 2, or 3."""
    if night not in _MAPS:
        raise ValueError(f"Unsupported night={night}; expected 1, 2, or 3")
    return _MAPS[night]
