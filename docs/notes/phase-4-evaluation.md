# Đánh giá Phase 4 — TICKET-04 "Bình minh: phát hành v1.0.0" (Contract v1.3)

## 1. Tổng quan Phạm vi Hoàn thành
Phase 4 đưa *Đảo Đèn Lồng* từ bản chơi được (Contract `v1.2`) thành bản phát hành `v1.0.0` hoàn chỉnh (`game.contract.json` `"contract_version": "1.3"`, `"bench_cmd": "python3 -m src.bench"`, `"soak_cmd": "python3 -m src.soak"`):
- **Benchmark đồ họa chuẩn (`src/bench.py`, `web/bench.html`, `web/bench.js`):** Khởi tạo `GameSim.create_benchmark(seed=42)` ở Đêm 1 (`200` Bóng Mực `wander`, `100` đom đóm, `L1–L3` sáng `fuel=100`, Mây đứng tại `(0,0,0)`), camera bay vòng tròn `(30,15,0)` ngược chiều kim đồng hồ `15s/vòng`, warm-up `3s`, đo đúng `30s`.
- **Soak test ổn định (`src/soak.py`, `src/sim/sysmem.py`):** Chạy `10` Đêm liên tục (`1→2→3`) kèm input ngẫu nhiên theo seed, đo RSS đa nền tảng thuần stdlib (`Windows ctypes`, `Linux /proc + ps`, `macOS ps`).
- **Bảng xếp hạng Top 10 cục bộ (`src/sim/leaderboard.py`, `src/play.py`, `web/`):** Lưu bền vững tại `data/leaderboard.json`, chuẩn hóa tên `3–12` ký tự hỗ trợ tiếng Việt có dấu, API `/api/leaderboard` có kiểm tra kiểu JSON chặt chẽ, xuất JSON qua `--export-leaderboard out.json`.
- **Tính năng Dễ tiếp cận (`web/`):** Đổi `9` phím điều khiển có cảnh báo trùng + khôi phục mặc định, phụ đề trực quan + mũi tên hướng Bóng Mực mới xuất hiện, bật/tắt Giảm chuyển động, cỡ chữ gốc `18px` tại `1280×720` + chế độ **Chữ lớn (`×1.25` -> `22.5px`)**.
- **Đóng gói & Tài liệu:** `Dockerfile`, `run.sh` (`100755`), `run.bat`, `scripts/build_release.py`, `README.md`, `CHANGELOG.md`, `CREDITS.md`, [retro.md](retro.md).

## 2. Kết quả Đo & Kiểm chứng Thực tế
- **Benchmark (`bench.json`):** `avg_fps = 142.6` (`>= 60`), `p1_low_fps = 36.1` (`>= 30`), `frame_ms_p95 = 12.6 ms`, `frames = 4280`, `load_ms = 1862 ms` (`<= 10000`), `peak_mem_mb = 849.7`, `vsync_off = true` trên Intel HD Graphics 630 (Windows 10 AMD64).
- **Soak (`soak.json`):** `nights = 10`, `crashes = 0`, `mem_start_mb = 17.4`, `mem_end_mb = 17.5` (`<= 1.2 × 17.4 = 20.88 MiB`), `duration_s = 5.41s`.
- **Bộ test & Gate:** `41` tests trong `tests/` đạt `OK` (`31.787s`, `0` skip); hash SHA-256 Đêm 1 (`39e44585...`) và Đêm 3 (`c5447a10...`, `4.908s / 5.304s`) giữ nguyên tất định không thay đổi so với Phase 3.
- **Rà soát độc lập (`research` subagent):** `0 Critical, 0 High`, xử lý toàn bộ `5 Medium` + các điểm `Low` chọn lọc (bit `+x` Unix trong `build_release.py`, `ctypes` Win64 `HANDLE`/`INVALID_HANDLE_VALUE` và cây `ps` macOS trong `sysmem.py`, kiểm tra kiểu JSON chặt ở `POST /api/leaderboard`, `is_relative_to`, guard `NaN` mũi tên và reset cảnh báo khi restart).
- **Kiểm thử trình duyệt `1280×720` (`browser` subagent):** `0` lỗi console, `0` lỗi mạng, kiểm chứng 5 màn hình: Menu, Bảng xếp hạng, Cài đặt (cảnh báo trùng `KeyW` -> đổi `KeyG` -> khôi phục `Space`, lưu qua reload), Đêm 1 chữ lớn (`22.5px`, `FPS: 61`), Đêm 1 mặc định (`18px`, `FPS: 30 (avg 56.4)` tại frame chụp / `59` HUD).

## 3. Hạng mục chờ Người dùng Ghi hình
- Do môi trường máy chủ Windows không cài `ffmpeg`/trình quay màn hình tự động, file video demo `< 5 phút` (`demo.mp4`) chưa được tự tạo; hướng dẫn và lệnh `gh release upload v1.0.0 demo.mp4` được cung cấp đầy đủ ở tổng kết bàn giao.
