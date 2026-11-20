# Phase 2 Specification — TICKET-02: "Ba hòn đảo" (Contract v1.1)

## 1. Thay đổi so với Phase 1 (Diff Constants & Rules)

| Hạng mục | Phase 1 (v1.0 tự chọn) | Phase 2 (v1.1 chuẩn hóa) | Ghi chú ảnh hưởng |
|---|---|---|---|
| `contract_version` | `"1.0"` | `"1.1"` | Thêm `dash_*`, `night2_duration_s`, `night3_duration_s` |
| `player_speed` | `8.0 m/s` | `6.0 m/s` | Cập nhật toàn bộ tính toán thời gian di chuyển trong test |
| `jump` | `7.5 m/s` | `7.0 m/s` | Trọng lực giữ nguyên `-20 m/s²`, chỉ nhảy khi `grounded` |
| `dash` | Chưa có | `14.0 m/s`, `0.2 s` (`12` tick), hồi `1.5 s` (`90` tick) | Không bất tử khi lướt; giữ độ cao Y khi lướt trên không |
| `lantern_cost` | `5` | `10` | Cập nhật các kịch bản nạp đèn từ 5 -> 10 đom đóm |
| `pickup_radius` | `2.0 m` | `1.0 m` (+ chênh cao `<= 1.5 m`) | Nhặt đòi hỏi cả XZ `<= 1.0 m` và `|py - my| <= 1.5 m` |
| `interact_radius` | `3.0 m` | `2.0 m` | Giảm bán kính tương tác đèn |
| `pulse` | `cost=2, r=8m, stun=3s, push=6m, cd=4s` | `cost=3, r=5m (3D từ py+0.8), stun=2s (120t), push=4m (15t), cd=3s` | Đo khoảng cách 3D từ tâm `(px, py+0.8, pz)` tới tâm Bóng Mực |
| `safe_radius` | `5.0 m` (đẩy tức thì) | `6.0 m` (đẩy Bóng Mực bên trong ra mép tối đa `30` tick, không sát thương khi bị đẩy) | Bóng Mực ở ngoài bị chặn ở mép `6.0 m` |
| `shade` | `4.5 m/s`, `hit=1.2m`, spawn `t=0` | `4.0 m/s` (Đêm 3: `4.5 m/s`), `hit=1.0m` & `|dy|<=1.5m`, phát hiện `12m`/bỏ `18m`, sinh 2 con tại `t=300` | Tên trạng thái bắt buộc: `spawning`, `wander`, `chase`, `recoil`, `stunned` |
| `player_hit` | Mất đom đóm vào sương | Rơi `floor(carried/2)` ra vành `1.5–2.5m` (TTL `480` tick, nhặt lại từ tick sau); bóng lùi `2m/60t` | Bóng không gây hit khi Mây bất tử hoặc đang bị đẩy safe-zone |
| `fall_enabled` | `false` (chặn mép `45m`) | `true` (`Y < -10`: `-1` Ngọn Lửa, mất hết đom đóm, chờ `60` tick, hồi sinh điểm xuất phát + bất tử `90` tick) | Mất hết Ngọn Lửa thua ngay không hồi sinh |
| `score` | `per_mote=10, per_lantern=200, per_stun=50, per_flame_left=100` | **Nhặt đom đóm +0**, **nạp đèn +10/đom đóm**, đèn `+100`, stun `+5`, `per_second_left=2`, `per_flame_left=50` | Đổi quy tắc: điểm cộng lúc nạp đèn thay vì lúc nhặt |
| Bản đồ Đêm 1 | `r = 45m`, tọa độ đèn 3 chữ số | `r = 40m` (rơi ngoài mép), đèn làm tròn 1 chữ số (`23.8, 7.7, 14.7, 20.2`), 24 điểm mote, 12 điểm shade | Tuân thủ tọa độ chuẩn Phần 2 |

### Lý do cập nhật các test Phase 1
- `tests/scenarios/pickup_and_deposit_win.*` & `tests/test_sim_unit.py`: Cập nhật lại số lượng đom đóm (`10`), tốc độ `6.0 m/s`, bán kính `1.0m`/`2.0m`, và công thức điểm mới (`+10/đom đóm nạp + 100/đèn + 50/ngọn lửa + 2/giây`).
- `tests/scenarios/pulse_and_safe_radius.*`: Cập nhật khoảng cách pulse 3D `<= 5.0m`, đẩy lùi `4m` trong `15` tick, choáng `120` tick, và vùng an toàn `6.0m`.
- `tests/scenarios/shade_hit_and_loss.*`: Cập nhật khoảng cách chạm `1.0m`, `random_shades: false` đặt bóng gần và kiểm tra đom đóm rơi dạng `dropped` có `ttl_s`.

---

## 2. Giả định chi tiết cho các điểm bổ sung ở Phase 2

1. **Vị trí xuất phát Đêm 2 & Đêm 3:**
   - Đêm 2 (Đảo Cau): xuất phát `(0, 0, 0)`, hướng `+Z`.
   - Đêm 3 (Đảo Chuông): xuất phát `(0, 0, -10)` trên tầng 0 (vì `(0, 0, 0)` nằm trong Tháp chuông bán kính `2m` trên tầng 2 `Y=6`), hướng `+Z`.
2. **Tháp chuông & Vách tầng Đêm 3:**
   - Tháp chuông tại `(0, z=0)` là hình trụ đặc bán kính `2.0m` từ tầng 2 (`Y=6`) lên `Y=14` (và chắn phần lõi từ `Y=0..14` trong bán kính `2m` vì tầng 2 đặc từ tâm ra `r=8m` và cao `Y=6`).
   - Vách đứng của tầng 1 (`r ∈ [12, 24], z > 0, Y=3`) và tầng 2 (`r <= 8, Y=6`): nhân vật và Bóng Mực không đi xuyên vách nếu mặt đất đích cao hơn vị trí chân hiện tại `> 0.55m`. Khi bước từ trên tầng xuống mép ngoài (hoặc ở bệ dốc `30°`/`150°`), chiều cao bề mặt thay đổi mượt theo dốc hoặc rơi theo trọng lực.
3. **Bục nhảy (Launch Pad):**
   - Đêm 2: `(20, 0, 18)` phóng hướng thẳng về tâm đảo B `(70, 0)` với vận tốc ngang `24 m/s`, `vy = 14 m/s`. `(50, 0, -18)` phóng hướng thẳng về tâm đảo A `(0, 0)` với vận tốc ngang `24 m/s`, `vy = 14 m/s`.
   - Đêm 3: `(0, 3, 13)` phóng với `vx = 0, vy = 12 m/s, vz = -8 m/s`.
   - Khi đang phóng, phím `WASD` không ghi đè vận tốc ngang cho tới khi chạm đất; người chơi **vẫn có thể nhấn Lướt (`dash`)** để hủy trạng thái phóng và lướt 0.2s như mô tả.
4. **Trạng thái Bóng Mực (`spawning | wander | chase | recoil | stunned`):**
   - Bóng Mực sinh theo lịch bắt đầu ở trạng thái `spawning` trong `30` tick (`0.5s`) rồi chuyển `wander`/`chase`. Bóng đặt sẵn qua `--scenario` mặc định vào ngay `chase` (nếu trong `12m`) hoặc `wander` (ngoài `12m`), trừ khi `scenario` chỉ định rõ `state` và `state_ticks_left`.
   - Khi `wander`, Bóng Mực đi tuần quanh vị trí sinh theo góc quay từ `SeededRNG` với tốc độ `2.0 m/s` (nhằm vào điểm tuần thuộc mặt phẳng đảo, tránh vùng an toàn `6m` của đèn sáng). Vào phạm vi XZ `<= 12m` và thấy Mây (không respawning) -> `chase`; vượt quá `18m` -> quay về `wander`.
5. **Gió mạnh (Đêm 3):**
   - Khi `wind_enabled` bật (mặc định `true` ở Đêm 3): chu kỳ `1800` tick (`30s`).
   - Từ tick `1680..1799` trong chu kỳ (`2s` trước gió): `wind_warning = true` (lá bay + âm thanh cảnh báo trên client), `wind.active = false`.
   - Từ `sim_tick % 1800` thuộc `[0, 300)` khi `sim_tick >= 1800` (tức mỗi mốc `30s, 60s, ...` kéo dài `5s = 300` tick): chọn ngẫu nhiên góc `dir_deg` từ `SeededRNG`, `wind.active = true`, đẩy Mây thêm `2.0 m/s` theo `(cos(dir), sin(dir))`.
6. **Gió Lạc & Bùa Gió:**
   - Gió Lạc bay lượn không bị địa hình tầng hoặc vùng an toàn của đèn chặn; vị trí xuất hiện tại tick `1200, 2400, ...` lấy từ các điểm sương xác định quanh đảo bằng `SeededRNG`, độ cao `Y = 1.2m` (hoặc trên tầng nếu gần tầng cao).
   - Bùa Gió: `C1` ở Đêm 2 tại `(35, 0, 0)`; `C1, C2` ở Đêm 3 tại `(30, 0, 25)` và `(-30, 0, 25)`.
7. **Sự kiện `night_start` & Khởi động:**
   - Snapshot tick `0` là trạng thái ngay sau dựng màn/scenario (`sim_tick = 0`). Ở bước `sim_tick = 1`, phát `night_start {"night": self.night}`.

---

## 3. Acceptance Criteria cho từng mục Phần 3

| Tính năng | Tiêu chí nghiệm thu kiểm chứng được (Acceptance Criteria) |
|---|---|
| **AC-1: Di chuyển, Nhảy, Lướt (`dash`)** | Nhấn `dash` khi không hồi chiêu lướt đúng `14 m/s` trong `12` tick (`2.8 m`), giữ nguyên `player.y` nếu đang nhảy trên không, đứng yên thì lướt theo hướng mặt, phát `dash {}`, hồi chiêu `90` tick từ lúc bắt đầu. |
| **AC-2: Rơi khỏi đảo & Hồi sinh** | Đi qua mép `r > 40m` ở Đêm 1 rơi xuống `Y < -10`: trừ `1` Ngọn Lửa (kể cả khi đang `invuln`), mất hết đom đóm (`lost` trong `player_hit`), chờ `60` tick, hồi sinh tại điểm xuất phát với `90` tick bất tử; nếu Ngọn Lửa về `0` thua ngay (`no_flames`). |
| **AC-3: Gió Lạc (Drifters)** | Sinh ở tick `1200` (Đêm 2/3, max `2`); `idle` `2 m/s` -> `chase` `7 m/s` khi `carried >= 5` & `dist_xz <= 15m`; chạm `<= 1.2m` cướp `min(3, carried)` (bỏ qua `invuln` & `safe_radius`) -> `drifter_steal`, chạy trốn `7 m/s` trong `240` tick rồi `removed`. Trúng Tỏa Sáng khi `chase` -> `flee` không cướp; khi `flee` có đồ -> thả lại đom đóm rơi (`drifter_drop`) rồi biến mất sau `120` tick. |
| **AC-4: Bùa Gió (Charms)** | Đứng vào vị trí bùa khi `available` -> phát `charm_picked`, hiệu lực `600` tick: tốc độ chạy tăng lên `7.2 m/s`, Lướt không cần chờ hồi chiêu (vẫn cần nhấn lại sau khi kết thúc `12` tick lướt). Bùa hồi lại sau `2700` tick. |
| **AC-5: Đảo Cau (Đêm 2) & Đảo Chuông (Đêm 3)** | Đêm 2 đi qua cầu tre `x∈[26,44], z∈[-2,2]` an toàn và chạm bục nhảy `(20,0,18)` bay sang Đảo B `(70,0)`. Đêm 3 leo dốc `30°`/`150°` lên tầng 1 (`Y=3`), vách đứng chặn trèo ngang, bục `(0,3,13)` đáp lên tầng 2 (`Y=6`), Tháp chuông `r=2` chặn đi xuyên tâm, gió mạnh đẩy `2 m/s` mỗi `30s` trong `5s`. |
| **AC-6: Chuỗi 3 Đêm & Bình Minh** | Menu chính -> Giới thiệu Đêm (lời Ông Đăng) -> chơi qua Đêm 1 -> 2 -> 3, cộng dồn điểm các Đêm thắng và hiện màn hình Bình Minh sau Đêm 3; thua cho phép chơi lại Đêm đó. |
| **AC-7: Tạm dừng & Cài đặt** | Nhấn `Esc`/`P` chuyển `state="paused"`, `sim_tick`/timer/TTL đứng yên trong khi `tick` vẫn tăng, hiện menu 4 nút; Âm lượng & Độ nhạy chuột lưu qua `localStorage` giữa các lần tải trang. |
| **AC-8: Bảng màu, Ánh sáng, HUD & Âm thanh** | Màu entity & môi trường khớp bảng Hex chuẩn (`±10%`); cường độ `ambient = 0.15 + 0.55*(đèn sáng/tổng)`; đồng hồ đỏ + nhấp nháy `<= 30s`; thanh 10 ô đom đóm, hồi chiêu Lướt/Tỏa Sáng, nhắc `[E]`, mũi tên chỉ đèn ngoài màn hình; Web Audio đủ nhạc đêm & 10 loại SFX. |
| **AC-9: Hiệu năng** | Headless Night 3 `21,600` tick hoàn thành trong `<= 30s`; game 3D tại `1280x720` đạt trung bình `>= 30 FPS`. |
