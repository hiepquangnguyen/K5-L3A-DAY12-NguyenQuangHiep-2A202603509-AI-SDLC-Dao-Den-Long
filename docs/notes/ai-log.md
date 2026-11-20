# Nhật ký dùng AI & Quản lý Token — Phase 1

## 1. Công cụ & Harness đã sử dụng
- **Agent điều phối & lập trình:** Antigravity IDE (chế độ lập kế hoạch + thực thi tách pha).
- **Subagent kiểm thử giao diện 3D:** `browser` subagent kiểm tra WebGL, WebSocket, console và tương tác phím/HUD trên `http://127.0.0.1:8765/`.
- **Subagent đánh giá độc lập:** `research` subagent (chế độ chỉ đọc) kiểm toán mã nguồn đối chiếu trực tiếp Test Contract v1.0.
- **Harness lưu trong repo:** `AGENTS.md`, `.agents/skills/verify-phase/SKILL.md`, `.agents/hooks/verify_gate.py`, `.claude/settings.json`, `.github/workflows/ci.yml`.

## 2. Các lần AI sai / thiếu sót & Cách phát hiện + Khắc phục

| Lần | Vấn đề phát sinh | Cách phát hiện | Cách sửa & điều chỉnh Harness |
|---|---|---|---|
| **1** | Đề xuất ban đầu dự định dùng Node.js + Vite/Three.js, nhưng máy thực tế không cài `node`/`npm` | Chạy lệnh kiểm tra môi trường (`node -v`, `python --version`) trước khi lập kế hoạch | Chuyển sang **Python 3 stdlib** (`src/sim/`, `src/play.py`) + vendor trực tiếp `three.module.min.js` r170, ghi rõ quy tắc không phụ thuộc `pip`/`npm` vào `AGENTS.md`. |
| **2** | `GameSim._apply_scenario` chỉ xử lý dict trong `motes`, gây lỗi `AttributeError` khi truyền list `[x, y, z]` trực tiếp trong Python | Chạy `unittest` (`test_xz_distance_ignores_jump_height_and_lands_at_zero`) | Sửa `src/sim/engine.py` hỗ trợ cả `list` lẫn `dict`. |
| **3** | Test `test_rising_edge_for_interact_and_pulse` khởi tạo `carried=8` nhưng tiêu `5` (nạp đèn) + `2` (pulse 1) nên lần pulse 2 chỉ còn `1 < 2` | Chạy `unittest` và phân tích lại luồng tiêu hao ánh sáng | Sửa fixture test sang `carried=10` để kiểm tra đúng hồi chiêu & rising edge. |
| **4** | File input chứa byte non-UTF-8 hoặc số `10**400` làm `src/headless.py` thoát mã `1` thay vì `2`; `math.floor(time_left_s)` lệch 1s với số thực; `--help` trả exit `1` | Rà soát độc lập bởi `research` subagent đối chiếu `validation.py`, `engine.py`, `headless.py` | Bắt `UnicodeDecodeError` và `OverflowError` trong `validation.py`, thêm `+ 1e-9` trong `engine.py`, sửa exit code `--help` trong `headless.py`, và bổ sung unit/contract test chặn tái diễn. |

## 3. Ghi nhận & Tiết kiệm Token / Chi phí
- **Lưu ý trung thực:** Giao diện agent đang dùng không hiển thị bộ đếm số token cụ thể cho từng lượt chạy, nên không bịa con số token giả; chi phí được kiểm soát bằng kỷ luật kiến trúc và ngữ cảnh như sau:
  1. **Kiểm tra môi trường trước khi code:** Tránh lãng phí lượt viết cả khung Node/TS rồi mới phát hiện thiếu runtime.
  2. **Giữ `AGENTS.md` ngắn gọn (~30 dòng):** Chỉ giữ lệnh cốt lõi và 8 bất biến của Test Contract v1.0 để không đội ngữ cảnh qua mỗi lần gọi model.
  3. **Dùng model nhẹ (`flash`) cho tác vụ kiểm thử trình duyệt:** Tiết kiệm quota model lớn cho phần thiết kế và kiểm toán logic.
  4. **Kiểm chứng tự động bằng 1 lệnh (`verify_gate.py`):** Thay vì yêu cầu agent tự chạy nhiều lệnh lặp đi lặp lại, gộp toàn bộ kiểm tra vào 1 script quyết định xanh/đỏ rõ ràng.
