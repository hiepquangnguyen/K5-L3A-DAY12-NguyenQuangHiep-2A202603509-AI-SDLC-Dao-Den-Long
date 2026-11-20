# Đánh giá Phase 3 — TICKET-03 CHANGE REQUEST "Đèn cạn dầu" (Contract v1.2)

## 1. Mục tiêu & Chuyển đổi kiến trúc
Phase 3 thực hiện yêu cầu thay đổi cốt lõi (`Change Request`) của khách hàng: thay thế vòng lặp thắng sớm `all_lit` bằng cơ chế giữ đảo sáng đến bình minh (`dawn_survived`) kèm nhiên liệu đèn hữu hạn, Bóng Mực hút dầu (`drain`), sức chứa đom đóm tăng dần (`10..20`), bảng điểm mới và chế độ hỗ trợ người mù màu.

Quyết định thiết kế mô hình trạng thái đèn và luật thắng được ghi chi tiết tại [ADR-001-lantern-fuel-and-dawn-win.md](ADR-001-lantern-fuel-and-dawn-win.md), và toàn bộ thay đổi phá vỡ tương thích (breaking changes) + lý do cập nhật test được tổng hợp tại [CHANGELOG.md](../../CHANGELOG.md).

## 2. Kiểm tra Định nghĩa Hoàn thành (DoD)
- **Bằng chứng đầy đủ & không sửa tay:** Thư mục `docs/proof/phase-3/` lưu nguyên bản kết quả test (`35/35 OK`), hash SHA-256 tính tất định, benchmark Đêm 3 `18,000` tick (`4.033s` / `3.906s <= 30s`) + stress `21,600` tick (`4.115s <= 30s`), hai file JSONL kịch bản `drain/refuel` và `dawn_win`, cùng ảnh chụp `1280×720` chế độ thường và chế độ mù màu (chi tiết trong [EVIDENCE.md](../proof/phase-3/EVIDENCE.md)).
- **Ghi chú quyết định thiết kế (ADR):** Đã viết [ADR-001](ADR-001-lantern-fuel-and-dawn-win.md) giải trình mô hình `fuel_60` số nguyên `1/60` tránh sai số IEEE-754 tại các mốc `30.0` và `0.0`, máy trạng thái `ever_lit/relit_count/relight_cost`, và thứ tự Bước 2 -> Bước 11.
- **Cập nhật test có lý do, không skip âm thầm:**
  - `tests/test_headless_contract.py` (`test_pickup_deposit_no_early_all_lit_win`, `test_snapshot_v1_2_schema_fields`, bổ sung validation v1.2 exit code `2`).
  - `tests/test_sim_unit.py` (`test_partial_deposit_dawn_win_scoring_capacity_and_pulse_miss`).
  - `tests/test_phase2_features.py` (`test_night3_dawn_18000_and_stress_21600_ticks_under_30s_and_deterministic`, `test_audit_regressions_...`).
  - Toàn bộ `35` test trong `tests/` đều chạy thật với `0` test bị skip.
- **Changelog:** Đã lập [CHANGELOG.md](../../CHANGELOG.md) liệt kê đầy đủ breaking changes từ v1.1 lên v1.2.
- **Tương thích ngược luật không bị thay thế:** Toàn bộ test Phase 1–2 về xoay camera, rơi khỏi đảo `Y < -10`, hồi sinh `60` tick, cầu tre, bục nhảy, dốc `30°/150°` Đêm 3, Tháp chuông, Gió mạnh, Gió Lạc, Bùa Gió, Pause đóng băng `sim_tick` đều giữ nguyên và tiếp tục xanh `OK`.

## 3. Kết quả kiểm thử trình duyệt & Rà soát độc lập
- **Kiểm thử trình duyệt `1280×720` (`browser` subagent):** `0` lỗi console, `0` request lỗi trên `http://127.0.0.1:8765/`. Đêm 1 bắt đầu đúng `04:00`, HUD hiển thị `🏮 0 / 5 (cần ≥ 3)` và `0 / 10`, FPS đạt `FPS: 60 (avg 59.7)` ở chế độ thường (`avg 45.4` sau pause/resume ở chế độ mù màu). Bật `"Bảng màu dễ phân biệt"` chuyển `#hud-pulse-cd` sang `#FFFFFF` kèm `⚠` và giữ nguyên qua `page.reload()`.
- **Rà soát độc lập (`research` subagent):** Đạt (**PASS** không có bug chặn), ghi nhận 4 rủi ro/chi tiết nhỏ đã được vá ngay trước commit cuối:
  1. Bổ sung `lantern_fuel_60` trong `ui_state()` (chỉ dùng cho HUD prompt `[E] Châm dầu`, không đụng `snapshot()` headless) để tránh khoảng lệch làm tròn 1 chữ số thập phân ở `99.95%` / `89.95%`.
  2. Chỉnh vệt rách giấy trên đèn tắt ôm khít bề mặt đèn (`r=0.665`, kích thước `0.14×0.34`) sau khi quan sát ảnh chụp thực tế, và giữ màu mắt đúng cho Bóng đang `stunned` khi bật mù màu lúc tạm dừng.
  3. Đồng bộ docstring `v1.2` tại `src/sim/validation.py` và chỉnh chính xác diễn giải trong `ADR-001` (`round(float(fuel) * 60)`, `{lantern_id, relight}`) + `CHANGELOG.md`.
