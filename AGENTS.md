# AGENTS.md — Đảo Đèn Lồng

## Architecture
- **Single source of truth:** `src/sim/` (pure Python stdlib, 60Hz fixed tick) powers both headless tests (`src/headless.py`) and the 3D web server (`src/play.py`).
- **3D Client:** `web/` uses vendored `web/vendor/three.module.min.js` (Three.js r170, MIT) over a local WebSocket (`/ws`) on the same port as HTTP.
- **No pip/npm dependencies:** Keep `src/` pure Python 3 stdlib so it runs offline on macOS, Linux, and Windows.

## Commands
- Build/check: `python3 -m compileall -q src` (Windows: `python`)
- Run 3D game: `python3 -m src.play`
- Run unit + contract tests: `python3 -m unittest discover -s tests -v`
- Run verification gate: `python3 .agents/hooks/verify_gate.py`
- Run headless: `python3 -m src.headless --seed 1 --night 1 --ticks 600 --out out.jsonl`

## Test Contract v1.0 Invariants (DO NOT BREAK)
1. **60Hz fixed step (`DT = 1/60`):** Snapshot `tick=0` before step `0`; step `k` emits events with `tick=k+1`; `time_left_s = initial - sim_tick / 60`.
2. **XZ distance `<= r`:** All tuning radii check 2D XZ distance only, ignoring `player.y`.
3. **Rising-edge actions:** `jump`, `interact`, `pulse` activate only on `false -> true`.
4. **Input rotation:** `x' = x*cos(θ) + z*sin(θ)`, `z' = -x*sin(θ) + z*cos(θ)`, normalize `|move| > 1`.
5. **Strict validation:** Malformed `--inputs` or `--scenario` must exit with code `2` and print to `stderr`.
6. **Determinism:** Use `SeededRNG` (`src/sim/prng.py`) exclusively; never use global `random`.
7. **Creative features:** Visual/audio additions belong strictly in `web/` and must never alter `src/sim/` or headless JSONL output.
8. **Verification gate:** Never mark work done or commit without passing `.agents/hooks/verify_gate.py`.
