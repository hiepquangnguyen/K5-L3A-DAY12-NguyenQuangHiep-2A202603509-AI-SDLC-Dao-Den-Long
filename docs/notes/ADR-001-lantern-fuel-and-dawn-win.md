# ADR-001: Lantern Fuel State Machine & Dawn Survival Win Rule (Contract v1.2)

- **Status:** Accepted
- **Date:** 2026-11-20
- **Ticket:** TICKET-03 — Change Request "Đèn cạn dầu" (Phase 3)
- **Supersedes:** Contract v1.1 monotonic lantern lighting (`all_lit` early victory, permanent `safe_radius`)

---

## 1. Context

Playtests on Contract v1.1 showed that skilled players could light all lanterns within ~2 minutes, immediately ending the Night via `all_lit`. This collapsed late-night tension and removed meaningful trade-offs once safe zones stabilized the island.

TICKET-03 transforms Đảo Đèn Lồng from a **one-shot lighting race** into an **endurance & resource-triage loop** until dawn:
- Lit lanterns burn fuel continuously, lose their safe zone below a critical threshold (`fuel < 30`), attract Shades to siphon remaining fuel (`drain` state), and can extinguish (`lantern_out`).
- Victory shifts from "all lanterns lit" (`all_lit`) to "survive until dawn with at least `ceil(0.6 * total_lanterns)` lit" (`dawn_survived`).

---

## 2. Design Decisions

### Decision A — Exact Integer Fixed-Point Fuel (`fuel_60`) & Cyclic Lantern State Model

In Contract v1.1, a lantern had only `{lit: bool, deposited: int}` (monotonic `0 -> 10 -> lit = True`).

In Contract v1.2, each lantern uses an extended cyclic model:
- `ever_lit: bool` — tracks whether the lantern was previously lit during the current Night.
  - First light (`ever_lit == False`): requires `10` motes (`lantern_cost`).
  - Relight after extinguishing (`ever_lit == True`, `lit == False`): requires `5` motes (`relight_cost`).
- `fuel_60: int` — integer fuel measured in `1/60` units (`FUEL_SCALE = 60`, range `0..6000` for `fuel_max = 100`).
  - **Why integer `1/60`?** Subtracting `1/60` decay and `5/60` drain in IEEE-754 float across `18,000` ticks introduces drift (`29.9999999999` vs `30.0`), causing cross-platform threshold bugs at `fuel == 30` or `fuel == 0`. Storing integer `fuel_60` guarantees bit-identical cross-platform determinism (`round(float(fuel) * 60)`).
  - Snapshot formatting emits `round(fuel_60 / 60.0, 1)` when `lit` is `True`, and `0.0` when `lit` is `False`.
- `relit_count: int` — number of relights performed after `lantern_out`.

**State Transitions:**
1. **Unlit (`lit = False`):** Accepts deposits up to `required_cost = 5 if ever_lit else 10`. Reaching `required_cost` sets `lit = True`, `ever_lit = True`, `fuel_60 = 6000`, increments `successful_lights` (boosting carry capacity `min(20, 10 + 2 * successful_lights)`), emits `lantern_lit {lantern_id, relight}`, and pushes Shades within `6.0m` out over `<= 30` ticks.
2. **Lit & Protected (`lit = True`, `fuel_60 >= 1800`):** Passive decay `-1` `fuel_60`/tick. Safe zone active (`safe_radius = 6.0m`). Eligible for refuel (`used = min(carried, ceil((6000 - fuel_60) / 600))`).
3. **Lit & Vulnerable (`lit = True`, `0 < fuel_60 < 1800`):** Loses safe zone (`fuel_60 == 1800` still keeps protection). Eligible targets for `wander` Shades (`drain` steals `-5` `fuel_60`/tick per draining Shade on top of `-1` passive decay). Refueling back across `< 1800 -> >= 1800` restores the safe zone and pushes Shades inside `6.0m` out over `<= 30` ticks with zero damage.
4. **Extinguished (`fuel_60 <= 0` in Step 2):** Transitions to `lit = False`, `deposited = 0`, `fuel_60 = 0`, preserves `ever_lit = True`, emits `lantern_out {lantern_id}`, and updates ambient lighting + capacity eligibility.

### Decision B — Shade `drain` State & Strict Tick Order

`VALID_SHADE_STATES` expands from `{spawning, wander, chase, recoil, stunned}` to include `drain`:
- Only `wander` Shades target weak lanterns (`lit and fuel < 30`, nearest by XZ, tie-break smaller numeric `id`), falling back to nearest unlit lantern when no weak lantern exists. Shades in `chase` never divert to weak lanterns.
- Entering `<= 2.0m` XZ of the target weak lantern enters `drain` (stationary, drains `5` fuel/s = `5/60`/tick; stacks across multiple draining Shades; emits `fuel_drain {lantern_id, shade_id, fuel}` every `60` ticks).
- Exit conditions from `drain`: `chase` if Mây enters `<= 6.0m`; `stunned` if hit by Pulse (`+15` total score instead of `+5`); `wander` if lantern extinguishes, is refueled to `>= 30`, or moves `> 2.0m` away.
- Pulse recovery (`stunned` expires) now transitions unconditionally to `wander`, allowing tactical interruption of a Shade without locking it permanently onto Mây.

**Per-Tick Causality Order:**
- Step 2 decrements timers AND applies fuel decay + active `drain` deductions, immediately firing `lantern_out` if `fuel_60 <= 0`. Because Step 2 runs before Mây movement, deposit/refuel, safe zones, and Step 8 AI, Shades never drain an already-dead lantern on the same tick, and UI/safe-zones see the exact state.
- Step 11 (`_evaluate_outcome`) runs at the end of every tick (after all damage, spawns, relights, and fuel updates) with strict priority:
  1. `player.flames <= 0` -> `loss` (`no_flames`), even on the exact dawn tick.
  2. `time_left <= 0` -> `win` (`dawn_survived`) if `lit_count >= ceil(0.6 * total_lanterns)` else `loss` (`dawn`).
- Early `all_lit` win is completely removed.

### Decision C — Progressive Carry Capacity & New Economy

- Carrying more motes rewards active lantern defense: `capacity = min(20, 10 + 2 * successful_lights)` resets per Night and excludes pre-lit scenario lanterns.
- Time bonus (`per_second_left`) is removed because every victorious Night runs the full `240 / 270 / 300 s` duration; endgame optimization shifts to keeping flames alive (`+50`/flame) and maximizing lit lantern count & residual fuel (`+50 + floor(fuel)` per lit lantern).

---

## 3. Consequences

- **Breaking changes:** Documented in [`CHANGELOG.md`](../../CHANGELOG.md); all v1.1 contracts, tests asserting `all_lit` early victory, `300/330/360s` durations, old `per_mote = 10` / `per_second_left = 2` scoring, or infinite lantern safe zones are intentionally updated for Contract v1.2.
- **Performance:** Keeping fuel integer (`fuel_60`) keeps per-tick overhead negligible; Night 3 `18,000`-tick headless dawn runs and `21,600`-tick stress runs complete well within the `<= 30s` budget.
- **Client Separation:** All fuel bars, `1 Hz` blinking `< 30`, deflated/torn unlit silhouettes, and saved Colorblind Mode (`#00B3FF` / `#FFFFFF` + `⚠`) live strictly in `web/`, preserving headless determinism.
