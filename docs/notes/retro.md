# Project Retrospective — Đảo Đèn Lồng (`Phase 1 → Phase 4 / v1.0.0`)

**Nhóm:** `2A202603509-NguyenQuangHiep` (Nguyễn Quang Hiệp · MSSV `2A202603509`)  
**Phạm vi:** 4 Phase · 4 Test Contracts (`v1.0 → v1.3`) · Phát hành `v1.0.0`

---

## 1. Kiến trúc & Quyết định giữ vững qua cả 4 Phase

1. **Một nguồn chân lý (`src/sim/`) thuần Python stdlib:**
   Tách toàn bộ vật lý, AI, nhiên liệu, đếm tick `60Hz` vào `src/sim/` và giữ `web/` chỉ là lớp dựng hình + nhập liệu giúp cả 4 công cụ — `src.play` (WebSocket 3D), `src.headless` (chấm tự động), `src.soak` (`10` đêm liên tục), và `src.bench` (`create_benchmark`) — chạy trên **cùng một mô phỏng tất định**. Khi Phase 3 đổi luật cốt lõi hoặc Phase 4 thêm chế độ benchmark/bảng xếp hạng, tính tất định SHA-256 của headless không hề bị xê dịch (`39e44585...` ở Đêm 1 và `c5447a10...` ở Đêm 3 khớp y nguyên từ Phase 3 sang Phase 4).
2. **Lưu nhiên liệu bằng số nguyên `1/60` (`fuel_60`):**
   Quyết định ghi ở [ADR-001](ADR-001-lantern-fuel-and-dawn-win.md) loại bỏ hoàn toàn sai số cộng dồn `1/60` kiểu dấu phẩy động tại các ranh giới nhạy cảm (`fuel == 30.0` giữ vùng an toàn, `fuel <= 0` phát `lantern_out`).

## 2. Xử lý Change Request (Phase 3) & Tối ưu Hiệu năng Thực tế (Phase 4)

- **Bài học từ Phase 3 ("Đèn cạn dầu"):**
  Việc yêu cầu khách hàng hủy điều kiện thắng `all_lit` buộc phải rà soát lại mọi test cũ theo nguyên tắc *không xóa hay skip test âm thầm*, mà đối chiếu rõ nguyên nhân trong `CHANGELOG.md` và tách trường `lantern_fuel_60` riêng vào `ui_state()` để HUD `[E]` chính xác mà không làm biến đổi schema JSONL headless.
- **Bài học hiệu năng iGPU thực địa (`bench.json`):**
  Trong Phase 4, khi thử nghiệm 200 Bóng Mực + 100 Đom Đóm + ánh sáng Đêm 1 trên card tích hợp **Intel(R) HD Graphics 630**, pipeline ban đầu dựng mỗi thực thể thành nhiều `THREE.Mesh` riêng kèm JSON snapshot văn bản cho ra `p1_low_fps = 22.5` (không đạt ngưỡng `>= 30`). Hai đợt tối ưu dựa trên đo đạc thật đã giải quyết triệt để:
  1. Gom Bóng Mực và Đom Đóm bằng `THREE.InstancedMesh`, truyền vị trí qua WebSocket nhị phân `Float32Array` (`0x2`), cập nhật ma trận trực tiếp theo dirty-flag thay cho `Object3D.updateMatrix()` mỗi frame.
  2. Hồ sơ chẩn đoán khung hình chậm phát hiện hai nguyên nhân sâu hơn trên Windows: tính năng `CalculateNativeWinOcclusion` của Edge tự hãm `requestAnimationFrame` khi cửa sổ bị che khuất (`p1_low_fps` từng tụt còn `1.8` / `5.2`), và shader PBR `MeshStandardMaterial` kết hợp cập nhật shadow `100+ Hz` gây nghẽn hàng đợi D3D11 (`250–1026 ms`). Sau khi tắt cờ occlusion trong `src/bench.py`, chuyển vật liệu benchmark sang `MeshLambertMaterial`, `precision: 'mediump'`, và cập nhật `BasicShadowMap` đồng bộ đúng `60Hz` khi Bóng Mực di chuyển, hiệu năng thực tế tăng lên **`avg_fps = 142.6`**, **`p1_low_fps = 36.1`**, **`frame_ms_p95 = 12.6 ms`**, **`load_ms = 1862 ms`**.

## 3. Quy trình AI SDLC & Số liệu Qua 4 Phase

| Phase | Contract | Unit & Contract Tests | Tốc độ Đêm 3 Headless | Chứng cứ Bổ sung |
|---|---|---|---|---|
| Phase 1 | `v1.0` | Bộ test Contract `v1.0` | N/A *(chỉ Đêm 1)* | WebGL Đêm 1 + Headless |
| Phase 2 | `v1.1` | `28` tests (`0` skip) | `2.655s` (`18k` ticks) | 3 bản đồ Đêm 1–3, ảnh `1280×720` |
| Phase 3 | `v1.2` | `35` tests (`0` skip) | `4.033s` (`18k`), `4.115s` (`21.6k`) | `ADR-001`, chế độ mù màu, JSONL mẫu |
| Phase 4 | `v1.3` | **`41` tests** (`31.787s`, `0` skip) | `4.908s / 5.304s` (`<= 30s`) | `bench.json` (`142.6` / `36.1`), `soak.json` (`0` crash, `17.4→17.5 MiB`), CI & `v1.0.0` |

- **Điều phát huy tác dụng mạnh nhất:** Kết hợp cổng tự động `.agents/hooks/verify_gate.py` ngay trước mỗi commit, tách subagent `browser` (`flash`) để kiểm chứng giao diện `1280×720` trực quan (bắt được ngay lỗi bố cục hoặc scrollbar) và subagent `research` rà soát độc lập trước release (phát hiện 5 lỗi mức Medium gồm bit `+x` trong ZIP tạo trên Windows, trường `INVALID_HANDLE_VALUE` 64-bit trong `ctypes`, cây tiến trình RSS macOS, ép kiểu `str(None)` ở `POST /api/leaderboard`, và dấu hiệu `OverflowError`).
- **Hạn chế còn tồn tại & Hướng cải thiện tiếp theo:**
  - Chưa có GPU rời hay macOS/Linux vật lý để chạy trực tiếp `src.bench` trên đủ 3 hệ điều hành (một phần RSS đa tiến trình macOS được rà soát qua mã nguồn + CI Linux chạy headless/soak).
  - Trong chế độ **Chữ lớn (`×1.25`)** ở độ phân giải `1280×720`, hộp thoại **Cài đặt** cần cuộn dọc để chạm dòng phím thứ 9 (`Tạm dừng`) và nút lưu; phiên bản kế tiếp có thể chuyển lưới đổi phím sang 3 cột khi kích hoạt `html.large-text`.
