---
name: verify-phase
description: Run automated unit tests, Test Contract v1.0 headless scenarios, determinism checks, and regenerate real proof artifacts for the current phase.
---

# Verify Phase Skill

Use this workflow at the end of every implementation milestone and before tagging any phase.

## Steps
1. Run syntax/bytecode compilation:
   - macOS/Linux: `python3 -m compileall -q src`
   - Windows: `python -m compileall -q src`
2. Run the full verification gate (unit tests, contract alignment, determinism):
   - `python3 .agents/hooks/verify_gate.py` (or `python .agents/hooks/verify_gate.py`)
3. Regenerate phase proof artifacts without hand-editing any output:
   - `python3 scripts/run_phase1_verification.py` (or `python scripts/run_phase1_verification.py`)
4. Visually inspect the 3D game if UI/rendering changed:
   - Start `python3 -m src.play --no-open --port 8765`, open `http://127.0.0.1:8765` in browser, verify zero console/WebSocket errors and live HUD updates, capture screenshot into `docs/proof/phase-1/`.
5. Inspect `git status` and `git diff` to ensure no secrets, temporary files, or unverified claims exist before committing.
