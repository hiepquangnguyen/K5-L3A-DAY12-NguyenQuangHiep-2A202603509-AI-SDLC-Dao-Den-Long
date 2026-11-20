# AGENTS.md — Đảo Đèn Lồng (Contract v1.3)

## Architecture
- **Single source of truth:** `src/sim/` (pure Python stdlib, 60Hz fixed tick) powers headless tests (`src/headless.py`), 3D web server (`src/play.py`), benchmark (`src/bench.py`), and soak test (`src/soak.py`).
- **Standard Maps & Persistence:** `src/sim/maps.py` defines canonical Nights 1–3; `src/sim/leaderboard.py` & `src/sim/sysmem.py` provide pure-stdlib Top-10 persistence and cross-platform RSS reading.
- **3D Client:** `web/` uses vendored `web/vendor/three.module.min.js` (Three.js r170, MIT) over local WebSocket (`/ws`).
- **No pip/npm dependencies:** Keep `src/` pure Python 3 stdlib so it runs offline on macOS, Linux, and Windows.

## Commands
- Build/check: `python3 -m compileall -q src` (Windows: `python`)
- Run 3D game: `python3 -m src.play` (`--export-leaderboard out.json`)
- Run unit + contract tests: `python3 -m unittest discover -s tests -v`
- Run verification gate: `python3 .agents/hooks/verify_gate.py`
- Run headless / bench / soak: `python3 -m src.headless --seed 1 --night 3 --ticks 18000 --out out.jsonl`, `python3 -m src.bench --seed 42 --duration 30 --out bench.json`, `python3 -m src.soak --seed 7 --nights 10 --out soak.json`

## Test Contract v1.3 Invariants (DO NOT BREAK)
1. **60Hz fixed step (`DT = 1/60`) & 12-step tick order:**
   1) Input & pause edge -> 2) Decrement timers + deduct lantern fuel (`1/60` decay + `5/60` per `drain` Shade, extinguishing `fuel <= 0` immediately with `lantern_out`) -> 3) Move Mây + fall check (`Y < -10`) -> 4) Pickup motes & charms -> 5) Lantern interact (light `10`, relight `5`, or refuel `used = min(carried, ceil((100 - fuel)/10))`) -> 6) Safe zones (`fuel >= 30`, including pushing nearby Shades when relit or refueled to `>= 30`) -> 7) Pulse (3D `<= 5m` from `py+0.8`) -> 8) Move Shades (`wander` -> weak `< 30` lit lantern else nearest unlit) & Drifters -> 9) Collisions (Drifter steal first, then Shade hit by ascending `id`) -> 10) Scheduled spawns -> 11) Win/Loss (`no_flames` > `dawn_survived` > `dawn`; no early `all_lit` win) -> 12) Snapshot.
2. **Pause behavior:** While paused, `tick` advances and `snapshot.state = "paused"`, while `sim_tick`, timers, fuel decay/drain, spawns, and TTL freeze.
3. **Exact Shade states:** Must use `spawning | wander | chase | drain | recoil | stunned`. Drifter states: `idle | chase | flee | removed`.
4. **Rising-edge actions & rebinding:** `jump`, `interact`, `pulse`, `dash`, `pause` activate only on `false -> true`; UI rebinding must reject conflicts and persist cleanly.
5. **Input rotation:** `x' = x*cos(θ) + z*sin(θ)`, `z' = -x*sin(θ) + z*cos(θ)`, normalize `|move| > 1`.
6. **Strict validation:** Malformed `--inputs` or `--scenario` must exit with code `2` and print to `stderr`.
7. **Determinism & Performance:** Use `SeededRNG` (`src/sim/prng.py`) exclusively; store fuel in integer `1/60` units (`fuel_60`); Night 3 headless `<= 30s`; bench (`200` wander Shades, `100` motes, `1280x720`) `avg_fps >= 60`, `p1_low_fps >= 30`, `load_ms <= 10000`; soak `10` nights `crashes == 0`, `mem_end <= 1.2 * mem_start`.
8. **Creative features:** Visual/audio additions belong strictly in `web/` (and stay disabled in bench/soak), never altering `src/sim/` headless JSONL output.
9. **Verification gate:** Never mark work done or commit without passing `.agents/hooks/verify_gate.py`.
