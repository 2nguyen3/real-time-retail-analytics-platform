# R11: tối ưu lưu trữ trên PostgreSQL và tốc độ đọc đến Power BI (28/11/2026)

## Thiết lập

| Mục | Giá trị |
|---|---|
| Biến thay đổi | Cách tổ chức dữ liệu: lưu **từng giao dịch** (trước) hoặc lưu **tổng hợp theo cửa hàng và sản phẩm** (sau) |
| Dữ liệu | Đợt 1 dunnhumby (`sor10_c01.jsonl`): 1 000 000 dòng; bảng tổng hợp tạo từ chính tệp này, 634 404 dòng |
| Cơ sở dữ liệu | Azure Database for PostgreSQL Flexible Server 17, `Standard_D2ds_v4`, East Asia; schema riêng `bench_r11` |
| Ứng dụng đọc | Power BI Desktop trên máy cá nhân, DirectQuery, tài khoản chỉ đọc, kết nối qua mạng |
| Index | Mỗi bảng có khóa chính và index `(run_id, product_id)`. Khóa chính bảng chi tiết: `(run_id, transaction_id)`; bảng tổng hợp: `(run_id, store_id, product_id, currency)` |
| Đồng nhất khi đọc | Bảng chi tiết được đọc qua view `tx_detail_v` có cùng tên cột với bảng tổng hợp (`transaction_count = 1` cho mỗi giao dịch). Power BI dùng cùng truy vấn DAX, chỉ đổi tham số nguồn |
| Mã | `tests/benchmark/r11/` |

## 1. Lưu trữ: dung lượng

`pg_table_size`, `pg_indexes_size`, `pg_total_relation_size` sau khi nạp và `VACUUM (ANALYZE)`. MB = 10^6 byte.

| Số đo | Chi tiết | Tổng hợp | Thay đổi |
|---|---:|---:|---|
| Số dòng | 1 000 000 | 634 404 | giảm 36,6% |
| Bảng | 195,2 MB | 59,6 MB | giảm 69,5% |
| Index | 197,5 MB | 43,6 MB | giảm 77,9% |
| **Tổng** | **392,7 MB** | **103,2 MB** | **giảm 73,7%** |

## 2. Lưu trữ: thời gian ghi vào PostgreSQL

`\copy` từ máy cá nhân vào bảng đã có sẵn index, làm trống bảng trước mỗi lượt, chạy xen kẽ hai bảng.

| Lượt | Chi tiết (giây) | Tổng hợp (giây) |
|---|---:|---:|
| 1 | 59,03 | 6,99 |
| 2 | 61,14 | 6,93 |
| 3 | 57,50 | 7,46 |
| **Trung bình** | **59,22** | **7,13** (ngắn hơn 88,0%) |

Thời gian gồm truyền dữ liệu qua mạng (CSV 171,0 MB so với 27,3 MB) và cập nhật index. Không gồm thời gian tổng hợp dữ liệu, và không phải tốc độ ghi của Flink (Flink ghi bằng JDBC upsert).

## 3. Đọc: PostgreSQL đến Power BI

| Truy vấn | Nội dung |
|---|---|
| Q1 | Tổng số dòng giao dịch, số lượng, doanh thu |
| Q2 | 10 sản phẩm doanh thu cao nhất |
| Q3 | 10 cửa hàng doanh thu cao nhất |

Mỗi cấu hình có 1 lượt làm nóng (không tính) và 3 lượt đo, chạy xen kẽ theo lượt. Sau mỗi lần đổi nguồn, cache của Power BI được xóa. Thời gian lấy từ số đo thực thi truy vấn DAX của engine Power BI Desktop (qua công cụ Power BI MCP), **không gồm thời gian vẽ biểu đồ**.

Thời gian truy vấn tổng (ms):

| Truy vấn | Chi tiết: 3 lượt | **Trung bình** | Tổng hợp: 3 lượt | **Trung bình** | Thay đổi trung bình |
|---|---|---:|---|---:|---|
| Q1 | 666 / 378 / 393 | **479,0** | 369 / 337 / 493 | **399,7** | ngắn hơn 16,6% (xem nhận xét) |
| Q2 | 621 / 546 / 603 | **590,0** | 403 / 410 / 330 | **381,0** | ngắn hơn 35,4% |
| Q3 | 444 / 473 / 444 | **453,7** | 323 / 341 / 311 | **325,0** | ngắn hơn 28,4% |
| Trung bình 9 lượt | | **507,6** | | **368,6** | ngắn hơn 27,4% |

Riêng phần DirectQuery (truy vấn đến PostgreSQL), trung bình: Q1 437,7 → 362,3 ms; Q2 572,0 → 367,7 ms; Q3 441,3 → 311,3 ms. Chi tiết từng lượt ở `r11-powerbi-runs.csv`.

## 4. Kiểm tra đúng

- SQL: Q1, Q2, Q3 trên cả hai nguồn khớp giá trị tính trực tiếp từ tệp nguồn (`r11-sql-check.csv`, `r11-expected-from-source.json`).
- Power BI: Q1 cả hai nguồn trả 1 000 000 giao dịch, số lượng 1 509 672, doanh thu 1 914 614,80.
- Truy vấn đi thật đến đúng bảng: mọi lượt đo có 0 lần dùng cache VertiPaq; trong 12 truy vấn mỗi nguồn (gồm lượt làm nóng), số dòng PostgreSQL đọc tăng đúng bằng 12 × số dòng của bảng tương ứng (`r11-scan-check.csv`).

## 5. Nhận xét và đánh đổi

- Lưu tổng hợp giảm mạnh dung lượng và thời gian nạp, đồng thời Q2 và Q3 đọc nhanh hơn; ở hai truy vấn này khoảng giá trị của hai cấu hình không chồng nhau.
- **Q1 chưa đủ để kết luận:** khoảng giá trị chồng nhau (378–666 và 337–493 ms). Trung bình bên chi tiết bị kéo lên bởi lượt 666 ms; trung vị là 393 so với 369 ms.
- Số dòng chỉ giảm 1,58 lần. Dung lượng giảm nhiều hơn số dòng; bảng tổng hợp bỏ các cột chi tiết, trong đó `transaction_id` là chuỗi dài. Phần đóng góp của từng yếu tố chưa được đo riêng.
- **Đánh đổi:** bảng tổng hợp không còn từng giao dịch, thời gian mua và các thuộc tính chi tiết; muốn phân tích theo các cột đó phải giữ dữ liệu chi tiết ở nơi khác. Công tổng hợp do bước xử lý trước khi ghi (trong hệ thống là Flink) đảm nhận.

## 6. Giới hạn

- Một đợt 1 000 000 dòng, một cấu hình PostgreSQL, một máy chạy Power BI, một người dùng.
- Chỉ 3 lượt đo; thời gian gồm độ trễ mạng nên có dao động.
- Mọi truy vấn lọc theo `run_id` mà bảng chỉ có một `run_id`, nên đọc toàn bảng; chưa đo truy vấn chọn lọc.
- So sánh một bảng tổng hợp (cửa hàng–sản phẩm), không phải cả ba bảng của hệ thống.
- Chưa có ảnh Performance Analyzer hay ảnh Azure Portal.
