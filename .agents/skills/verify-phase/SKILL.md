---
name: verify-phase
description: Run automated unit tests, Test Contract v1.1 headless scenarios across Nights 1-3, determinism & performance checks, and regenerate real proof artifacts.
---

# Verify Phase Skill (Phase 2 — Contract v1.1)

Use this workflow at the end of every milestone and before tagging any phase.

## Steps
1. Run syntax/bytecode compilation:
   - macOS/Linux: `python3 -m compileall -q src`
   - Windows: `python -m compileall -q src`
2. Run the full verification gate (v1.1 contract check, unit + contract tests, Night 1 & Night 3 determinism, 21,600-tick Night 3 perf `<= 30s`):
   - `python3 .agents/hooks/verify_gate.py` (or `python .agents/hooks/verify_gate.py`)
3. Regenerate Phase 2 proof artifacts without hand-editing any output:
   - `python3 scripts/run_phase2_verification.py` (or `python scripts/run_phase2_verification.py`)
4. Visually inspect the 3D game at `1280x720`:
   - Start `python3 -m src.play --no-open --port 8765`, open `http://127.0.0.1:8765` at `1280x720`, verify Main Menu, Night 1–3 worlds, Pause menu, Settings persistence, `window.__gamePerf.avgFps >= 30`, zero console/WebSocket errors, and save screenshots into `docs/proof/phase-2/`.
5. Inspect `git status` and `git diff` to ensure no secrets, temporary files, or unverified claims exist before committing.
