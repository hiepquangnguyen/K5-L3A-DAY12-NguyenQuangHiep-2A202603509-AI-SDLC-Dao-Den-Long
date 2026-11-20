# Changelog

All notable changes and Test Contract migrations for **Đảo Đèn Lồng** are documented here.

---

## [1.0.0] — Phase 4: TICKET-04 "Bình minh: phát hành v1.0.0" (Contract v1.3)

### Added
- **3D Benchmark Mode (`src/bench.py`, `web/bench.html`, `web/bench.js`):**
  - Contract `v1.3` CLI `python3 -m src.bench --seed 42 --duration 30 --out bench.json` launching an isolated `1280×720` windowed Chromium/Chrome/Edge instance with vsync disabled (`--disable-frame-rate-limit --disable-gpu-vsync`).
  - Standardized scene (`GameSim.create_benchmark(seed=42)`): Night 1 full lighting/shadows, `200` `wander` Shades outside safe zones, `100` Motes, `L1–L3` lit (`fuel = 100`), stationary Mây at `(0,0,0)`, spawns/damage/pickup/decay/dawn disabled, CCW orbit around `(0,0,0)` from `(30,15,0)` at `15s/rev`, `3s` warm-up + measured `--duration`.
  - Exact frame statistics (`avg_fps`, `p1_low_fps`, `frame_ms_p95`, `frames`, `load_ms`, `peak_mem_mb`, `vsync_off`, `renderer`, `os`), validated at `avg_fps = 142.6`, `p1_low_fps = 36.1`, `load_ms = 1862` on Intel HD Graphics 630.
- **10-Night Soak Runner (`src/soak.py`, `src/sim/sysmem.py`):**
  - CLI `python3 -m src.soak --seed 7 --nights 10 --out soak.json` executing `10` consecutive headless Nights (`1→2→3` cycling) with pure-stdlib cross-platform RSS tracking (Windows `ctypes` PSAPI/Toolhelp, Linux `/proc/<pid>/status` + `ps`, macOS `ps`), verified `crashes = 0` and `17.4 → 17.5 MiB`.
- **Persistent Top-10 Leaderboard (`src/sim/leaderboard.py`, `src/play.py`, `web/`):**
  - Stores `{name, score, nights_won, achieved_at, seed}` atomically on disk (`data/leaderboard.json` or `DDL_LEADERBOARD_PATH`), validates `3–12` chars (`[A-Za-z0-9_]` + Vietnamese accented letters), sorts by `(-score, earlier achieved_at)`, serves `GET`/`POST /api/leaderboard` with strict JSON type checks, displays Top-10 table from Main Menu, and supports `python3 -m src.play --export-leaderboard out.json`.
- **Accessibility & UX (`web/index.html`, `web/style.css`, `web/main.js`):**
  - Full 9-action key rebinding (`moveUp/Down/Left/Right`, `jump`, `dash`, `interact`, `pulse`, `pause`) with conflict detection, `"Khôi phục mặc định"`, and `localStorage` persistence.
  - Visual captions (`#hud-captions`) & screen-edge directional arrow (`#shade-spawn-arrow`) for Shade spawns, wind warnings, final `10s`, and low fuel (`< 30`).
  - Reduced Motion toggle (`#opt-reduced-motion`) disabling camera shake, screen flashes, and CSS animations/transitions.
  - `18px` base HUD/modal typography at `1280×720` with **"Chữ lớn (×1.25)"** toggle scaling cleanly to `22.5px`.
- **Release Packaging, Docs & CI:** Added `Dockerfile`, `run.sh` (`100755`), `run.bat`, `scripts/build_release.py`, `scripts/run_phase4_verification.py`, `CREDITS.md`, `docs/notes/retro.md`, `tests/test_phase4_release.py` (`41` total tests), and GitHub Release `v1.0.0`.

---

## [0.3.0] — Phase 3: TICKET-03 "Đèn cạn dầu" (Contract v1.2)

### Breaking Changes (`[THAY THẾ]` Rules & Schema)

1. **Victory & Loss Conditions (`all_lit` removed)**
   - **Removed:** Immediate win when all lanterns become lit (`game_over.reason = "all_lit"` is no longer emitted).
   - **Replaced by:** Survive until dawn (`time_left == 0.0`) with lit lanterns `>= ceil(0.6 * total_lanterns)` (`3/5` Night 1, `4/6` Night 2, `5/7` Night 3) -> `game_over.reason = "dawn_survived"`; otherwise `game_over.reason = "dawn"`.
   - **Precedence:** `no_flames` (`flames <= 0`) triggers immediately and takes precedence over `dawn_survived` / `dawn` even on the final dawn tick.

2. **Night Durations & Contract Tuning**
   - `contract_version` bumped from `"1.1"` to `"1.2"`.
   - `night1_duration_s`: `300.0 -> 240.0` (`14,400` ticks); `night2_duration_s`: `330.0 -> 270.0` (`16,200` ticks); `night3_duration_s`: `360.0 -> 300.0` (`18,000` ticks).
   - Added required `tuning` keys: `fuel_max`, `fuel_decay_per_s`, `fuel_per_mote`, `relight_cost`, `win_ratio`, `drain_per_s`, `low_fuel_threshold`, `capacity_max`.

3. **Lantern Fuel, Extinguish & Relight**
   - Stored in integer `1/60` fuel units (`fuel_60`); decays `1/60`/tick; refuel `used = min(carried, ceil((100 - fuel)/10))`; extinguishes with `lantern_out` (`ever_lit = True`, `relight_cost = 5`); safe zone drops when `fuel < 30`.

4. **Shade `drain` State, Scoring & Schema**
   - Added `"drain"` state (`5/s` stacked fuel drain), replaced scoring (`+5/mote`, `+100` first light, `+40` relight, `+5/+15` pulse, Dawn Win bonuses), progressive carry capacity `min(20, 10 + 2 * successful_lights)`, colorblind mode, paper-tear unlit visuals, and [ADR-001](docs/notes/ADR-001-lantern-fuel-and-dawn-win.md).

---

## [0.2.0] — Phase 2: TICKET-02 "Ba hòn đảo" (Contract v1.1)
- Standardized physics constants (`6.0 m/s`, jump `7.0 m/s`, gravity `-20 m/s^2`, dash `14 m/s`), canonical maps for Nights 1–3 (`src/sim/maps.py`), Gió Lạc (Drifters), Vật phẩm Bùa (Charms), Ramps/Bridges/Launch Pads, pause freeze, PointerLock + smooth camera damping, and offline 3D Three.js client.

## [0.1.0] — Phase 1: PRD-0 "Đảo Đèn Lồng" (Contract v1.0)
- Initial Night 1 (Đảo Bến) headless simulation, WebSocket play server, and Three.js 3D scene.
