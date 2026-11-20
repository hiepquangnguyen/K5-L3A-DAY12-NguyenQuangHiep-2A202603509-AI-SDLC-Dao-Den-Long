# Đánh giá Phase 1 (`PRD-0` & `Test Contract v1.0`)

## 1. Kết quả đạt được
- **Kiến trúc một nguồn chân lý (`src/sim/`):** Toàn bộ luật game 60Hz được tách khỏi giao diện WebGL (`web/`), chạy thuần Python 3 stdlib (không cần `pip` hay `npm`) nên hoạt động đồng nhất trên Windows, macOS và Linux.
- **Tuân thủ Test Contract v1.0:** Đạt **17/17** test đơn vị và test headless CLI (`tests/test_sim_unit.py`, `tests/test_headless_contract.py`), tính tất định SHA-256 trùng khớp `100%` giữa 2 lần chạy độc lập (`6dffd690921f240135f0e105210ab7fe6eaecbda133361028f99996961df18b7`, `77003 bytes`).
- **Game 3D chơi được hoàn chỉnh:** Chạy thử trên trình duyệt qua WebSocket 60Hz (`src/play.py`) với `0` lỗi console/module; đầy đủ di chuyển, nhảy, xoay camera 3D, nhặt đom đóm, nạp đèn, tỏa sáng, Bóng Mực đuổi & vùng an toàn `safe_radius`, sáng dần hòn đảo, HUD và chơi lại.

## 2. Chưa hoàn tất / Lưu ý trước khi gắn tag `phase-1`
- Trường `"team"` trong `game.contract.json` đang giữ placeholder `"TODO-mssv-ho-ten"` theo yêu cầu của bạn (chờ cập nhật MSSV & họ tên trước khi gắn tag `phase-1`).
- Remote Git hiện tại vẫn trỏ về repo mẫu của lớp (`VinUni-AI20k/...`), chưa tạo repo cá nhân Public và chưa đẩy tag `phase-1`.

## 3. Rà soát độc lập & Cải thiện Harness
- Một subagent `research` độc lập đã rà soát toàn bộ `src/sim/`, `src/headless.py`, `game.contract.json` và `tests/` (tách biệt với bước code ban đầu).
- **Những lỗi thật được phát hiện và sửa ngay trong Phase 1:**
  1. Dạng mảng `[x, y, z]` trong `scenario.motes` gây `AttributeError` khi gọi `GameSim` trực tiếp từ Python (do `validation.py` chuẩn hóa sang dict còn unit test truyền list thô) -> đã sửa để `GameSim` nhận cả hai dạng.
  2. File `--inputs`/`--scenario` chứa byte non-UTF-8 hoặc số nguyên quá lớn (`10**400`) gây exit code `1` thay vì `2` -> đã bắt `UnicodeDecodeError` và `OverflowError` thành `ContractFormatError` (exit `2`).
  3. Phép tính `math.floor(time_left_s)` khi thắng có thể bị hụt 1 giây do sai số IEEE-754 -> đã đồng bộ cộng `1e-9` giống điều kiện kiểm tra `dawn`.
  4. Cờ `--help` của `src/headless.py` trả mã thoát `1` thay vì `0` -> đã sửa trả `0`.
  5. Bổ sung xử lý an toàn cho scenario đặt sẵn đèn `deposited >= lantern_cost, lit=false` hoặc Bóng Mực `state="stunned"`.
- **Cải tiến Harness cho Phase 2:**
  - `.agents/hooks/verify_gate.py` tự động chặn kết thúc nếu compileall, kiểm tra đồng nhất `game.contract.json`, 17 unit/contract tests hoặc kiểm tra tính tất định thất bại.
  - `AGENTS.md` tóm tắt ngắn 8 bất biến của Test Contract v1.0 để các phase sau không vô tình làm sai contract cũ.
