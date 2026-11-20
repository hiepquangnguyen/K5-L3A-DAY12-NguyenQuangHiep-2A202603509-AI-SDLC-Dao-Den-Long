# Đảo Đèn Lồng — Đèn Cạn Dầu (Phase 3 · Contract v1.2)

> **Video demo:** `[TODO Phase 4 — Sẽ đính kèm demo.mp4 (< 5 phút) vào Release v1.0.0 hoặc docs/demo/demo.mp4]`
> Tài liệu đề bài gốc của khóa học được lưu giữ tại [docs/lab/LAB_README.md](docs/lab/LAB_README.md) · Quyết định thiết kế: [ADR-001](docs/notes/ADR-001-lantern-fuel-and-dawn-win.md) · Thay đổi phá vỡ tương thích: [CHANGELOG.md](CHANGELOG.md).

Game 3D góc nhìn thứ ba **Đảo Đèn Lồng** (Day 12 · AI SDLC Lab — Phase 3). Người chơi điều khiển **Mây** giữ ánh sáng qua **3 Đêm**: **Đêm 1 (Đảo Bến)**, **Đêm 2 (Đảo Cau)** và **Đêm 3 (Đảo Chuông)** — không chỉ thắp đèn mà còn phải **châm dầu, bảo vệ đèn sắp cạn khỏi Bóng Mực hút dầu và trụ vững tới bình minh** (`≥ ceil(0.6 × tổng đèn)`).

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
| `E` | Nạp đom đóm vào đèn gần nhất (`2.0m`): thắp mới (`10`), thắp lại đèn đã từng sáng (`5`), hoặc **châm dầu** đèn đang sáng (`used = min(mang, ceil((100 - fuel)/10))`; bỏ qua đèn đã đầy `100`) |
| `F` hoặc `J` | **Tỏa Sáng** (tốn `3` đom đóm, bán kính 3D `5.0m`, hồi `3.0s`): đẩy lùi `4.0m` & choáng Bóng Mực `2.0s`; xua Gió Lạc và bắt nhả đom đóm đã cướp |
| Kéo chuột trái / `Q` `C` | Xoay camera 3D (độ nhạy chỉnh trong Cài đặt, tự động lưu) |
| `Esc` hoặc `P` | Tạm dừng / Tiếp tục (đứng yên toàn bộ logic & đồng hồ) |
| `M` | Bật / tắt âm thanh |

---

## 3. Tổng quan 3 Đêm & Luật Phase 3 (`game.contract.json` v1.2)

- **Luật thắng tới Bình Minh:** Không còn thắng sớm khi thắp hết đèn. Mây thắng (`dawn_survived`) khi còn sống lúc hết giờ và có số đèn sáng `≥ ceil(0.6 × tổng đèn)`: **Đêm 1** `3/5` (`240s`), **Đêm 2** `4/6` (`270s`), **Đêm 3** `5/7` (`300s`). Hết Ngọn Lửa luôn thua `no_flames` trước kể cả ở tick bình minh; hết giờ dưới ngưỡng thua `dawn`.
- **Nhiên liệu đèn & Bóng Mực hút dầu (`drain`):** Đèn vừa thắp có `fuel = 100`, tự hao `1.0/s` (lưu theo đơn vị nguyên `1/60` để tránh sai số số thực), tắt khi `fuel ≤ 0` (`lantern_out`, giữ `ever_lit = true` để thắp lại chỉ cần `5` đom đóm). Đèn có `fuel < 30` mất vùng an toàn (`30.0` vẫn còn) và nhấp nháy `1 Hz`; Bóng Mực ở trạng thái `wander` sẽ tiến về đèn yếu gần nhất, vào `drain` khi `≤ 2.0m` để hút `5/s` cộng dồn (dù châm lại `≥ 30` sẽ đẩy bóng trong `6m` ra ngoài trong `≤ 30` tick).
- **Sức chứa tăng dần & Bảng màu dễ phân biệt:** Sức chứa đom đóm tăng theo số lần thắp thành công trong Đêm: `min(20, 10 + 2 × successful_lights)` (reset đầu mỗi Đêm). Trong *Cài đặt*, bật **"Bảng màu dễ phân biệt"** (tự động lưu) đổi viền/mắt Bóng Mực `#7A3CFF → #00B3FF` và cảnh báo `#FF5A5F → #FFFFFF` kèm biểu tượng `⚠`; đèn tắt luôn xẹp `-20%` kèm vết rách giấy phân biệt không cần màu.
- **Địa hình 3 Đêm:** **Đêm 1 (Đảo Bến)** tròn `40m`; **Đêm 2 (Đảo Cau)** 2 đảo `28m`, cầu tre, 2 bục nhảy gió, Bùa Gió & Gió Lạc; **Đêm 3 (Đảo Chuông)** đảo 3 tầng `45m`, 2 dốc `30°/150°`, bục nhảy, Tháp chuông, Bóng Mực `4.5 m/s` & Gió mạnh `2 m/s`.
- **Điểm số chuẩn hóa (v1.2):** `+5` mỗi đom đóm nạp/châm dầu · `+100` thắp lần đầu · `+40` thắp lại · Tỏa Sáng `+5` mỗi Bóng Mực (`+15` nếu đang `drain`) · thưởng bình minh (chỉ khi thắng): `+50 + floor(fuel)` mỗi đèn đang sáng `+ 50` mỗi Ngọn Lửa còn lại (bỏ thưởng thời gian).

---

## 4. Kiểm thử & Chế độ Headless (Test Contract v1.2)

**Chạy toàn bộ 35 unit & contract tests:**
```bash
python3 -m unittest discover -s tests -v
```
*(Trên Windows thay `python3` bằng `python`.)*

**Chạy cổng kiểm chứng đầy đủ (Contract v1.2 + 35 tests + Tất định Đêm 1 & 3 + Benchmark Đêm 3 `<= 30s`):**
```bash
python3 .agents/hooks/verify_gate.py
```

**Sinh lại toàn bộ bằng chứng Phase 3 (`docs/proof/phase-3/`):**
```bash
python3 scripts/run_phase3_verification.py
```

**Chạy chế độ headless trực tiếp (`--night 1 | 2 | 3`):**
```bash
python3 -m src.headless --seed 1 --night 3 --ticks 18000 --out out.jsonl --snapshot-every 10
```

---

## 5. Sáng tạo của tôi

Mọi phần sáng tạo đều được giữ **thuần túy ở lớp hiển thị và âm thanh (`web/`)**, tách biệt hoàn toàn khỏi lõi `src/sim/` nên không làm thay đổi bất kỳ dòng JSONL nào của chế độ headless:

1. **Vòng hào quang đom đóm quanh nón lá (`Orbiting Firefly Halo`, mở rộng tối đa 20 hạt) & Hiệu ứng hạt:** Số đom đóm đang mang xoay quanh vành nón lá của Mây; kèm bùng sáng hạt vàng/tím-xanh khi nhặt, châm dầu, tắt đèn, hút dầu, thắp đèn, lướt, chạm Bóng Mực, tỏa sáng và lá bay Đêm 3. Thanh dầu billboard trên đỉnh đèn, vòng phản hồi `drain`, và nhấp nháy `1 Hz` dưới ngưỡng `30` được dựng tách riêng ở lớp Three.js.
2. **Nhạc nền & Bộ tổng hợp Âm thanh Cổ tích (`Procedural Web Audio Synth`):** Tự tổng hợp nhạc nền đêm và hiệu ứng riêng cho mọi sự kiện (bao gồm `lantern_out`, `refuel`, nhặt, thắp đèn, tỏa sáng, bị đánh, nhảy, lướt, bùa, gió, đếm ngược 10 giây cuối, thắng/thua) với âm lượng và chế độ mù màu lưu trong `localStorage`.

*Bằng chứng không phá Test Contract:* Toàn bộ `35` tests (`tests/test_phase3_change_request.py` cùng bộ hồi quy v1.1/v1.0 không bị thay thế), kiểm tra tính tất định SHA-256 Đêm 1 & Đêm 3 ([determinism_diff.txt](docs/proof/phase-3/determinism_diff.txt)), benchmark Đêm 3 `18,000` & `21,600` tick ([perf_night3_dawn.txt](docs/proof/phase-3/perf_night3_dawn.txt)), và kiểm chứng `1280×720` ([EVIDENCE.md](docs/proof/phase-3/EVIDENCE.md)) đều đạt hoàn toàn.

---

## 6. Cấu trúc thư mục

- `src/sim/` — Lõi mô phỏng 60Hz (`maps.py`, `engine.py`, `config.py`, `prng.py`, `validation.py`)
- `src/headless.py` — CLI Test Contract v1.2 (`--night 1|2|3`, exit `2` khi sai định dạng)
- `src/play.py` — Máy chủ HTTP + WebSocket một cổng phục vụ chiến dịch 3 Đêm
- `web/` — Giao diện 3D Three.js r170, Menu/Intro/Pause/Settings (gồm Bảng màu dễ phân biệt)/Bình Minh, thanh dầu đèn & HUD
- `tests/` — Bộ test hồi quy v1.2, Phase 2 & `test_phase3_change_request.py` (`35` tests)
- `docs/notes/` — ADR ([ADR-001](docs/notes/ADR-001-lantern-fuel-and-dawn-win.md)), Spec Phase 2 (`phase-2-spec.md`), đánh giá (`phase-1/2/3-evaluation.md`), nhật ký AI (`ai-log.md`)
- `docs/proof/` — Bằng chứng thực tế `phase-1/`, `phase-2/`, `phase-3/`
- `CHANGELOG.md`, `AGENTS.md`, `.agents/`, `.claude/`, `.github/workflows/ci.yml` — Changelog breaking changes, Harness AI & CI tự động
