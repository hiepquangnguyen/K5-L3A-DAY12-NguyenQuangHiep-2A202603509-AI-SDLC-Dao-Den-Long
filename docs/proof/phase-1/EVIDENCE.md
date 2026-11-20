# Phase 1 Verification Evidence — Đảo Đèn Lồng (PRD-0 & Test Contract v1.0)

> Tất cả kết quả kiểm tra dưới đây được sinh trực tiếp từ mã nguồn thực tế (`scripts/run_phase1_verification.py`, `.agents/hooks/verify_gate.py`, và trình duyệt thực tế tại `http://127.0.0.1:8765/`). Không có kết quả sửa tay.

## 1. Bảng truy vết Yêu cầu → Bằng chứng

| Nhóm | Yêu cầu (PRD-0 / Test Contract v1.0) | Cách kiểm chứng | Bằng chứng | Kết quả |
|---|---|---|---|---|
| **TC-A** | `game.contract.json` đúng schema v1.0 & khớp hằng số engine | Gate kiểm tra nhất quán schema với `src/sim/config.py` | [game.contract.json](../../../game.contract.json), [verify_gate.py](../../../.agents/hooks/verify_gate.py) | **Đạt** *(Lưu ý: trường `"team"` đang để `"TODO-mssv-ho-ten"` chờ điền MSSV cá nhân)* |
| **TC-B** | Headless CLI (`--seed`, `--night 1`, `--scenario`, `--inputs`, `--ticks`, `--out`, `--snapshot-every`) chạy 60Hz, không cửa sổ | Unit + CLI integration tests (`test_headless_contract.py`) | [test_report.txt](test_report.txt), [sample_win.jsonl](sample_win.jsonl) | **Đạt (17/17 tests OK)** |
| **TC-B** | Exit code `0` khi kết thúc/đủ ticks; exit code `2` + stderr khi sai định dạng `inputs`/`scenario` (kể cả non-UTF-8 & integer overflow); `--help` trả `0` | `test_invalid_inputs_and_scenario_exit_code_2`, `test_ticks_zero_and_help_exit_zero` | [test_report.txt](test_report.txt) | **Đạt** |
| **TC-B** | Hệ tọa độ mét, +Y lên, đất `Y=0`, khoảng cách XZ `<= r` bỏ qua độ cao nhảy | `test_xz_distance_ignores_jump_height_and_lands_at_zero` | [test_report.txt](test_report.txt) | **Đạt** |
| **TC-C** | Giữ trạng thái frame, `tick` tăng nghiêm ngặt, công thức xoay theo `cam_yaw_deg`, chuẩn hóa `|move| > 1`, cạnh lên `false -> true` | `test_camera_yaw_rotation_and_normalization`, `test_rising_edge_for_interact_and_pulse`, `test_negative_zero_rounding_and_jump_no_auto_rejump` | [test_report.txt](test_report.txt) | **Đạt** |
| **TC-D** | Dựng scenario không phát event, không cộng điểm; tắt `random_motes`/`random_shades` | `test_scenario_setup_emits_no_events_or_score`, fixtures trong `tests/scenarios/` | [test_report.txt](test_report.txt), [sample_win.jsonl](sample_win.jsonl) | **Đạt** |
| **TC-E** | Đủ 3 loại dòng JSONL (`snapshot`, 7 `event`, `end`), làm tròn 3 chữ số thập phân | `test_pickup_deposit_win_scenario`, `test_pulse_and_safe_radius_scenario`, `test_shade_hit_and_no_flames_loss`, `test_dawn_timeout_loss`, `test_random_shades_deterministic_spawn_event` | [sample_win.jsonl](sample_win.jsonl), [test_report.txt](test_report.txt) | **Đạt** |
| **TC-E** | Tính tất định tuyệt đối: cùng `--seed`, `--scenario`, `--inputs` cho output giống hệt từng byte | Chạy `src.headless --seed 12345 --night 1 --ticks 1500` 2 lần, so SHA-256 | [determinism_diff.txt](determinism_diff.txt) (`sha256: 6dffd690...`, `77003 bytes`, `Exact match: True`) | **Đạt** |
| **PRD-0** | Màn Đêm 1 – Đảo Bến (đảo tròn, 5 Đèn Lồng Lớn, Mây đội nón lá treo đèn, đom đóm vàng cam, Bóng Mực tím đen, HUD, thắng/thua/chơi lại) | Chạy thật `python -m src.play`, kiểm tra trình duyệt WebGL + WebSocket (`0` lỗi console, chơi & nhấn `R` chơi lại) | [screenshot_initial.png](screenshot_initial.png), [screenshot_gameplay.png](screenshot_gameplay.png), [screenshot_restart.png](screenshot_restart.png) | **Đạt** |
| **Sáng tạo** | Vòng đom đóm quanh nón lá + Web Audio synth không ảnh hưởng logic/output headless | Cách ly 100% trong `web/main.js`, chế độ headless không import `web/` | [determinism_diff.txt](determinism_diff.txt), [test_report.txt](test_report.txt) | **Đạt** |
| **Nộp bài** | Đặt tên repo public, điền `"team"` trong `game.contract.json`, gắn tag `phase-1` & push | Chờ thông tin cá nhân & repo riêng của bạn | — | **Chưa hoàn tất (chờ user cập nhật `"team"` + remote + tag `phase-1`)** |

## 2. Minh họa trực quan (Chạy game 3D thực tế tại `http://127.0.0.1:8765/`)

- **Trạng thái ban đầu (`screenshot_initial.png`):** WebSocket kết nối xanh (`conn-dot online`), timer đếm ngược từ `05:00`, Mây đội nón lá có ánh sáng ấm, 5 Đèn Lồng Lớn, đom đóm vàng cam và Bóng Mực tím đen hiển thị đầy đủ cùng HUD tiếng Việt.
- **Đang chơi (`screenshot_gameplay.png`):** Sau khi di chuyển, nhảy và nhặt đom đóm, HUD cập nhật trực tiếp `✨ 1 / 10`, `Điểm: 20`, va chạm Bóng Mực hiện toast `Bị Bóng Mực chạm!` và giảm ngọn lửa.
- **Chơi lại bằng `[R]` (`screenshot_restart.png`):** Toàn bộ chỉ số (ngọn lửa `3/3`, đom đóm `0/10`, đèn `0/5`, điểm `0`, đồng hồ `05:00`) được khởi tạo lại sạch sẽ.
