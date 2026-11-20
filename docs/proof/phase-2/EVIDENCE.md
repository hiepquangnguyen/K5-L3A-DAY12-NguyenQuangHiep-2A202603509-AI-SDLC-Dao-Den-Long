# Phase 2 Verification Evidence — Đảo Đèn Lồng ("Ba hòn đảo" · Contract v1.1)

> Tất cả số liệu, JSONL và ảnh chụp dưới đây được sinh trực tiếp từ mã nguồn thực tế (`scripts/run_phase2_verification.py`, `.agents/hooks/verify_gate.py`, và trình duyệt thực tế tại `http://127.0.0.1:8765/` độ phân giải `1280×720`). Không có kết quả sửa tay.

## 1. Bảng truy vết Yêu cầu → Bằng chứng

| Nhóm | Yêu cầu (Ticket-02 / Contract v1.1) | Cách kiểm chứng | Bằng chứng | Kết quả |
|---|---|---|---|---|
| **Contract** | `game.contract.json` v1.1 khớp 100% số liệu chuẩn (`dash_*`, `night2/3_duration_s`, tốc độ, bán kính, điểm) | Gate kiểm tra schema & consistency với `src/sim/` | [game.contract.json](../../../game.contract.json), [verify_gate.py](../../../.agents/hooks/verify_gate.py) | **Đạt** *(Lưu ý: `"team"` vẫn để `"TODO-mssv-ho-ten"` chờ điền MSSV cá nhân)* |
| **Regression** | Toàn bộ test Phase 1 cập nhật theo số liệu chuẩn v1.1 đều xanh | `test_sim_unit.py` & `test_headless_contract.py` (schema v1.1, exit `2` kể cả `>4300` chữ số) | [test_report.txt](test_report.txt) (`28/28 OK`) | **Đạt** |
| **Tick & Pause** | Thứ tự 12 bước/tick; `pause` giữ nguyên `sim_tick`/timer/TTL trong khi `tick` tăng và `state="paused"` | `test_pause_freezes_sim_tick_timers_and_ttl` + thử `Esc` trên trình duyệt | [test_report.txt](test_report.txt), [screenshot_pause.png](screenshot_pause.png) | **Đạt** |
| **Di chuyển/Lướt/Rơi** | Lướt `14 m/s` `0.2s` giữ độ cao Y, hồi `1.5s`; rơi `Y < -10` bỏ qua bất tử, chờ `60` tick, hồi sinh | `test_dash_air_altitude_hold_and_cooldown`, `test_fall_off_island_ignores_invuln_respawns_and_loses_on_last_flame` | [test_report.txt](test_report.txt) | **Đạt** |
| **Đêm 2 (Đảo Cau)** | Hai đảo `28m`, cầu tre `x∈[26,44], z∈[-2,2]`, 2 bục nhảy `(20,0,18)`/`(50,0,-18)`, `L1..L6`, 24 mote, 16 shade | `test_night2_bridge_and_launch_pad`, JSONL mẫu & ảnh chụp `1280×720` | [sample_night2.jsonl](sample_night2.jsonl), [screenshot_night2.png](screenshot_night2.png) | **Đạt** |
| **Đêm 3 (Đảo Chuông)** | Đảo `45m`, 3 tầng (`0/3/6`), 2 dốc `30°`/`150°` chặn đi xuyên vách, bục `(0,3,13)`, Tháp chuông `r=2`, gió `2 m/s` mỗi `30s` | `test_night3_ramp_cliffs_launch_bell_tower_and_wind`, `test_audit_regressions_*`, JSONL & ảnh chụp | [sample_night3.jsonl](sample_night3.jsonl), [screenshot_night3.png](screenshot_night3.png) | **Đạt** |
| **Gió Lạc & Bùa Gió** | Gió Lạc `idle/chase/flee/removed`, cướp `min(3, carried)` bỏ qua `invuln`/`safe_radius`, pulse thả đồ; Bùa Gió `7.2 m/s`, Lướt `0s` hồi, hồi `2700` tick | `test_drifter_steal_ignores_invuln_safe_zone_and_pulse_drops`, `test_charm_boosts_speed_removes_dash_cooldown_and_respawns`, `test_audit_regressions_*` | [test_report.txt](test_report.txt) | **Đạt** |
| **Vùng an toàn & Trạng thái** | Đủ 5 trạng thái Bóng Mực (`spawning|wander|chase|recoil|stunned`); đèn vừa thắp đẩy bóng bên trong ra `<=30` tick không gây sát thương | `test_safe_push_30_ticks_and_obstacle_knockback_stop`, `test_pulse_and_safe_radius_scenario` | [test_report.txt](test_report.txt) | **Đạt** |
| **Tính tất định** | Chạy 2 lần độc lập cùng seed (Đêm 1 `1800` tick & Đêm 3 `21,600` tick) trùng byte-for-byte | `scripts/run_phase2_verification.py` & `verify_gate.py` | [determinism_diff.txt](determinism_diff.txt) (`Exact match: True`, Night 3 sha256 `4631fc9d...`) | **Đạt** |
| **Hiệu năng Headless** | Chạy Đêm 3 đầy đủ `21,600` tick trong `<= 30s` | Đo thời gian thực tế 2 lần chạy | [perf_night3_21600.txt](perf_night3_21600.txt) (`2.370s` & `2.796s <= 30.0s`) | **Đạt** |
| **Client 3D & FPS (`1280×720`)** | Bảng màu chuẩn, ánh sáng `0.15 + 0.55*(lit/total)`, Menu -> Intro Ông Đăng -> 3 Đêm -> Pause -> Settings `localStorage`, mũi tên chỉ đèn, `>= 30 FPS` | Kiểm thử trực tiếp trình duyệt ở `1280×720` (`0` lỗi console/network; đọc trực tiếp `#hud-fps`) | [screenshot_menu.png](screenshot_menu.png), [screenshot_night1.png](screenshot_night1.png), [screenshot_pause.png](screenshot_pause.png), [screenshot_night2.png](screenshot_night2.png), [screenshot_night3.png](screenshot_night3.png) (`#hud-fps`: `FPS: 30 (avg 30.0)` / `FPS: 58 (avg 31.5)`) | **Đạt** |
| **Nộp bài GitHub** | Điền `"team"`, gắn tag `phase-2` trên repo public | Chờ thông tin cá nhân & repo riêng của bạn | — | **Chưa hoàn tất (chờ user cập nhật `"team"` + remote + tag)** |

## 2. Minh họa trực quan (`1280×720`)
- [screenshot_menu.png](screenshot_menu.png): Menu chính chọn hành trình 3 Đêm hoặc vào Cài đặt (đã kiểm tra lưu `localStorage` qua reload trang).
- [screenshot_night1.png](screenshot_night1.png): Đêm 1 – Đảo Bến (`40m`) với thanh 10 ô đom đóm, biểu tượng hồi chiêu Lướt/Tỏa Sáng và vòng hào quang sáng quanh nón lá.
- [screenshot_pause.png](screenshot_pause.png): Màn hình Tạm dừng khi nhấn `Esc` (đồng hồ đêm đứng yên hoàn toàn).
- [screenshot_night2.png](screenshot_night2.png): Đêm 2 – Đảo Cau với 2 đảo tròn `28m`, cầu tre nối giữa và Bùa Gió đỏ viền vàng.
- [screenshot_night3.png](screenshot_night3.png): Đêm 3 – Đảo Chuông 3 tầng, dốc `30°`/`150°`, Tháp chuông, mũi tên chỉ đèn ngoài màn hình (`L1 (16m)`) và bộ đo `#hud-fps` đạt `>= 30 FPS`.
