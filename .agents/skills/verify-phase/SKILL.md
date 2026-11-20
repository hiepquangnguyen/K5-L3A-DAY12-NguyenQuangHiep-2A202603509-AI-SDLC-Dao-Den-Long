---
name: verify-phase
description: Run automated unit tests, Test Contract v1.3 headless scenarios, bench & soak benchmarks, determinism & accessibility checks, and regenerate real proof artifacts.
---

# Verify Phase Skill (Phase 4 — Contract v1.3)

Use this workflow at the end of every milestone and before tagging any phase/release.

## Steps
1. Run syntax/bytecode compilation:
   - macOS/Linux: `python3 -m compileall -q src`
   - Windows: `python -m compileall -q src`
2. Run the full verification gate (v1.3 contract check, unit + contract tests, Night 1 & Night 3 determinism, Night 3 perf `<= 30s`):
   - `python3 .agents/hooks/verify_gate.py` (or `python .agents/hooks/verify_gate.py`)
3. Run Benchmark (`1280x720`, 200 Shades, 100 Motes) and 10-Night Soak test:
   - `python3 -m src.soak --seed 7 --nights 10 --out soak.json`
   - `python3 -m src.bench --seed 42 --duration 30 --out bench.json`
4. Regenerate Phase 4 proof artifacts without hand-editing any output:
   - `python3 scripts/run_phase4_verification.py` (or `--check-only` in CI)
5. Visually inspect the 3D game at `1280x720`:
   - Start `python3 -m src.play --no-open --port 8765`, open `http://127.0.0.1:8765` at `1280x720`, verify Leaderboard UI, `--export-leaderboard`, Key Rebinding + conflict detection + reset, Large Text (`>= 18px` base / `>= 22.5px` large), Reduced Motion, Visual Captions & Shade spawn arrow, and save screenshots into `docs/proof/phase-4/`.
6. Inspect `git status` and `git diff` to ensure no secrets, temporary files, or unverified claims exist before tagging.
