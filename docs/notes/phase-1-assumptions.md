# Phase 1: PRD-0 Analysis, Assumptions & Verification Plan

## 1. PRD-0 & Test Contract v1.0 Breakdown

### Mandatory Exact Requirements (Test Contract v1.0)
- `game.contract.json` at repo root with exact schema (`contract_version: "1.0"`, `team`, `build_cmd`, `run_cmd`, `headless_cmd`, `tuning.*`).
- Headless CLI: `--seed <int> --night 1 [--scenario <file>] [--inputs <file>] --ticks <int> --out <file.jsonl> [--snapshot-every <int>]`.
- Fixed 60 ticks/sec (`DT = 1/60s`), zero-window, fast execution, exit code `0` on completion/game-over, exit code `2` + stderr on malformed `--inputs` or `--scenario`, non-zero + stderr on other errors.
- Tick model: tick `0` snapshot is post-scenario pre-input; step `k` (`0..N-1`) applies tick `k` input, outputs tick `k+1`, emits events at `tick = k+1`. `time_left_s = initial - sim_tick / 60`.
- Coordinate & measurement rules: meters, +Y up, ground at `Y = 0`, default player spawn `(0, 0, 0)`, XZ-plane distance `<= r` (ignores height Y).
- Input state persistence, strict strictly-increasing frame ticks, world rotation formula, vector normalization (`|move| > 1`), rising-edge activation (`false -> true`).
- Scenario overrides without emitting events or awarding score during setup.
- JSONL output format (`snapshot`, `event`, `end`), 3-decimal coordinate rounding, strict byte-for-byte determinism for same `--seed`, `--scenario`, `--inputs`.

### Game Requirements (PRD-0)
- Third-person 3D game **Đảo Đèn Lồng** — Night 1: **Đảo Bến** (circular island, 5 Big Lanterns `L1`..`L5`).
- Player character **Mây** wearing a conical hat (`nón lá`) with a hanging miniature lantern; moves, jumps, 3D third-person camera.
- Fireflies (đom đóm) scattered on island; collectible up to `carry_capacity`.
- Deposit light into Big Lanterns (`interact`); lit lanterns gradually brighten the island.
- Ink Shades (Bóng Mực) spawn and chase player; touch deals flame damage + invulnerability window + drops carried fireflies; shades cannot enter `safe_radius` around lit lanterns.
- Pulse (`pulse`) spends carried light to push & stun nearby shades.
- Win (`all_lit`), Loss (`no_flames`, `dawn`), HUD, Scoring, Restartable after win/loss.
- Cozy fairy-tale dark aesthetic: warm gold/orange = good/light, dark purple/ink = danger, non-violent.

---

## 2. Explicit Assumptions for Ambiguities in PRD-0

| Ambiguous Area | Chosen Assumption & Tuning Value | Rationale |
|---|---|---|
| Island size & edge fall | Circular island default radius `45.0m`, `fall_enabled: false` (clamp XZ to boundary). If a test scenario places entities outside `45.0m`, `effective_island_radius = max(45.0, max_entity_r + 15.0)` so tests remain reachable. | Keeps gameplay smooth without unfair accidental falls while respecting arbitrary scenario test coordinates. |
| Lantern layout (`L1`..`L5`) | Regular pentagon at radius `25.0m`, starting at `L1 = [0, 0, 25]` (matching Contract Section D example): `L1(0,0,25)`, `L2(23.776,0,7.725)`, `L3(14.695,0,-20.225)`, `L4(-14.695,0,-20.225)`, `L5(-23.776,0,7.725)`. | Matches Contract example `L1` and distributes lanterns evenly around Đảo Bến. |
| Player physics | `player_speed = 8.0 m/s`, `JUMP_SPEED = 7.5 m/s`, `GRAVITY = 20.0 m/s^2`, `carry_capacity = 10`. | Snappy traversal across a 45m radius island within 300s (`night1_duration_s`). |
| Deposit mechanic | Pressing `interact` (rising edge) within `interact_radius = 3.0m` of the nearest unlit lantern deposits `min(carried, lantern_cost - deposited)` in one action (`lantern_cost = 5`). | Fast, responsive interaction; allows single-trip or partial multi-trip lighting. |
| Safe radius scope | `safe_radius = 5.0m` blocks shades around **lit** lanterns only (`lit == True`). Unlit lanterns do not repel shades. | Aligns with lore ("Bóng Mực sợ những chiếc đèn") and gives each lit lantern meaningful tactical reward. |
| Hit drop & invuln | `flames = 3`, `invuln_s = 1.5s`, `hit_drop_ratio = 0.5`. On hit, `dropped = floor(carried * 0.5)` dissipates into mist (`carried -= dropped`). | Prevents instant stun-lock death and avoids cluttered dropped-item re-pickup ambiguity. |
| Pulse behavior | `pulse_cost = 2`, `pulse_radius = 8.0m`, `pulse_stun_s = 3.0s`, `pulse_push_m = 6.0m`, `pulse_cooldown_s = 4.0s`. Triggers whenever `carried >= pulse_cost` and cooldown is 0, even if `0` shades are in range (emits `pulse` with `stunned_ids: []`). | Predictable resource spending and clean `pulse` event testing even when testing miss/empty radius. |
| Random spawn rules | When `random_motes = true`: start with 20 motes on `r in [5, 40]` outside player `pickup_radius`; replenish 1 every 180 ticks (3s) if active < 20. When `random_shades = true`: start with 2 shades on `r in [24, 38]` outside lit `safe_radius`; spawn 1 every 1200 ticks (20s) up to cap 6, >= 18m from player. | Ensures active gameplay without overwhelming player or spamming events. |
| Scoring formula | `per_mote = 10`, `per_lantern = 200`, `per_stun = 50`, `per_second_left = 2`, `per_flame_left = 100`. Time & flame bonuses awarded once when winning (`all_lit`). | Directly maps to every field in `game.contract.json`'s `score` object. |

---

## 3. Acceptance Criteria & Verification Plan (Written Pre-Implementation)

1. **Movement & Camera Rotation:** Given `cam_yaw_deg = 90`, `move = [0, 1]`, stepping `N` ticks moves player along `+X` by `player_speed * N / 60`. Verified via unit test.
2. **Input Rising Edge & Persistence:** Holding `interact: true` across 10 ticks executes only 1 deposit; omitting `move` keeps prior velocity. Verified via unit test & JSONL inspection.
3. **Pickup & Deposit Win Loop:** Walking over 5 motes then interacting near `L1` emits 5 `mote_picked`, 1 `deposit`, 1 `lantern_lit`, and `game_over` (`won`/`all_lit`) with exact end score. Verified via headless scenario `pickup_and_deposit_win`.
4. **Pulse & Safe Radius:** Pulsing within `8.0m` pushes shade by `6.0m`, sets `state="stunned"` for `3.0s`, emits `pulse`; active shades cannot cross `< 5.0m` of a lit lantern. Verified via unit test & headless scenario `pulse_and_safe_radius`.
5. **Shade Hit & Loss (`no_flames` / `dawn`):** Shade touch within `1.2m` decrements `flames`, drops `floor(carried * 0.5)`, triggers `1.5s` invulnerability, and loses on `flames == 0` or `time_left_s == 0`. Verified via headless scenarios `shade_hit_and_loss` and `dawn_timeout`.
6. **Format Validation & Determinism:** Bad inputs/scenario files return exit code `2` + stderr; two runs with `--seed 12345` produce identical SHA-256 JSONL outputs. Verified via `test_headless_contract.py` & `verify_gate.py`.
7. **3D Visual Gameplay & Creativity:** Browser opens local game at `127.0.0.1:8765`, WebGL renders Đảo Bến, Mây in `nón lá` with hanging lantern, 5 Big Lanterns brightening island, HUD, restart button, plus Orbiting Firefly Halo & Web Audio synth (isolated to `web/`). Verified by live browser launch & screenshot capture.
