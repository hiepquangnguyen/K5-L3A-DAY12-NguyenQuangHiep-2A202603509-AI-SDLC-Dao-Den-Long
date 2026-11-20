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


---

# Nhật ký dùng AI & Quản lý Token — Phase 2

## 1. Cập nhật Harness AI cho Phase 2
- Cập nhật [AGENTS.md](../../AGENTS.md) thêm quy ước module `src/sim/maps.py`, thứ tự 12 bước/tick, danh sách trạng thái chính xác của Bóng Mực (`spawning|wander|chase|recoil|stunned`) & Gió Lạc (`idle|chase|flee|removed`), và ngưỡng hiệu năng `21,600 ticks <= 30s`, `>= 30 FPS @ 1280x720`.
- Cập nhật [SKILL.md](../../.agents/skills/verify-phase/SKILL.md) và [verify_gate.py](../../.agents/hooks/verify_gate.py) tự động chặn nếu thiếu khóa v1.1, sai tính tất định Đêm 1/Đêm 3 hoặc chạy `21,600` tick vượt quá `30s`.

## 2. Các lỗi AI phát hiện & cách khắc phục trong Phase 2

| Lần | Vấn đề phát sinh | Cách phát hiện | Cách sửa & phòng ngừa |
|---|---|---|---|
| **5** | Kịch bản test `p2_drifter_steal_drop` đặt tick pulse ở `80`, nhưng Gió Lạc chạy `7 m/s` đã cướp ở tick `41` và chạy ra `5.75m > 5.0m` nên trượt pulse | Chạy `unittest` đối chiếu tính toán quãng đường `7 m/s` | Chỉnh tick pulse sang `55` (cự ly `2.83m`) đúng lúc Gió Lạc đang `flee` mang đom đóm. |
| **6** | `RingGeometry(..., 0, Math.PI)` trên tầng 1 Đêm 3 sau `rotateX(-PI/2)` bị lật sang bán cầu `z < 0`, tạo thành nửa vòng tròn lơ lửng trên đầu Mây; và `#offscreen-arrow` đè nhẹ lên góc kỹ năng | Mở và xem trực tiếp ảnh chụp `step_20_shot_1.png` từ `browser` subagent | Đổi góc `RingGeometry` sang `(Math.PI, Math.PI)` và kẹp biên `#offscreen-arrow`; chụp lại ảnh Đêm 3 xác nhận hết lỗi. |
| **7** | Không đọc được `window.__gamePerf` do sandbox trình duyệt chặn `page.evaluate` | Thông báo `BLOCKED / EVALUATE_UNSUPPORTED_IN_SANDBOX` từ `browser` subagent | Bổ sung hiển thị `#hud-fps` trực tiếp trên DOM HUD và đọc lại thành công (`FPS: 30` / `58` ở `1280×720`). |
| **8** | Rà soát độc lập phát hiện đi xuyên hông dốc `30°`/`150°`, Gió Lạc `idle` cướp khi `carried == 0`, lỗi Python `4300`-digit `ValueError` trả exit `1` thay vì `2`, và 5 lỗi biên khác | Subagent `research` độc lập kiểm toán `maps.py`, `validation.py`, `engine.py` | Vá toàn bộ 8 điểm và thêm `test_audit_regressions_*` + test `5000`-digit exit code `2` vào CI & `verify_gate.py`. |

## 3. Tiết kiệm Token ở Phase 2
- Giữ ranh giới rõ ràng giữa `src/sim/` và `web/` giúp tái sử dụng nguyên khung HTTP/WS ở Phase 1, chỉ bổ sung bảng đồ thị 3 màn và các thực thể mới mà không phải viết lại kiến trúc.
- Dồn kiểm tra 21,600 tick và 28 tests vào một lệnh `verify_gate.py` duy nhất giúp giảm hẳn các lượt gọi lặp lại của agent.
