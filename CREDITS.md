# Credits & Assets

## Third-Party Libraries
- **Three.js (r170)** — 3D WebGL rendering engine vendored locally at `web/vendor/three.module.min.js`.
  - License: MIT License (`https://github.com/mrdoob/three.js/blob/dev/LICENSE`).
  - Source: `https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.min.js`.

## Original Code, 3D Assets & Audio
- **Author:** Nguyễn Quang Hiệp (`2A202603509` · `hiepquangnguyen`), VinUni K5-L3-LAB Day 12 AI SDLC.
- **Simulation & Tooling (`src/`):** Pure Python 3 stdlib 60Hz deterministic simulation, CLI headless runner, automated 3D benchmark runner, multi-night soak harness, cross-platform RSS telemetry, and Top-10 leaderboard persistence.
- **3D Models & Environment (`web/main.js`, `web/bench.js`):** Procedural Three.js geometry built specifically for *Đảo Đèn Lồng* (Mây with conical hat `nón lá` & miniature hanging lantern, Đảo Bến / Đảo Cau / Đảo Chuông islands, ramps, bamboo bridges, wind launch pads, bell tower, Grand Lanterns with fuel bars & paper-tear silhouettes, orbiting firefly halo, Bóng Mực shades, Gió Lạc drifters, cloud sea).
- **Audio (`web/main.js`):** Original procedural Web Audio API sound synthesis (night drone ambience, pentatonic mote pickup chimes, lantern ignition & relight chords, fuel-out warning, pulse wave, dash whoosh, hit thud, countdown ticks, victory/defeat cues). No copyrighted external audio files were used.

## AI Tools Used
- **Antigravity IDE + Claude / Gemini coding & review agents:** Assisted across Phases 1–4 with Test Contract `v1.0 → v1.3` analysis, pure-stdlib architecture design, adversarial regression tests, Three.js scene optimization (`InstancedMesh`, binary `Float32Array` WebSocket frames, `MeshLambertMaterial`), accessibility implementation, independent read-only audits, and automated verification scripting. All requirements, physics numbers, and benchmark/soak proofs were verified directly against `game.contract.json` and real execution outputs.
