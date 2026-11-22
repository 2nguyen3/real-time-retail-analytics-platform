# GĐ10: sổ tay thao tác và nơi kiểm tra (dùng để demo, quay video, viết báo cáo)

Mọi lệnh Azure chỉ chạy sau khi người phụ trách duyệt. Không ghi mật khẩu, ID tài khoản hay email vào tài liệu này. Giá trị trong ngoặc nhọn là chỗ điền khi chạy.

## 0. Hai loại lần chạy

| Loại | Mục đích | Nơi lưu kết quả | Nhãn |
|------|----------|-----------------|------|
| Chạy thử (dry-run) | Kiểm tra script, ước lượng thời gian | `reports/runtime/stage10/` (Git bỏ qua) | `dry-run` |
| Chạy chính thức | Quay video, làm báo cáo, nộp minh chứng | `docs/evidence/` | `official` |

Chỉ kết quả `official` được dùng để ghi PASS trong `rubric_mapping.md`. Chạy thử không có giá trị minh chứng.

## 1. Công cụ đã có (kiểm tra local, chưa tốn tiền)

| Công cụ | Việc làm |
|---------|----------|
| `producer/generate_bulk.py` | Sinh nhiều chunk synthetic kèm manifest và tệp tổng hợp |
| `tests/benchmark/run_stage10.py` | Chạy `volume` (mọi chunk) hoặc `repeat` (N lượt cùng workload): publish, Flink, đối soát, độ trễ truy vấn |
| `tests/benchmark/sample_metrics.py` | Lấy mẫu CPU/RAM/disk mỗi 5 giây vào CSV |
| `docker/compose.yaml` | Biến `KAFKA_LOG_RETENTION_BYTES`, `FLINK_TM_PROCESS_MEMORY`, `FLINK_TM_MANAGED_FRACTION`, `FLINK_TM_MEM_LIMIT` (mặc định giữ nguyên khi không đặt) |
| `sql/flink/run_jdbc.py`, `run_sql.py` | Biến `JDBC_FLUSH_MAX_ROWS` (mặc định 100), `FLINK_PARALLELISM` (mặc định 1), `JDBC_SUBMIT_TIMEOUT` (mặc định 180 giây), `FLINK_SOURCE_IDLE_TIMEOUT` (mặc định `5 s`; benchmark đặt `10 min`) |

Kết quả chạy thử (21/11/2026, không phải minh chứng): xem bảng thay đổi ở mục 9 của `stage_10_benchmark_plan.md`. Tóm tắt: cloud 200 000 dòng PASS (Flink 1 484 dòng/giây); local 1 triệu dòng với TaskManager 3 GB PASS (2 376 dòng/giây); cấu hình mặc định hết bộ nhớ từ 500 000 dòng.

## 2. Các bước trên Azure (theo thứ tự demo)

| # | Việc | Lệnh hoặc thao tác | Kiểm tra ở đâu |
|---|------|-------------------|----------------|
| 1 | Đăng nhập, kiểm tra đúng tenant | `az account show --query tenantId -o tsv` (phải bắt đầu bằng `b38272bd`) | Terminal |
| 2 | Bật PostgreSQL | `az postgres flexible-server start -g rg-retail-analytics -n psql-retail-ea-7476` | Portal, PostgreSQL, Overview: Status = Ready |
| 3 | Bật VM | `az vm start -g rg-retail-analytics -n vm-retail-ea-01` | Portal, VM, Overview: Running |
| 4 | SSH vào VM | `ssh azureuser@{ip-công-khai}` | Terminal |
| 5 | Khởi động Kafka, Flink cục bộ trên VM với bộ nhớ lớn hơn | `KAFKA_LOG_RETENTION_BYTES=1073741824 FLINK_TM_PROCESS_MEMORY=3g FLINK_TM_MANAGED_FRACTION=0.1 FLINK_TM_MEM_LIMIT=3500m sudo -E docker compose --env-file .env -f docker/compose.yaml up -d kafka-init flink-jobmanager flink-taskmanager` | `docker ps`; log TaskManager có `Xmx` khoảng 1,97 GB |
| 6 | Sinh dữ liệu | `python producer/generate_bulk.py --out-dir ~/bench --chunks 12 --rows-per-chunk 1000000` | Tệp `bench10_summary.json`: `total_bytes`, `exceeds_4_GiB` |
| 7 | Tải lên Blob | `az storage blob upload-batch` vào container `benchmark` bằng `--auth-mode login` | Portal, Storage account, Containers, benchmark |
| 8 | Chạy toàn khối lượng | `export JDBC_FLUSH_MAX_ROWS=2000 FLINK_SOURCE_IDLE_TIMEOUT="10 min"; python tests/benchmark/run_stage10.py volume --dir ~/bench --evidence-dir docs/evidence --label official --environment cloud` | `10-volume-summary.csv`, `10-benchmark-log.txt` |
| 9 | Chạy ba lượt đo | `export JDBC_FLUSH_MAX_ROWS=2000 FLINK_SOURCE_IDLE_TIMEOUT="10 min"; python tests/benchmark/run_stage10.py repeat --source ~/bench/bench10_c01.jsonl --rows 1000000 --reps 3 --evidence-dir docs/evidence --label official --environment cloud` | `10-throughput-runs.csv`, `10-query-latency.csv`, `10-resource-samples.csv` |
| 10 | Chụp biểu đồ Portal | VM, Monitoring, Metrics: CPU, Network; PostgreSQL, Monitoring: CPU, Storage, Connections | Portal (che tên tài khoản khi chụp) |
| 11 | Kiểm tra chi phí | Portal, Cost Management, Cost analysis (dữ liệu trễ vài giờ) | Portal |
| 12 | Tắt khi người phụ trách báo | `az vm deallocate ...` rồi `az postgres flexible-server stop ...` | Portal: Deallocated và Stopped |

Biến môi trường cần có trên VM (đã ở `~/retail/.env`, không in ra): `PG_HOST`, `PG_USER`, `PG_PASSWORD`, `JDBC_URL`, `JDBC_USER`, `JDBC_PASSWORD`.

## 3. Tệp kết quả

| Tệp | Nội dung | Dùng cho |
|-----|----------|----------|
| `10-volume-summary.csv` | Số dòng, số byte cộng dồn từng chunk, GiB | R03 |
| `10-throughput-runs.csv` | Dòng/giây, MB/giây của publish và Flink, thời gian đối soát | R08 |
| `10-query-latency.csv` | p50, p95, max từng truy vấn mỗi lượt | R08 |
| `10-resource-samples.csv` | CPU/RAM/disk theo thời gian và theo giai đoạn | R03 |
| `10-benchmark-log.txt` | Nhật ký từng bước, có thời gian UTC | Minh chứng |

## 4. Lưu ý khi đọc kết quả

- `publish_send_s` là thời gian gửi thực; `publish_wall_s` gồm cả bước kiểm trùng ID trước khi gửi.
- Độ trễ truy vấn đo ở phía client (`\timing` của psql trong một phiên), bỏ lần đầu để loại ảnh hưởng bộ nhớ đệm.
- Flink chạy sau khi publish xong (chế độ bounded), nên hai khâu tính riêng, không chồng nhau.
- So sánh local và cloud phải kèm cấu hình máy, không kết luận tuyệt đối ai nhanh hơn.

## 5. Kiểm tra trước mỗi lần chạy (rút ra từ lần chạy thử)

1. Không còn tiến trình `replay.py`, `run_stage10.py`, `run_jdbc.py` hoặc `sql-client` chạy sót (trên VM: `pgrep -af "replay|run_stage10|run_jdbc|sql-client"`).
2. Flink không có job RUNNING hoặc RESTARTING (`curl -s localhost:8081/jobs/overview`).
3. TaskManager báo đủ bộ nhớ (log có `Xmx` khoảng 1,97 GB) và `df -h /` còn ít nhất 20 GB.
4. Khi job Flink ở trạng thái RESTARTING lâu: dừng, đọc `/jobs/<id>/exceptions`; đừng chờ hết thời hạn.
5. Đặt `FLINK_SOURCE_IDLE_TIMEOUT="10 min"` (với `5 s`, đối soát bảng theo phút có thể thiếu cửa sổ khi replay lớn). Trên VM, chạy bằng `set -a; . ./.env; set +a; sudo -E ...` và nohup.
6. Kết quả của lần chạy chính thức chỉ hợp lệ khi chạy một lượt tại một thời điểm.
