# Kế hoạch GĐ10: benchmark dữ liệu lớn (>4 GB)

Trạng thái (cập nhật 21/11/2026): **kế hoạch đã duyệt, đã chạy thử (dry-run) trên local và Azure, đã điều chỉnh theo kết quả thử (xem mục 9). Chưa chạy chính thức.** Mọi số liệu trong tài liệu này là của lần chạy thử, không phải minh chứng; các tiêu chí B1–B7 vẫn PENDING. Rubric liên quan: R03 (>4 GB, RAM/CPU/disk, so sánh local và cloud), R08 (tốc độ đọc ghi, ba lần đo, p50/p95).

## 1. Mục tiêu và tiêu chí PASS

| Mã | Tiêu chí | PASS khi |
|----|----------|----------|
| B1 | Tổng dữ liệu nguồn >4 GiB (4,29 GB) | Tổng `raw_file_bytes` các manifest lớn hơn 4 294 967 296 |
| B2 | Flink xử lý đủ số dòng | Số dòng Kafka offset delta = số dòng manifest = tổng `raw_lines` PostgreSQL; sai lệch 0 |
| B3 | Đối soát giá trị | Tổng số lượng và doanh thu PostgreSQL khớp manifest từng chunk (dùng `sql/postgres/reconcile.py`) |
| B4 | Throughput ba lần đo | Ba lượt cùng workload, báo dòng/giây và MB/giây từng khâu |
| B5 | Độ trễ truy vấn p50/p95 | Mỗi truy vấn chạy ít nhất 30 lần mỗi lượt, ghi p50/p95 |
| B6 | RAM/CPU/disk | CSV lấy mẫu 5 giây trong suốt lượt chạy |
| B7 | So sánh local và cloud | Cùng một chunk chạy ở máy local và VM, ghi cấu hình hai bên |

Dữ liệu là **synthetic** (`source_type=synthetic`, quy tắc sinh công khai trong `producer/generate_data.py`). Không gọi là giao dịch thật. Mốc >4 GB còn chờ giảng viên chấp nhận cách tính này (xem `stage_01_status.md`).

## 2. Các phát hiện từ code hiện tại (ảnh hưởng thiết kế)

1. `producer/generate_data.py` giới hạn 100 000 dòng và cố ý từ chối nhiều hơn. Mỗi dòng trung bình **435 byte** (đo thật trên 2 000 dòng). Cần script sinh dữ liệu lớn **mới**, không sửa giới hạn của GĐ02.
2. Kafka đang giữ tối đa 128 MiB mỗi partition x 3 = 384 MiB và 6 giờ. Không chứa nổi 4 GB. Cách xử lý: chia **chunk**, chạy tuần tự từng chunk (publish, Flink bounded, đối soát), đồng thời nâng retention bằng biến môi trường trên VM để không mất dữ liệu giữa các bước.
3. `audit_data.py` giữ tập ID trong RAM, `replay.py` kiểm trùng ID bằng SQLite. Mỗi chunk 1 triệu dòng thì nằm trong 8 GB RAM của VM. Không chạy một file 12 triệu dòng.
4. Flink có 2 slot, TaskManager 1,5 GB. PostgreSQL `B1ms` là Burstable: tải ghi kéo dài có thể cạn credit CPU và làm chậm. Nếu thấy hiện tượng này sẽ ghi vào kết quả và đề xuất nâng `B2s` (cần duyệt riêng).
5. Dữ liệu synthetic cho mỗi basket một phút riêng, nên bảng `sales_by_store_minute` có khoảng 4 triệu dòng sau toàn bộ benchmark. Dung lượng PostgreSQL 32 GiB là đủ.

## 3. Thiết kế dữ liệu

- Tổng **12 000 000 dòng, khoảng 5,2 GB (4,86 GiB)**, chia **12 chunk x 1 000 000 dòng** (khoảng 435 MB mỗi chunk), có biên an toàn so với mốc 4 GiB. (Bản đầu là 5 chunk x 2 400 000 dòng; đổi vì giới hạn bộ nhớ Flink, xem mục 9.)
- Script mới `producer/generate_bulk.py`: sinh từng chunk bằng cùng hàm `rows()` của GĐ02 (cùng schema, seed cố định), `run_id` riêng cho mỗi chunk (`bench10_c01`...`bench10_c05`), mỗi chunk có manifest từ `audit_data.py`.
- Sinh **trên VM**, không tải về máy cá nhân. Đẩy chunk và manifest lên Blob.
- Chunk 1 cũng dùng cho lần chạy **local** (Docker trên máy Windows của người phụ trách) để so sánh.

## 4. Quy trình đo

Pha A. Sinh và lưu trữ
1. Sinh 12 chunk (1 triệu dòng mỗi chunk) và manifest, ghi thời gian sinh. Tổng byte tính từ manifest.
2. Tải lên Blob container riêng tư `benchmark` (xác thực bằng tài khoản người dùng, không dùng khóa tài khoản; không in khóa ra log). Ghi tên blob, kích thước, checksum.

Pha B. Chạy toàn bộ khối lượng một lần (chứng minh >4 GB, B1 đến B3)
1. Với từng chunk theo thứ tự: chụp offset, `replay.py` (rate 0), Flink bounded bằng `run_jdbc.py`, `reconcile.py`.
2. Ghi thời gian từng khâu và số dòng từng chunk vào `docs/evidence/10-volume-summary.csv`.

Pha C. Ba lượt đo hiệu năng (B4 đến B6)
1. Cùng chunk 1, mỗi lượt dùng `run_id` mới: đo thời gian publish (dòng/giây, MB/giây), thời gian Flink xử lý đến khi PostgreSQL đủ dòng (end-to-end), rồi chạy bộ truy vấn.
2. Bộ truy vấn cố định (doanh thu theo cửa hàng, theo phút trong 24 giờ, top sản phẩm): mỗi truy vấn 30 lần, tính p50/p95 từ phía VM.
3. Lấy mẫu RAM/CPU/disk 5 giây: script mới `tests/benchmark/sample_metrics.sh` (ghi CSV: `free`, `/proc/stat`, `df`, `docker stats`).

Pha D. Local
1. Chạy đúng chunk 1 một lượt (hoặc ba lượt) trên Docker local, ghi cấu hình máy (CPU, RAM, ổ đĩa).
2. Lập bảng so sánh local và cloud (B7). Hai bên khác phần cứng nên bảng ghi rõ cấu hình, không kết luận ai nhanh hơn một cách tuyệt đối.

## 5. Minh chứng sẽ lưu (không chứa bí mật)

`docs/evidence/10-volume-summary.csv`, `10-throughput-runs.csv`, `10-query-latency.csv`, `10-resource-samples.csv`, `10-local-vs-cloud.csv`, `10-benchmark-log.txt`; manifest từng chunk; cập nhật `docs/plan/rubric_mapping.md` (R03, R08 chỉ đổi sang PASS khi đủ bằng chứng) và `docs/azure-deployment.md`.

## 6. Quy trình Azure và chi phí (cần duyệt từng bước)

| Bước | Hành động | Bắt đầu tính tiền | Ước tính |
|------|-----------|-------------------|----------|
| 1 | Bật PostgreSQL `psql-retail-ea-7476` | Có (khoảng 0,0286 USD/giờ) | Cả GĐ khoảng 0,15 USD |
| 2 | Bật VM `vm-retail-ea-01` | Có (khoảng 0,114 USD/giờ) | Cả GĐ khoảng 0,6 USD |
| 3 | Kiểm tra firewall PostgreSQL và SSH theo IP hiện tại | Không | Chỉ xin duyệt nếu phải sửa rule |
| 4 | Tạo container `benchmark`, tải 5,2 GB lên Blob | Có (Hot LRS khoảng 0,024 USD/GB/tháng) | Khoảng 0,13 USD/tháng; không phí truyền trong cùng region |
| 5 | Chạy Pha A đến C trên VM | Đã tính ở bước 1–2 | Dự kiến 5–6 giờ (đã cập nhật, xem mục 9) |
| 6 | Tắt VM và PostgreSQL khi người phụ trách báo | Dừng tính compute | Còn đĩa, IP, storage |

Tổng ước tính GĐ10 khoảng **1 đến 2 USD** nếu không để máy chạy nhàn rỗi. Không có tắt tự động theo lịch: chỉ tắt khi người phụ trách yêu cầu. Chưa tính vùng thứ hai (thuộc GĐ11).

## 7. Rủi ro

| Rủi ro | Cách giảm |
|--------|-----------|
| Đĩa VM đầy (64 GB) | Dữ liệu khoảng 5,2 GB cộng log Kafka có retention giới hạn; kiểm `df` trước mỗi chunk |
| PostgreSQL B1ms hết credit CPU | Ghi lại, báo trước khi nâng cấu hình |
| Giảng viên không chấp nhận synthetic cho mốc >4 GB | Số đo vẫn hợp lệ cho R08; R03 giữ OPEN cho đến khi có xác nhận |
| IP người phụ trách đổi | Cập nhật rule firewall sau khi xin duyệt |
| Sai lệch số dòng | Dừng, không chuyển chunk, điều tra bằng offset và `reconcile.py` |

## 8. Việc chưa làm

Chưa viết `generate_bulk.py`, `sample_metrics.sh`, bộ truy vấn; chưa chạy bất kỳ phép đo nào. Mọi tiêu chí B1–B7 đang **PENDING**.

## 9. Nhật ký thay đổi so với kế hoạch ban đầu (21/11/2026)

Các thay đổi dưới đây đến từ lần chạy thử (dry-run), không phải từ lần chạy chính thức. Số liệu là số đo thử, không dùng làm minh chứng.

| # | Phát hiện | Bằng chứng (dry-run) | Thay đổi |
|---|-----------|----------------------|----------|
| 1 | Chạy thử cloud 200 000 dòng PASS, đối soát khớp | Publish 2 269 dòng/giây; Flink 1 484 dòng/giây; local cùng tệp: 3 163 và 2 429 | Giữ quy trình; ghi nhận cloud chậm hơn máy local |
| 2 | Nút thắt là CPU của VM, không phải PostgreSQL | Azure Monitor trong lúc chạy: PostgreSQL CPU 7–22%, VM CPU 66–96%, credit VM chưa cạn | Không nâng PostgreSQL. Nâng VM là tùy chọn để rút ngắn thời gian, chưa cần |
| 3 | Flink hết bộ nhớ heap với cấu hình mặc định (TaskManager 1 536 MB, heap khoảng 436 MB) | 1 triệu dòng: `OutOfMemoryError` và TaskManager chết; 500 000 dòng: job không hoàn thành trong 25 phút (chưa xác nhận trực tiếp bằng log) | Chunk 2,4 triệu dòng bị loại. Dùng chunk 1 triệu dòng và TaskManager 3 GB (heap khoảng 1,97 GB) |
| 4 | TaskManager 3 GB xử lý được 1 triệu dòng | PASS, đối soát khớp, Flink 2 376 dòng/giây (421 giây) | Đặt `FLINK_TM_PROCESS_MEMORY=3g`, `FLINK_TM_MANAGED_FRACTION=0.1`, `FLINK_TM_MEM_LIMIT=3500m` |
| 5 | Lô ghi JDBC 2 000 dòng nhanh hơn lô 100 khoảng 20% | 200 000 dòng: 2 911 so với 2 429 dòng/giây | Đặt `JDBC_FLUSH_MAX_ROWS=2000` cho benchmark (mặc định 100 giữ nguyên cho kiểm thử) |
| 6 | Tăng parallelism không giúp | Parallelism 2 so với 1: 2 362 so với 2 429 dòng/giây | Giữ `FLINK_PARALLELISM=1` |
| 7 | Kafka phải giữ nhiều hơn 128 MiB mỗi partition khi chunk lớn | Chunk 1 triệu dòng khoảng 145 MiB mỗi partition | Đặt `KAFKA_LOG_RETENTION_BYTES=1073741824` |
| 8 | Tiến trình `replay.py` mồ côi từ lần dừng trước ghi song song vào cùng topic, làm sai số đo | Thử nghiệm A bị lẫn, phải bỏ và chạy lại | Trước mỗi lần chạy: kiểm tra không còn `replay.py`, `run_stage10.py`, `run_jdbc.py`, job Flink RUNNING/RESTARTING |
| 9 | Lần chạy chính thức đầu tiên trên Azure (22/11/2026) dừng ở chunk 1: bảng `sales_by_store_minute` thiếu 457 cửa sổ phút (0,14%), hai bảng còn lại khớp 100%. Tái hiện trên local (thiếu 426). Tệp nguồn đúng thứ tự thời gian | Local 1 triệu dòng, idle-timeout nguồn `5 s`: FAIL, Flink 1 016 giây; idle-timeout `10 min`: PASS, Flink 347 giây (2 879 dòng/giây). Mới thử một lần mỗi cấu hình. Lần PASS trước đó với `5 s` cho thấy lỗi không xảy ra mọi lần, mà phụ thuộc tải | Thêm biến `FLINK_SOURCE_IDLE_TIMEOUT` (mặc định `5 s`, luồng realtime giữ nguyên). Benchmark bounded đặt `10 min`. Ghi vào báo cáo: idle-timeout ngắn làm mất dữ liệu khi replay backlog lớn |

Hệ quả cho lần chạy chính thức:
- 12 chunk x 1 triệu dòng, tổng khoảng 5,2 GB. Thời gian dự kiến trên VM hiện tại: khoảng 10 giờ cho toàn khối lượng theo số đo chunk 1 trên Azure (publish 13 phút, Flink 9 phút, đối soát 1 phút mỗi chunk, cộng đối soát và lấy mẫu), thay vì 4–5 giờ, cộng khoảng 1 giờ cho ba lượt đo. Chi phí vẫn khoảng 1–2 USD.
- Giới hạn bộ nhớ Flink (trạng thái khử trùng tăng theo số dòng, không được dọn trong một lần chạy) là **giới hạn thật của thiết kế hiện tại**, ghi vào báo cáo cùng với cách xử lý.
- Chưa kiểm chứng chunk lớn hơn 1 triệu dòng với TaskManager 3 GB.
- Nâng VM (hướng B) chỉ để rút ngắn thời gian; nếu dùng thì ghi so sánh trước/sau vào báo cáo và xin duyệt riêng.
