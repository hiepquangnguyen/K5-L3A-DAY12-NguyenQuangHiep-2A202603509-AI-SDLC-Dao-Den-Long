---
name: verify-phase
description: Run automated unit tests, Test Contract v1.2 headless scenarios across Nights 1-3, determinism & performance checks, and regenerate real proof artifacts.
---

# Verify Phase Skill (Phase 3 — Contract v1.2)

Use this workflow at the end of every milestone and before tagging any phase.

## Steps
1. Run syntax/bytecode compilation:
   - macOS/Linux: `python3 -m compileall -q src`
   - Windows: `python -m compileall -q src`
2. Run the full verification gate (v1.2 contract check, unit + contract tests, Night 1 & Night 3 determinism, Night 3 dawn perf `<= 30s`):
   - `python3 .agents/hooks/verify_gate.py` (or `python .agents/hooks/verify_gate.py`)
3. Regenerate Phase 3 proof artifacts without hand-editing any output:
   - `python3 scripts/run_phase3_verification.py` (or `python scripts/run_phase3_verification.py`)
4. Visually inspect the 3D game at `1280x720`:
   - Start `python3 -m src.play --no-open --port 8765`, open `http://127.0.0.1:8765` at `1280x720`, verify Main Menu, `04:00` Night 1 timer, `3/5` dawn threshold, lantern fuel bars & `1 Hz` blink `< 30`, deflated/torn unlit silhouettes, Colorblind mode toggle + persistence, `#hud-fps >= 30`, zero console/WebSocket errors, and save screenshots into `docs/proof/phase-3/`.
5. Inspect `git status` and `git diff` to ensure no secrets, temporary files, or unverified claims exist before committing.
