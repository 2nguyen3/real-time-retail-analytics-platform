# GĐ10: so sánh local và Azure trên dữ liệu dunnhumby (26/11/2026)

Workload: đợt 1 (`sor10_c01`, 1 000 000 dòng, 588 788 829 byte, SHA-256 hai bên khớp), 3 lượt mỗi môi trường, cơ sở dữ liệu được xóa sạch trước khi đo, cùng cấu hình Flink (TaskManager 3 GB, parallelism 1, lô JDBC 2000, idle-timeout 10 phút). Cả 6 lượt đối soát PASS.

| Cấu hình | Local | Azure (East Asia) |
|---|---|---|
| Máy | Ryzen 7 8745HS, 8 nhân, 13,8 GB RAM, Windows 11; Docker khoảng 6,7 GiB | VM Standard_D4as_v4, 4 vCPU, 16 GB |
| PostgreSQL | Container cùng máy | Flexible Server Standard_D2ds_v4, qua mạng |

## 1. Tốc độ (dòng/giây)

| Lượt | Azure gửi | Azure Flink | Local gửi | Local Flink |
|---|---:|---:|---:|---:|
| 1 | 2 755 | 2 074 | 3 557 | 2 879 |
| 2 | 2 758 | 2 050 | 3 348 | 2 789 |
| 3 | 2 766 | 2 051 | 3 843 | 2 767 |
| Trung vị | 2 758 | 2 051 | 3 557 | 2 789 |

Tốc độ Flink đã gồm ghi PostgreSQL.

## 2. Độ trễ truy vấn p50 / p95 (ms), 30 lần mỗi truy vấn mỗi lượt

| Truy vấn | Azure lượt 1 | Azure lượt 2 | Azure lượt 3 | Local lượt 1 | Local lượt 2 | Local lượt 3 |
|---|---|---|---|---|---|---|
| `store_totals` | 1,7 / 2,1 | 2,0 / 3,6 | 2,1 / 6,5 | 0,6 / 0,9 | 0,6 / 0,8 | 0,9 / 1,1 |
| `minute_window_1d` | 3,6 / 4,1 | 3,5 / 4,1 | 4,0 / 5,8 | 2,3 / 2,7 | 2,5 / 3,3 | 2,4 / 3,3 |
| `revenue_by_store` | 9,9 / 12,5 | 10,2 / 18,0 | 10,9 / 15,2 | 6,0 / 8,6 | 7,6 / 12,5 | 7,0 / 9,2 |
| `top_products` | 259 / 275 | 318 / 340 | 284 / 299 | 76 / 94 | 115 / 136 | 122 / 163 |

## 3. Tài nguyên trong giai đoạn Flink (trung bình / đỉnh, gộp 3 lượt)

| Số đo | Azure | Local |
|---|---|---|
| CPU toàn máy | 49% / 86% | Không đo được trên Windows |
| RAM toàn máy | 4,76 / 5,21 GiB | Không đo được trên Windows |
| CPU TaskManager (100% = 1 nhân) | 160% / 379% | 219% / 895% |
| RAM TaskManager | 2,42 / 2,59 GiB | 2,51 / 2,68 GiB |

## 4. Nhận xét và giới hạn

- Với hai cấu hình này, local nhanh hơn (trung vị: gửi khoảng 29%, Flink khoảng 36%) và truy vấn có độ trễ thấp hơn. Azure ổn định hơn (ba lượt chênh khoảng 1%).
- Hai bên khác phần cứng và vị trí PostgreSQL, nên không kết luận cloud luôn chậm hơn.
- CPU toàn máy của VM trung bình khoảng 49%, nên tổng CPU không phải điểm nghẽn. Parallelism 1 và ghi PostgreSQL qua mạng là nguyên nhân có thể, chưa kiểm chứng riêng.
- So sánh trên một đợt (khoảng 0,13 GiB CSV gốc). Quy mô đầy đủ chỉ chạy trên Azure: đã xong đợt 1–5 (`azure/10-throughput-runs.csv`), tạm dừng, còn đợt 6–35.

## 5. Tệp nguồn

`azure/` và `local/`: nhật ký, throughput, độ trễ, tóm tắt tài nguyên. Mẫu tài nguyên thô của Azure lưu ngoài Git ở `reports/runtime/part9/azure_partial/`.
