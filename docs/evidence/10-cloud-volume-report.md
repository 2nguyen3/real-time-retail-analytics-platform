# GĐ10: minh chứng chạy `volume` trên Azure (22/11/2026)

Trạng thái: **R03 PASS một phần** (đủ >4 GiB trên cloud, thiếu so sánh local–cloud chính thức); **R08 PENDING** (chưa có ba lượt `repeat`). Gate GĐ10 chưa đạt.

## 1. Kết quả

| Chỉ số | Giá trị | Tệp nguồn |
|--------|---------|-----------|
| Số chunk | 12, tất cả PASS | `10-cloud-volume-summary.csv` |
| Tổng số dòng | 12 000 000 | `10-cloud-volume-summary.csv` |
| Tổng dung lượng | 5 366 480 537 byte = 4,998 GiB (5,37 GB), vượt 4 GiB | `10-cloud-volume-summary.csv` |
| Nguồn dữ liệu | `synthetic`, sinh bằng `producer/generate_bulk.py`, mỗi chunk có manifest kiểm tra (không trùng, không lỗi) | `10-cloud-volume-benchmark-log.txt` |
| Đối soát | Mỗi chunk khớp số dòng, số lượng và doanh thu với tệp gốc ở cả ba bảng PostgreSQL | log, cột `status` |

Dữ liệu synthetic được nhóm chấp nhận cho mốc >4 GB (quyết định của nhóm, chưa có xác nhận bằng văn bản của giảng viên).

## 2. Cấu hình lần chạy

| Thành phần | Giá trị |
|------------|---------|
| Vùng | East Asia |
| VM | Standard B2as_v2 (2 vCPU, 8 GB RAM, đĩa 64 GB), Kafka và Flink chạy bằng Docker Compose trên VM |
| PostgreSQL | Azure Database for PostgreSQL Flexible Server, B1ms, 32 GiB |
| Flink | 2.2.1, bounded job, TaskManager 3 GB (`FLINK_TM_PROCESS_MEMORY=3g`, `FLINK_TM_MANAGED_FRACTION=0.1`), parallelism 1 |
| JDBC | `JDBC_FLUSH_MAX_ROWS=2000` |
| Nguồn Kafka | `FLINK_SOURCE_IDLE_TIMEOUT="10 min"` (xem mục 4) |
| Kafka | 3 partition, `KAFKA_LOG_RETENTION_BYTES=1073741824` |
| Lệnh | `run_stage10.py volume --dir ~/bench --prefix bench10 --evidence-dir docs/evidence --label official --environment cloud` |

## 3. Số đo từng chunk (rút gọn)

| Chunk | Publish (dòng/giây) | Flink (dòng/giây) |
|-------|--------------------:|------------------:|
| 1–3 | 2 436–2 461 | 1 780–1 883 |
| 4 | 2 462 | 1 357 |
| 5–12 | 1 228–1 254 | 699–726 |

Chi tiết ở `10-cloud-volume-throughput.csv`, độ trễ truy vấn (p50, p95, max) ở `10-cloud-volume-query-latency.csv`, CPU/RAM/disk tóm tắt theo chunk và giai đoạn ở `10-cloud-volume-resource-summary.csv`. Dữ liệu lấy mẫu thô (45 594 dòng, 4 MB) không đưa vào Git, vẫn lưu ngoài repo tại `reports/runtime/stage10_cloud_official_volume/`.

Lưu ý khi đọc số đo: đây là một lần chạy cho mỗi chunk, không phải ba lượt, nên chưa đủ cho R08.

## 4. Hai phát hiện trong quá trình chạy

1. **Lần chạy chính thức đầu tiên (22/11/2026 05:26 UTC) FAIL ở chunk 1.** Bảng `sales_by_store_minute` thiếu 457 cửa sổ phút (0,14%), hai bảng còn lại khớp 100%. Tái hiện trên local (thiếu 426) với idle-timeout nguồn `5 s`; với `10 min` đối soát PASS (một lần thử mỗi cấu hình). Nguyên nhân khả dĩ nhất là subtask nguồn bị coi là rảnh nên watermark chạy trước và các sự kiện sớm bị loại. Mặc định `5 s` được giữ cho luồng realtime. Log lần FAIL: `10-cloud-attempt1-failed-log.txt`, `10-cloud-attempt1-failed-reconcile.csv`.
2. **VM burstable hết credit CPU.** Azure Monitor (trung bình 15 phút): credit còn lại giảm từ khoảng 58 lúc 08:30 UTC xuống khoảng 3 lúc khoảng 10:00 và giữ ở khoảng 1,6–1,9 sau đó; CPU VM từ 67–74% xuống khoảng 40%. Từ chunk 5, Flink giảm từ khoảng 1 800 xuống khoảng 725 dòng/giây và publish từ khoảng 2 450 xuống khoảng 1 230 dòng/giây. Chunk 1–3 là hiệu năng burst, chunk 5–12 là hiệu năng bền vững ở mức nền; không nên gộp thành một con số trung bình.

## 5. Còn thiếu cho Gate GĐ10

| Mục | Trạng thái |
|-----|------------|
| >4 GiB trên cloud, đối soát từng chunk (R03) | PASS |
| So sánh local–cloud chính thức, cùng workload (R03) | PENDING (mới có số chạy thử local, không phải minh chứng) |
| Ba lượt `repeat` cùng workload, throughput, p50/p95 (R08) | PENDING (lượt đầu bị dừng trước khi publish xong) |
| Ảnh Azure Monitor/Cost cho video và báo cáo | PENDING |
| Tải dữ liệu lên Blob container `benchmark` | PENDING (VM chưa có `az`) |
