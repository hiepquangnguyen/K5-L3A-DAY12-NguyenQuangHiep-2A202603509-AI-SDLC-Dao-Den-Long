# Đánh giá Phase 2 (`TICKET-02` — "Ba hòn đảo" & Contract v1.1)

## 1. Kết quả đạt được
- **Chuẩn hóa hoàn toàn sang Contract v1.1:** Toàn bộ hằng số vật lý, bán kính, điểm số (`+10` lúc nạp đèn thay vì lúc nhặt) và thứ tự xử lý 12 bước/tick khớp tuyệt đối với Ticket-02 (`28/28` unit + headless contract tests xanh).
- **Mở rộng thành công 3 Đêm & tính năng mới:**
  - `src/sim/maps.py` đóng gói chuẩn hình học, cầu tre, bục nhảy, dốc `30°`/`150°`, vách đứng, Tháp chuông và bảng điểm sinh cho Đảo Bến, Đảo Cau và Đảo Chuông.
  - Gió Lạc, Bùa Gió, Lướt (`dash`), Rơi & Hồi sinh, Tạm dừng (`paused`) đóng băng `sim_tick`/TTL, và Gió mạnh Đêm 3 hoạt động đồng nhất giữa CLI headless và WebGL 3D.
- **Hiệu năng & Tất định vượt ngưỡng:**
  - Headless Đêm 3 `21,600` tick chạy thực tế trong `2.370s` / `2.796s` (dưới xa ngưỡng `30.0s`).
  - Client 3D ở `1280×720` đạt `0` lỗi console/network và `#hud-fps` đo thực tế `FPS: 30 (avg 30.0)` / `FPS: 58 (avg 31.5)` ngay cả trong trình duyệt sandbox.

## 2. Lỗi phát hiện & khắc phục trong Phase 2
1. **Lỗi thị giác phát hiện từ ảnh chụp thật (`web/main.js`):** `THREE.RingGeometry(23.5, 24.0, 36, 1, 0, Math.PI)` sau `rotateX(-Math.PI / 2)` xoay sang `z < 0` làm viền cát tầng 1 Đêm 3 lơ lửng trên không; đã đổi góc sang `[Math.PI, 2*Math.PI]` để nằm khít trên tầng 1 `z > 0`, đồng thời kẹp vị trí `#offscreen-arrow` tránh đè lên bảng kỹ năng góc dưới phải.
2. **8 phát hiện từ subagent kiểm toán độc lập (`research`):**
   - Chặn đi xuyên vách bên dốc `30°`/`150°` ở tầng 0 Đêm 3 (`src/sim/maps.py`).
   - Ràng buộc Gió Lạc chỉ cướp khi `state == "chase"` và `carried > 0` (`src/sim/engine.py`).
   - Bắt `ValueError`/`RecursionError` của Python 3.13 khi JSON có số nguyên `>4300` chữ số để trả đúng exit code `2` (`src/sim/validation.py`).
   - Ngăn Bóng Mực đang bị kẹt trong vùng an toàn gần Tháp chuông gây sát thương sau khi hết `safe_push_ticks`, đồng bộ cập nhật `shade.y` theo địa hình khi bị đẩy/choáng/lùi, hủy `safe_push_ticks` khi bị pulse, lọc độ cao tầng khi rớt đom đóm, sắp xếp ID tự nhiên (`S2` trước `S10`), và tôn trọng `tuning.fall_enabled`/`shade_speed`.

## 3. Việc cần làm trước khi gắn tag nộp bài
- Điền MSSV & họ tên vào `"team"` trong `game.contract.json`.
- Trỏ `origin` tới repo GitHub Public cá nhân, push lịch sử và gắn đủ `phase-1`, `phase-2`.
