# Changelog

All notable changes and Contract migrations for **Đảo Đèn Lồng** are documented here.

---

## [1.2.0] — Phase 3: TICKET-03 "Đèn cạn dầu" (Contract v1.2)

### Breaking Changes (`[THAY THẾ]` Rules & Schema)

1. **Victory & Loss Conditions (`all_lit` removed)**
   - **Removed:** Immediate win when all lanterns become lit (`game_over.reason = "all_lit"` is no longer emitted).
   - **Replaced by:** Survive until dawn (`time_left == 0.0`) with lit lanterns `>= ceil(0.6 * total_lanterns)` (`3/5` Night 1, `4/6` Night 2, `5/7` Night 3) -> `game_over.reason = "dawn_survived"`; otherwise `game_over.reason = "dawn"`.
   - **Precedence:** `no_flames` (`flames <= 0`) triggers immediately and takes precedence over `dawn_survived` / `dawn` even on the final dawn tick.

2. **Night Durations & Contract Tuning**
   - `contract_version` bumped from `"1.1"` to `"1.2"`.
   - `night1_duration_s`: `300.0 -> 240.0` (`14,400` ticks).
   - `night2_duration_s`: `330.0 -> 270.0` (`16,200` ticks).
   - `night3_duration_s`: `360.0 -> 300.0` (`18,000` ticks).
   - Added required `tuning` keys: `fuel_max: 100`, `fuel_decay_per_s: 1.0`, `fuel_per_mote: 10`, `relight_cost: 5`, `win_ratio: 0.6`, `drain_per_s: 5`, `low_fuel_threshold: 30`, `capacity_max: 20`.

3. **Lantern Fuel, Extinguish & Relight (`lit` is no longer permanent)**
   - **Replaced:** Lit lanterns previously never lost charge and never accepted additional motes.
   - **Now:** Lit lanterns start at `fuel = 100.0` (`6000` internal integer `1/60` units), decay `1.0/s` (`1/60` per tick), accept refueling via `interact` (`used = min(carried, ceil((100 - fuel) / 10))`, skipped cleanly if `used == 0`), extinguish at `fuel <= 0` (`lit = False`, `deposited = 0`, `ever_lit = True`, emits `lantern_out`), and relight for `5` motes (`relight_cost`) instead of `10`.
   - **Safe Zone threshold:** Lanterns with `fuel < 30` lose their `6.0m` safe zone (exact `30.0` retains protection). Refueling across `< 30 -> >= 30` pushes Shades inside `6.0m` out over `<= 30` ticks without damage.

4. **Shade `drain` State & AI Transitions**
   - Added Shade state `"drain"` (`VALID_SHADE_STATES = {"spawning", "wander", "chase", "drain", "recoil", "stunned"}`).
   - Only `wander` Shades seek the nearest lit lantern with `fuel < 30` (tie-break smaller numeric `id`), falling back to nearest unlit lantern. `chase` Shades do not divert.
   - Within `<= 2.0m` XZ of a weak lantern, `wander` Shades enter `drain`, halt, and drain `5/s` (`5/60`/tick, stacking per draining Shade; emits `fuel_drain` every `60` ticks).
   - Transitions out of `drain`: Mây `<= 6.0m` -> `chase`; Pulse -> `stunned`; lantern out / `fuel >= 30` / distance `> 2.0m` -> `wander`.
   - When `stunned` expires, Shades now return to `wander` (instead of `chase`).

5. **Scoring Formula Replaced**
   - `per_mote`: `10 -> 5` (applies to light, relight, and refuel deposits).
   - First light: `+100` (`per_lantern`); relight: `+40` (`per_relight`).
   - Pulse stun: `+5` (`per_stun`), or `+15` total (`per_stun_draining`) if the Shade was in `drain` immediately before being pulsed.
   - **Removed:** `per_second_left` time bonus.
   - **Dawn Win Bonus (win only):** `+50 + floor(fuel)` per currently lit lantern + `+50` per remaining flame.

6. **Headless JSONL Schema Extensions**
   - Snapshot `lanterns[]`: added `fuel` (1 decimal float, `0.0` when unlit), `ever_lit`, `relit_count`.
   - Snapshot `player`: added `capacity`.
   - Events: added `refuel {lantern_id, amount, fuel}`, `lantern_out {lantern_id}`, `fuel_drain {lantern_id, shade_id, fuel}`; `lantern_lit` added `relight: bool`.
   - Scenario JSON validation: accepts `lanterns[].lit`, `lanterns[].fuel` (defaults to `100.0` if `lit: true` and omitted), `lanterns[].ever_lit`; `player.successful_lights`; `shades[].target_lantern_id` and state `"drain"`.

7. **Test Suite Migrations (Rationale for Modified Phase 1–2 Tests)**
   - `tests/test_phase2_features.py`: Updated `test_night3_dawn_18000_and_stress_21600_ticks_under_30s_and_deterministic` for `night3` dawn at `18,000` ticks (`300s`) while retaining a `21,600`-tick `<= 30s` stress test via scenario `time_left_s: 360.0`; updated same-tick outcome precedence assertion (`all_lit` -> `dawn_survived` plus `no_flames > dawn_survived` check). Contract v1.2 tuning/durations and Shade stun-recovery (`stunned -> wander`) assertions are verified in `tests/test_phase3_change_request.py`.
   - `tests/test_headless_contract.py` & `tests/test_sim_unit.py`: Migrated tests that asserted `all_lit` early win, old `+10/mote` score, or old `per_second_left` time bonus to assert v1.2 `lantern_lit.relight == False`, non-termination on lighting all lanterns, and `dawn_survived` / `dawn` / `no_flames` rules. Zero tests were silently skipped or weakened.

### Added (Non-Breaking Features)
- **Progressive Carry Capacity:** `capacity = min(20, 10 + 2 * successful_lights)` per Night (scenario pre-lit lanterns excluded), displayed in HUD & orbiting Halo.
- **3D Fuel UI & Non-Color Distinction:** Overhead camera-facing fuel bar on lit lanterns; `1 Hz` blink + hidden safe ring when `fuel < 30`; deflated (`-20%` height) & paper-tear silhouettes on unlit lanterns.
- **Colorblind Mode (`"Bảng màu dễ phân biệt"`):** Saved toggle in Settings switching Shade outline/eyes (`#7A3CFF -> #00B3FF`) and UI warnings (`#FF5A5F -> #FFFFFF` + `⚠`).
- **Design Documentation:** Added `docs/notes/ADR-001-lantern-fuel-and-dawn-win.md`.

---

## [1.1.0] — Phase 2: TICKET-02 "Ba hòn đảo" (Contract v1.1)
- Standardized physics constants (`6.0 m/s`, jump `7.0 m/s`, gravity `-20 m/s^2`, dash `14 m/s`), canonical maps for Nights 1–3 (`src/sim/maps.py`), Gió Lạc (Drifters), Vật phẩm Bùa (Charms), Ramps/Bridges/Launch Pads, pause freeze, PointerLock + smooth camera damping, and offline 3D Three.js client.

## [1.0.0] — Phase 1: PRD-0 "Đảo Đèn Lồng" (Contract v1.0)
- Initial Night 1 (Đảo Bến) headless simulation, WebSocket play server, and Three.js 3D scene.
