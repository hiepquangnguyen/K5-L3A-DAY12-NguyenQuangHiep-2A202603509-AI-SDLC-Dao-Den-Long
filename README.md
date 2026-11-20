# Đảo Đèn Lồng — Đêm 1: Đảo Bến

> **Video demo:** `[TODO Phase 4 — Sẽ đính kèm demo.mp4 (< 5 phút) vào Release v1.0.0 hoặc docs/demo/demo.mp4]`
> Tài liệu đề bài gốc của khóa học được lưu giữ tại [docs/lab/LAB_README.md](docs/lab/LAB_README.md).

Game 3D góc nhìn thứ ba **Đảo Đèn Lồng** (Day 12 · AI SDLC Lab — Phase 1). Người chơi điều khiển **Mây**, cô bé giữ đèn đội nón lá có treo đèn lồng nhỏ, thu thập đom đóm vàng cam để thắp sáng 5 Đèn Lồng Lớn trên Đảo Bến và dùng ánh sáng đẩy lùi Bóng Mực trong màn sương đen.

---

## 1. Cài đặt và Chạy game (1 lệnh, không cần cài thêm thư viện)

Dự án chỉ dùng **Python 3 chuẩn (stdlib)** cho máy chủ và mô phỏng 60Hz, cùng **Three.js r170 (MIT)** đóng gói sẵn tại `web/vendor/three.module.min.js`.

**Trên macOS / Linux:**
```bash
python3 -m src.play
```

**Trên Windows:**
```powershell
python -m src.play
```

Lệnh trên tự mở trình duyệt tại `http://127.0.0.1:8765/`. Nếu cần đổi cổng hoặc không tự mở trình duyệt: `python3 -m src.play --port 8080 --no-open`.

---

## 2. Điều khiển trong game

| Phím / Chuột | Hành động |
|---|---|
| `W` `A` `S` `D` hoặc Phím mũi tên | Di chuyển Mây theo hướng camera |
| `Space` | Nhảy |
| `E` hoặc `F` | Nạp ánh sáng vào Đèn Lồng Lớn gần nhất (khi đứng trong bán kính `3.0m`) |
| `Shift` hoặc `J` | Tỏa sáng (`pulse`, tốn `2` đom đóm): đẩy lùi `6.0m` và làm choáng Bóng Mực `3.0s` |
| Kéo chuột trái hoặc `Q` / `C` | Xoay camera 3D quanh Mây |
| `M` | Bật / tắt âm thanh |
| `R` | Chơi lại Đêm 1 |

---

## 3. Luật chơi, Điểm số & Tham số (`game.contract.json`)

- **Thắng:** Thắp sáng đủ 5 Đèn Lồng Lớn (`L1`..`L5`, mỗi đèn cần `5` đom đóm). Đảo và bầu trời sáng dần lên theo số đèn được thắp; đèn đã sáng tạo vùng an toàn bán kính `5.0m` khiến Bóng Mực không thể bước vào.
- **Thua:** Hết `3` ngọn lửa (máu) do chạm Bóng Mực, hoặc hết `300s` thời gian đêm trước bình minh.
- **Không rơi khỏi đảo (`fall_enabled: false`):** Người chơi và Bóng Mực bị giữ an toàn trong mép tròn của Đảo Bến (`45m`).
- **Công thức tính điểm:**
  - Nhặt 1 đom đóm: `+10` điểm (`per_mote`)
  - Thắp sáng 1 Đèn Lồng Lớn: `+200` điểm (`per_lantern`)
  - Làm choáng 1 Bóng Mực bằng Tỏa sáng: `+50` điểm (`per_stun`)
  - Thưởng khi thắng: `+2` điểm/giây còn lại (`per_second_left`) + `+100` điểm/ngọn lửa còn lại (`per_flame_left`)

---

## 4. Kiểm thử & Chế độ Headless (Test Contract v1.0)

**Chạy toàn bộ unit test + kiểm tra hợp đồng headless:**
```bash
python3 -m unittest discover -s tests -v
```
*(Trên Windows thay `python3` bằng `python`.)*

**Chạy cổng kiểm chứng đầy đủ (compileall + contract consistency + tests + determinism SHA-256):**
```bash
python3 .agents/hooks/verify_gate.py
```

**Chạy chế độ headless trực tiếp:**
```bash
python3 -m src.headless --seed 1 --night 1 --ticks 600 --out out.jsonl --snapshot-every 10
```

Hỗ trợ đầy đủ `--scenario <file.json>` và `--inputs <file.json>`, tuân thủ cố định 60Hz (`DT = 1/60s`), đo khoảng cách trên mặt phẳng XZ (`<= r`), trả mã thoát `2` nếu file đầu vào sai định dạng, và đảm bảo tính tất định tuyệt đối qua `SeededRNG` (`src/sim/prng.py`).

---

## 5. Sáng tạo của tôi

Hai điểm sáng tạo được bổ sung **hoàn toàn ở lớp hiển thị & âm thanh (`web/main.js`)**, **tách biệt 100% khỏi lõi mô phỏng `src/sim/`** nên không tạo bất kỳ thay đổi nào đối với đầu ra JSONL của chế độ headless:

1. **Vòng hào quang đom đóm quanh nón lá (`Orbiting Firefly Halo`) & Sóng tỏa sáng:** Số lượng đom đóm Mây đang mang (`carried`) bay xoay tròn xung quanh vành nón lá kèm hiệu ứng hạt bùng sáng khi nhặt/nạp đèn và vòng sóng vàng khi kích hoạt `pulse`.
2. **Âm thanh cổ tích tổng hợp trực tiếp (`Procedural Web Audio Synth`):** Tự tổng hợp âm thanh ngũ cung bằng Web Audio API khi nhặt đom đóm, hợp âm ấm khi thắp đèn, sóng âm khi tỏa sáng, tín hiệu trúng đòn và thắng/thua mà không dùng file âm thanh có bản quyền bên ngoài (có nút tắt `[M]`).

*Bằng chứng không phá Test Contract:* Toàn bộ `17` unit & headless contract tests và kiểm tra tính tất định 2 lần chạy (`docs/proof/phase-1/determinism_diff.txt`) đều xanh `100%` sau khi thêm phần sáng tạo; kiểm chứng trực quan WebGL xem tại `docs/proof/phase-1/EVIDENCE.md`.

---

## 6. Cấu trúc thư mục & Ghi chú Phase 1

- `src/sim/` — Lõi mô phỏng 60Hz tất định (`engine.py`, `config.py`, `prng.py`, `validation.py`)
- `src/headless.py` — CLI chế độ headless theo Test Contract v1.0
- `src/play.py` — Máy chủ HTTP + WebSocket một cổng phục vụ game 3D
- `web/` — Giao diện 3D Three.js r170 (`vendor/three.module.min.js`) & HUD
- `tests/` — Unit tests, kịch bản JSON và test hợp đồng headless
- `docs/notes/` — Giả định Phase 1 (`phase-1-assumptions.md`), đánh giá (`phase-1-evaluation.md`), nhật ký AI (`ai-log.md`)
- `docs/proof/phase-1/` — Bằng chứng kiểm chứng, JSONL mẫu, SHA-256 tính tất định và ảnh chụp thực tế
- `AGENTS.md`, `.agents/`, `.claude/`, `.github/workflows/ci.yml` — Harness AI & CI tự động
