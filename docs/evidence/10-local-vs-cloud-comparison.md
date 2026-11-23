# GĐ10: so sánh local và cloud, cùng workload (22–23/11/2026)

Workload: chunk `bench10_c01` (1 000 000 dòng, 447 205 234 byte, synthetic, seed 2026). Tệp sinh lại trên máy local trùng tuyệt đối số byte với tệp trên Azure. Mỗi môi trường chạy ba lượt `repeat` bằng cùng một lệnh, cùng cấu hình Flink, nhãn `official`. Các tệp nguồn: `10-cloud-repeat-*` và `local-repeat/`.

## 1. Cấu hình hai bên

| Hạng mục | Local | Cloud (Azure) |
|----------|-------|---------------|
| Máy | AMD Ryzen 7 8745HS, 8 nhân / 16 luồng, 13,8 GB RAM, Windows 11 | VM Standard B2as_v2: 2 vCPU, 8 GB RAM, đĩa 64 GB (loại burstable) |
| Docker | Docker Desktop, được cấp 16 CPU và khoảng 6,7 GiB RAM | Docker trên VM, dùng toàn bộ tài nguyên VM |
| Kafka, Flink | Cùng Docker Compose, Flink 2.2.1, TaskManager 3 GB, parallelism 1 | Giống |
| PostgreSQL | 17-alpine trong container cùng máy | Azure Database for PostgreSQL Flexible Server, B1ms, 32 GiB (dịch vụ quản lý, truy vấn qua mạng) |
| Biến cấu hình | `JDBC_FLUSH_MAX_ROWS=2000`, `FLINK_SOURCE_IDLE_TIMEOUT="10 min"` | Giống |

## 2. Throughput ba lượt (dòng/giây)

| Lượt | Local publish | Local Flink | Cloud publish | Cloud Flink |
|------|--------------:|------------:|--------------:|------------:|
| 1 | 1 352 | 1 328 | 2 422 | 2 131 |
| 2 | 2 558 | 3 583 | 2 447 | 2 000 |
| 3 | 4 274 | 3 731 | 2 415 | 2 047 |
| Trung bình | 2 728 | 2 881 | 2 428 | 2 059 |
| Trung vị | 2 558 | 3 583 | 2 422 | 2 047 |

- Cloud ổn định giữa ba lượt (chênh nhau dưới 7%).
- Local tăng dần theo lượt (publish gấp 3 lần, Flink gấp 2,8 lần từ lượt 1 đến lượt 3). Không đo được máy local bận gì ở lượt 1 (bộ lấy mẫu trên Windows chỉ ghi được disk của máy chủ), nên chưa xác định nguyên nhân. Khả năng cao là khởi động nguội (Docker, cache) và hoạt động nền của máy. Vì độ phân tán lớn, không dùng một con số local duy nhất để kết luận; báo cáo nên nêu cả ba lượt.
- Cloud được đo khi VM còn credit CPU (burst). Khi credit cạn (chạy dài, xem `10-cloud-volume-report.md`), cloud giảm còn khoảng 725 dòng/giây Flink.

## 3. Độ trễ truy vấn p50 / p95 (ms)

| Truy vấn | Local (3 lượt) | Cloud (3 lượt) |
|----------|----------------|----------------|
| `revenue_by_store` | 45–112 / 52–144 | 313–359 / 358–480 |
| `top_products` | 0,4–1,0 / 0,7–1,7 | 1,4–2,4 / 1,9–6,8 |
| `minute_window_1d` | 2,2–4,3 / 2,7–6,1 | 3,2–4,0 / 4,5–10,5 |
| `store_totals` | 0,2–0,4 / 0,3–0,6 | 0,9–1,3 / 1,3–1,7 |

Local nhanh hơn ở độ trễ truy vấn, một phần vì PostgreSQL chạy cùng máy, không qua mạng, và cloud dùng cấp B1ms nhỏ. Cần tách hai yếu tố này nếu muốn kết luận về chi phí.

## 4. Tài nguyên TaskManager Flink (trung bình / đỉnh)

| Lượt | Local CPU TaskManager | Local RAM TaskManager | Cloud CPU máy (giai đoạn Flink) |
|------|----------------------|-----------------------|----------------------------------|
| 1 | 174% / 659% | 2,13 / 2,53 GiB | xem `10-cloud-repeat-resource-summary.csv` |
| 2 | 181% / 468% | 2,51 / 2,58 GiB | |
| 3 | 170% / 372% | 2,57 / 2,61 GiB | |

CPU container tính theo nhân (100% là một nhân), nên không so trực tiếp với phần trăm CPU máy của cloud.

## 5. Kết luận và giới hạn

- Không kết luận "local nhanh hơn cloud" hay ngược lại: hai môi trường khác cấu hình (máy 8 nhân so với 2 vCPU burstable, PostgreSQL trong container so với dịch vụ quản lý), local có độ phân tán lớn, và cloud phụ thuộc credit CPU.
- Điều chắc chắn: cùng workload 1 triệu dòng chạy PASS đối soát ở cả hai môi trường, ba lượt mỗi bên.
- Dữ liệu là synthetic. Việc giảng viên chấp nhận mốc >4 GB bằng dữ liệu synthetic chưa được xác nhận bằng văn bản.
