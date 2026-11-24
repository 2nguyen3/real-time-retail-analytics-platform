# GĐ11: độ trễ theo region, DB cố định (24/11/2026)

Trạng thái: **R10 có số đo, chờ rà soát và ảnh Portal**. C5 (throughput ghi qua region xa) chưa thực hiện.

## 1. Thiết lập

| Hạng mục | Giá trị |
|----------|---------|
| PostgreSQL | Azure Database for PostgreSQL Flexible Server, B1ms, **cố định ở East Asia** (không đổi giữa hai phép đo) |
| VM1 | `vm-retail-ea-01`, East Asia (cùng vùng với DB), Standard_B2as_v2, Ubuntu 24.04 |
| VM2 | `vm-retail-ind-01`, **India South Central**, Standard_B2as_v2, Ubuntu 24.04 (cùng SKU với VM1) |
| Công cụ | `tests/benchmark/run_stage11.py`, cùng mã, cùng lệnh trên hai VM |
| Dữ liệu truy vấn | cùng `run_id` đã nạp trong PostgreSQL (lượt `repeat` 1 triệu dòng của GĐ10) |
| Số lượt | 3 lượt mỗi VM; mỗi lượt 50 lần mở kết nối TCP và 30 lần mỗi truy vấn (bỏ lần đầu) |
| Thời điểm đo | 24/11/2026 từ 04:26 đến 04:29 UTC, các lượt chạy liên tiếp |

Lý do chọn India South Central: subscription có chính sách chỉ cho triển khai ở East Asia, Japan East, Malaysia West, India South Central, UAE North (East US và West Europe bị chặn, xem `docs/plan/stage_11_region_plan.md`). UAE North không có SKU phù hợp. India South Central là vùng xa nhất còn dùng được và có đúng SKU của VM1.

## 2. Kết quả (khoảng giá trị giữa ba lượt, mili giây)

| Phép đo | VM1 East Asia (cùng vùng DB) | VM2 India South Central |
|---------|------------------------------|-------------------------|
| RTT: mở kết nối TCP (p50) | 4,3–4,5 | **77,1–77,8** |
| RTT: mở kết nối TCP (p95) | 8,4–9,0 | 79,0–80,4 |
| `SELECT 1` (p50 / p95) | 0,8–1,0 / 1,4–1,7 | **74,7–74,8** / 75,1–77,3 |
| `store_totals` (p50 / p95) | 1,0–1,1 / 1,2–2,0 | 75,0–75,1 / 75,5–77,4 |
| `top_products` (p50 / p95) | 1,3–1,6 / 2,6–4,0 | 75,6–77,5 / 76,1–78,1 |
| `minute_window_1d` (p50 / p95) | 3,2–3,5 / 4,1–7,7 | 112,8–116,5 / 113,8–117,0 |
| `revenue_by_store` (p50 / p95) | 318,1–320,4 / 343,9–496,6 | 372,1–388,1 / 407,1–416,4 |

Số đo từng lượt: `11-region-latency-eastasia.csv`, `11-region-latency-indiasouthcentral.csv`; nhật ký: `11-benchmark-log-*.txt`.

## 3. Cách đọc

- Từ vùng khác, mỗi lần truy vấn đều cộng thêm khoảng một RTT. `SELECT 1` và các truy vấn nhỏ (`store_totals`, `top_products`) tăng từ khoảng 1 ms lên khoảng 75 ms, gần 70–75 lần.
- `minute_window_1d` trả về nhiều dòng nên cộng thêm khoảng 1,5 RTT (3,4 ms lên khoảng 114 ms): kết quả lớn cần nhiều gói trả về qua đường dài.
- `revenue_by_store` chủ yếu là thời gian xử lý ở DB (khoảng 320 ms), nên chênh lệch giữa hai vùng nhỏ hơn về tỷ lệ (khoảng +60 ms).
- RTT mở kết nối TCP của VM1 (khoảng 4,4 ms) lớn hơn `SELECT 1` trong phiên đã mở (khoảng 1 ms) vì bao gồm bắt tay kết nối, trong khi phiên SQL đã mở sẵn.
- Ý nghĩa cho hệ thống: ứng dụng nên đặt gần DB, và gộp truy vấn để giảm số vòng đi về khi chạy từ vùng xa.

## 4. Giới hạn

- Ba lượt chạy liên tiếp trong khoảng 3 phút, chỉ một thời điểm; chưa đo ở nhiều giờ khác nhau trong ngày.
- Mới đo một vùng thứ hai (India South Central). Chưa có vùng gần hơn (Japan East, Malaysia West) để vẽ đường cong khoảng cách.
- Chưa đo throughput ghi của Flink từ vùng xa (C5, tùy chọn).
- Giá trị tuyệt đối phụ thuộc đường truyền Azure tại thời điểm đo.
