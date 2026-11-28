# GĐ10: benchmark toàn bộ 35 đợt dữ liệu dunnhumby trên Azure

Đo ngày 26–27/11/2026.

## 1. Khối lượng

| Mục | Giá trị |
|---|---:|
| Số đợt | 35, cả 35 PASS (gồm đối soát PostgreSQL với tệp nguồn) |
| Số dòng giao dịch | 34 802 918 |
| Dung lượng JSON Lines đã xử lý | 20 488 590 148 byte (19,08 GiB) |
| Dung lượng CSV gốc của bộ dữ liệu | 4 966 475 591 byte (4,97 GB; 4,63 GiB) |

Ngưỡng 4 GB của đề tài tính theo CSV gốc. JSON Lines lớn hơn do định dạng.

## 2. Cấu hình

VM `Standard_D4as_v4` (4 vCPU, 16 GB) và Azure Database for PostgreSQL Flexible Server `Standard_D2ds_v4`, East Asia. TaskManager 3 GB, parallelism 1, lô ghi JDBC 2000 dòng, idle-timeout 10 phút. Chế độ bounded: Producer gửi hết một đợt vào Kafka, sau đó Flink xử lý và ghi PostgreSQL.

## 3. Thời gian chạy (cộng thời gian của 35 đợt)

| Phần | Tổng thời gian | Trung vị mỗi đợt |
|---|---:|---:|
| **Đầu-cuối: từ lúc bắt đầu gửi đến khi Flink xử lý xong** (`end_to_end_s`) | **47 546 giây (13 giờ 12 phút 26 giây)** | 1 396 giây |
| Trong đó: bước Producer (`publish_wall_s`, gồm kiểm tra dữ liệu đầu vào và gửi) | 28 987 giây (8 giờ 03 phút 07 giây) | 839 giây |
| Riêng thời gian gửi vào Kafka (`publish_send_s`, nằm trong bước Producer) | 13 286 giây (3 giờ 41 phút 26 giây) | 391 giây |
| Trong đó: job Flink (`flink_job_s`) | 18 015 giây (5 giờ 00 phút 15 giây) | 534 giây |
| Đối soát, tính riêng (`reconcile_s`) | 1 328 giây (22 phút 08 giây) | 39 giây |

- Đây là tổng thời gian đo của từng đợt, không gồm thời gian chuẩn bị giữa các đợt và thời gian đo độ trễ truy vấn.
- Thời gian đầu-cuối của một đợt có thể nhỏ hơn tổng `publish_wall_s + flink_job_s + reconcile_s` vì nó không gồm đối soát.
- Không gồm thời gian tiền xử lý CSV thành JSON Lines.

## 4. Thông lượng

| Số đo | Tính trên toàn bộ (tổng dòng / tổng thời gian) | Trung vị theo đợt | Thấp nhất – cao nhất |
|---|---:|---:|---:|
| Gửi vào Kafka (dòng/giây) | 2 619 | 2 555 | 2 513 – 2 800 |
| Gửi vào Kafka (MB/giây) | | 1,50 | 1,48 – 1,65 |
| Job Flink, gồm ghi PostgreSQL (dòng/giây) | 1 932 | 1 873 | 1 800 – 2 194 |
| Job Flink (MB/giây) | | 1,10 | 1,06 – 1,29 |

MB = 10^6 byte JSON Lines. Đợt 35 có 802 918 dòng, các đợt khác 1 000 000 dòng.

## 5. Độ trễ truy vấn PostgreSQL

Sau mỗi đợt, mỗi truy vấn chạy 30 lần trên kết quả của đợt đó (bỏ lần làm nóng). Bảng ghi trung vị và khoảng giá trị qua 35 đợt, đơn vị ms.

| Truy vấn | p50: trung vị (thấp nhất – cao nhất) | p95: trung vị (thấp nhất – cao nhất) |
|---|---:|---:|
| `store_totals` | 1,8 (1,5 – 2,2) | 2,7 (1,9 – 7,8) |
| `minute_window_1d` | 3,6 (3,4 – 9,3) | 4,4 (3,8 – 12,2) |
| `revenue_by_store` | 11,5 (9,9 – 17,6) | 17,0 (11,0 – 45,6) |
| `top_products` | 576 (259 – 883) | 627 (275 – 1 010) |

`top_products` dao động lớn giữa các đợt. Nguyên nhân chưa được kiểm chứng.

## 6. Tài nguyên (35 đợt, lấy mẫu mỗi 5 giây; trung bình / đỉnh)

CPU của container: 100% tương đương một vCPU. CPU toàn máy: 100% tương đương cả 4 vCPU. RAM tính theo GiB.

| Số đo | Giai đoạn gửi | Giai đoạn Flink |
|---|---:|---:|
| CPU toàn máy | 32% / 100% | 49% / 92% |
| RAM toàn máy (tổng 15,61 GiB) | 4,44 / 4,92 | 5,01 / 5,43 |
| CPU TaskManager | 0,6% / 15% | 156% / 381% |
| RAM TaskManager | 2,37 / 2,58 | 2,55 / 2,65 |
| CPU JobManager | 0,6% / 10% | 10% / 332% |
| RAM JobManager | 0,46 / 0,53 | 0,83 / 0,92 |
| CPU Kafka | 32% / 235% | 29% / 218% |
| RAM Kafka | 0,58 / 0,75 | 0,59 / 0,77 |
| Đĩa đã dùng, đỉnh | 38,25 | 38,91 |

Các container tạm dùng để chạy `psql` không được đưa vào bảng.

## 7. Giới hạn

- Một VM, một broker Kafka, parallelism 1.
- Tốc độ Flink gồm cả ghi PostgreSQL qua mạng, không tách riêng tốc độ ghi cơ sở dữ liệu.
- Chế độ bounded đo thông lượng, không phải độ trễ realtime.
- Dữ liệu đọc từ tệp trên đĩa VM, không đọc từ Blob Storage.

## 8. Tệp trong thư mục

| Tệp | Nội dung |
|---|---|
| `10-throughput-runs.csv` | Kết quả từng đợt, mỗi đợt một dòng |
| `10-volume-summary.csv` | Số dòng và byte cộng dồn, dựng lại từ `10-throughput-runs.csv` |
| `10-query-latency.csv` | Độ trễ truy vấn của từng đợt |
| `10-resource-summary.csv` | Tài nguyên theo đợt và giai đoạn, tính từ mẫu thô |
| `10-benchmark-log.txt` | Các dòng nhật ký của 35 đợt |

Mỗi đợt dùng một lượt đo; với đợt 1 là lượt đầu. Ba lượt đo lặp của đợt 1 phục vụ so sánh local–cloud nằm ở `../10-local-vs-cloud.md`. Mẫu tài nguyên thô lưu ngoài Git ở `reports/runtime/from_vm/final/`.
