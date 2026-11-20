# Đảo Đèn Lồng — Ba Hòn Đảo (Phase 2 · Contract v1.1)

> **Video demo:** `[TODO Phase 4 — Sẽ đính kèm demo.mp4 (< 5 phút) vào Release v1.0.0 hoặc docs/demo/demo.mp4]`
> Tài liệu đề bài gốc của khóa học được lưu giữ tại [docs/lab/LAB_README.md](docs/lab/LAB_README.md).

Game 3D góc nhìn thứ ba **Đảo Đèn Lồng** (Day 12 · AI SDLC Lab — Phase 2). Người chơi điều khiển **Mây** mang ánh sáng qua **3 Đêm**: **Đêm 1 (Đảo Bến)**, **Đêm 2 (Đảo Cau)** và **Đêm 3 (Đảo Chuông)** để thắp sáng toàn bộ Đèn Lồng Lớn, tránh **Bóng Mực**, đối phó **Gió Lạc** và tận dụng **Bùa Gió**.

---

## 1. Cài đặt và Chạy game (1 lệnh, không cần cài thêm thư viện)

Dự án dùng **Python 3 chuẩn (stdlib)** cho lõi mô phỏng 60Hz + máy chủ WebSocket và **Three.js r170 (MIT)** đóng gói sẵn tại `web/vendor/three.module.min.js`.

**Trên macOS / Linux:**
```bash
python3 -m src.play
```

**Trên Windows:**
```powershell
python -m src.play
```

Mở trình duyệt tại `http://127.0.0.1:8765/`. Tùy chọn: `--port 8080`, `--no-open`.

---

## 2. Điều khiển trong game

| Phím / Chuột | Hành động |
|---|---|
| `W` `A` `S` `D` / Phím mũi tên | Di chuyển (`6.0 m/s`, tăng thành `7.2 m/s` khi có Bùa Gió) |
| `Space` | Nhảy (`7.0 m/s`, chỉ nhảy khi chạm đất) |
| `Shift` | **Lướt** (`14.0 m/s` trong `0.2s`, hồi `1.5s`; giữ nguyên độ cao khi lướt trên không; không hồi chiêu khi có Bùa Gió) |
| `E` | Nạp đom đóm vào Đèn Lồng Lớn gần nhất (bán kính `2.0m`, tối đa `10`/đèn) |
| `F` hoặc `J` | **Tỏa Sáng** (tốn `3` đom đóm, bán kính 3D `5.0m`, hồi `3.0s`): đẩy lùi `4.0m` & choáng Bóng Mực `2.0s`; xua Gió Lạc và bắt nhả đom đóm đã cướp |
| Kéo chuột trái / `Q` `C` | Xoay camera 3D (độ nhạy chỉnh trong Cài đặt, tự động lưu) |
| `Esc` hoặc `P` | Tạm dừng / Tiếp tục (đứng yên toàn bộ logic & đồng hồ) |
| `M` | Bật / tắt âm thanh |

---

## 3. Tổng quan 3 Đêm & Quy tắc chuẩn hóa (`game.contract.json` v1.1)

- **Đêm 1 — Đảo Bến (`300s`):** Đảo tròn `40m`, 5 Đèn Lồng Lớn (`L1..L5`), Bóng Mực `4.0 m/s` (tối đa 6). Rơi xuống biển mây (`Y < -10`) mất 1 Ngọn Lửa, mất hết đom đóm đang mang và hồi sinh sau `1.0s`.
- **Đêm 2 — Đảo Cau (`330s`):** Hai đảo `28m` nối bằng cầu tre (`x ∈ [26, 44], z ∈ [-2, 2]`) và 2 bục nhảy gió (`(20,0,18)`, `(50,0,-18)`), 6 Đèn Lồng Lớn (`L1..L6`), **Bùa Gió** tại `(35,0,0)` và **Gió Lạc** (tối đa 2) rình cướp đom đóm khi Mây mang `>= 5`.
- **Đêm 3 — Đảo Chuông (`360s`):** Đảo 3 tầng `45m` (`Y = 0, 3, 6`), 2 dốc `30°`/`150°` rộng `3m`, bục nhảy `(0,3,13)` lên tầng 2, Tháp chuông `r=2m` ở tâm, 7 Đèn Lồng Lớn (`L1..L7`), Bóng Mực nhanh hơn (`4.5 m/s`, tối đa 10), 2 Bùa Gió, Gió Lạc và **Gió mạnh** mỗi `30s` đẩy `2 m/s` trong `5s` (báo trước `2s`).
- **Điểm số chuẩn hóa:** `+10` mỗi đom đóm nạp vào đèn · `+100` mỗi đèn thắp sáng · `+5` mỗi Bóng Mực trúng Tỏa Sáng · khi thắng thưởng `+ floor(giây còn lại) × 2 + 50 × Ngọn Lửa còn lại`. Tổng điểm hành trình cộng dồn qua các Đêm thắng cho tới màn hình Bình Minh.

---

## 4. Kiểm thử & Chế độ Headless (Test Contract v1.1)

**Chạy toàn bộ 28 unit & contract tests:**
```bash
python3 -m unittest discover -s tests -v
```
*(Trên Windows thay `python3` bằng `python`.)*

**Chạy cổng kiểm chứng đầy đủ (Contract v1.1 + 28 tests + Tất định Đêm 1 & 3 + Benchmark 21,600 tick `<= 30s`):**
```bash
python3 .agents/hooks/verify_gate.py
```

**Chạy chế độ headless trực tiếp (`--night 1 | 2 | 3`):**
```bash
python3 -m src.headless --seed 1 --night 3 --ticks 21600 --out out.jsonl --snapshot-every 10
```

---

## 5. Sáng tạo của tôi

Mọi phần sáng tạo đều được giữ **thuần túy ở lớp hiển thị và âm thanh (`web/main.js`)**, tách biệt hoàn toàn khỏi lõi `src/sim/` nên không làm thay đổi bất kỳ dòng JSONL nào của chế độ headless:

1. **Vòng hào quang đom đóm quanh nón lá (`Orbiting Firefly Halo`) & Hiệu ứng hạt:** Số đom đóm đang mang xoay quanh vành nón lá của Mây; kèm bùng sáng hạt vàng/tím khi nhặt, nạp đèn, lướt, chạm Bóng Mực, tỏa sáng và lá bay khi gió mạnh nổi lên ở Đêm 3.
2. **Nhạc nền & Bộ tổng hợp Âm thanh Cổ tích (`Procedural Web Audio Synth`):** Tự tổng hợp nhạc nền đêm và hiệu ứng riêng cho cả 12+ hành động (nhặt, nạp, thắp đèn, tỏa sáng, bị đánh, nhảy, lướt, nhặt bùa, Gió Lạc cướp/thả, cảnh báo gió, Bóng Mực xuất hiện, đếm ngược 10 giây cuối, thắng/thua) với thanh chỉnh âm lượng lưu trong `localStorage`.

*Bằng chứng không phá Test Contract:* Toàn bộ `28` tests, kiểm tra tính tất định SHA-256 Đêm 1 & Đêm 3 (`docs/proof/phase-2/determinism_diff.txt`), benchmark `21,600` tick Đêm 3 (`docs/proof/phase-2/perf_night3_21600.txt`), và kiểm chứng `1280×720` (`docs/proof/phase-2/EVIDENCE.md`) đều đạt hoàn toàn.

---

## 6. Cấu trúc thư mục

- `src/sim/` — Lõi mô phỏng 60Hz (`maps.py`, `engine.py`, `config.py`, `prng.py`, `validation.py`)
- `src/headless.py` — CLI Test Contract v1.1 (`--night 1|2|3`, exit `2` khi sai định dạng)
- `src/play.py` — Máy chủ HTTP + WebSocket một cổng phục vụ chiến dịch 3 Đêm
- `web/` — Giao diện 3D Three.js r170, bảng màu chuẩn, Menu/Intro/Pause/Settings/Bình Minh & HUD
- `tests/` — Bộ test hồi quy v1.1, test tính năng Phase 2 & kiểm tra hiệu năng
- `docs/notes/` — Spec Phase 2 (`phase-2-spec.md`), đánh giá (`phase-1/2-evaluation.md`), nhật ký AI (`ai-log.md`)
- `docs/proof/` — Bằng chứng thực tế `phase-1/` và `phase-2/`
- `AGENTS.md`, `.agents/`, `.claude/`, `.github/workflows/ci.yml` — Harness AI & CI tự động
