# Flink Streaming ETL local — Giai đoạn 05

Flink 2.2.1 đọc **Kafka thật** tại `kafka:9092`, topic `retail.sales.transactions`. `sql/flink/01_kafka_source.sql` dùng Kafka SQL connector 5.0.0-2.2 và `raw` format: mỗi value đi vào SQL dưới dạng chuỗi JSON, kể cả JSON hỏng. Trường `event_time` trong contract là chuỗi UTC; DDL chuyển bằng `TO_TIMESTAMP_LTZ(..., 'UTC')` thành `event_ts` và đặt watermark trễ 5 giây. `emitted_at` chỉ là thời gian Producer phát; không dùng thay event time lịch sử. Metadata Kafka partition, offset và timestamp vẫn có trong source để điều tra.

`02_clean.sql` phân loại JSON lỗi, ID/trường bắt buộc thiếu, quantity, price, revenue, event time và một số quy tắc nguồn. Kiểm ngày bằng **round trip** vì hàm parse của Flink có thể chỉnh `2024-02-30` thành `2024-02-29`. `basket_id=null` vẫn hợp lệ. Tiền được `TRY_CAST` sang `DECIMAL`; mọi `SUM` dùng **`line_revenue`**, không dùng giá suy ra. `ROW_NUMBER() OVER (PARTITION BY run_id, transaction_id ORDER BY proc_time ASC)` giữ dòng hợp lệ đến đầu tiên. SQL `table.exec.state.ttl=1 h` giới hạn state của job vô hạn: bản trùng sau TTL có thể lọt vào và phải được xử lý theo chính sách dài hạn ở giai đoạn sau. Đây không phải exactly-once end-to-end.

`03_aggregates.sql` tạo tổng theo run, store, product và cặp store/product. `04_windows.sql` tạo TUMBLE **một phút theo event time** và group `run_id, store_id`. `table.exec.source.idle-timeout=5 s` giúp partition Kafka không có dữ liệu không giữ watermark đứng yên. Event đến sau khi watermark vượt window được bỏ khỏi kết quả window; các aggregate không window vẫn tính nó nếu hợp lệ. Chưa có side output/counter trực tiếp cho late event. JSON Schema toàn diện vẫn được kiểm ở Producer GĐ04; Flink SQL hiện kiểm các quy tắc nghiệp vụ chính, chưa thay thế validator JSON Schema cho mọi kiểu JSON, nullable key và extra field.

## Chạy và đối soát

Sau `docker compose -f docker/compose.yaml up -d`, kiểm `flink-checkpoint-init` thoát mã 0; nó sửa chủ sở hữu **chỉ checkpoint volume** sang UID/GID 9999, còn JobManager/TaskManager chạy bằng user `flink`. Cài `producer/requirements.txt` trong `.venv` nếu chưa có. Không dùng `down -v`.

Mỗi phép thử lấy high offsets **trước và sau** khi phát. `run_sql.py` render `scan.startup.mode=specific-offsets` và `scan.bounded.mode=specific-offsets` từ hai JSON baseline. Như vậy job bounded chỉ đọc message thuộc đoạn offset của phép thử, không cộng message GĐ04 đã có. Run ID mới dùng để đối soát độc lập, và `properties.group.id` khác cho mỗi tên run. Ví dụ:

```bash
.venv/bin/python producer/consumer_probe.py --capture-baseline reports/runtime/flink/demo_start.json
.venv/bin/python producer/replay.py --input data/samples/synthetic_10000.jsonl --limit 1000 --run-id stage05_demo_01 --stats-output reports/runtime/flink/demo_producer.json
.venv/bin/python producer/consumer_probe.py --capture-baseline reports/runtime/flink/demo_end.json
.venv/bin/python sql/flink/run_sql.py --name demo --start reports/runtime/flink/demo_start.json --end reports/runtime/flink/demo_end.json --query totals
.venv/bin/python sql/flink/verify_results.py --name demo --source data/samples/synthetic_10000.jsonl --limit 1000 --run-id-override stage05_demo_01 --queries totals
```

Các lựa chọn `--query`: `raw`, `quality`, `totals`, `store`, `product`, `store_product`, `windows`. Để đối soát trọn vẹn, chạy từng query rồi gọi verifier với toàn bộ danh sách. SQL Client ở streaming mode xuất changelog `+I/-U/+U`; verifier **materialize trạng thái cuối theo khóa**, không cộng các dòng update. Log, SQL đã render, offset baseline, JSON kết quả ở `reports/runtime/flink/` và được Git ignore. SQL Client đôi khi trả exit 0 dù câu SQL lỗi; runner còn kiểm `[ERROR]`/`Exception` trong log.

Fixture lỗi/trùng được tạo bằng `test_events.py quality --output reports/runtime/flink/quality_fixture.jsonl`, sau đó phát bằng `test_events.py send --input ...` giữa hai lần lấy baseline. Công cụ phát raw này **chỉ dành cho negative test**, giới hạn 100 dòng/100 KB và cố ý bỏ qua kiểm schema ở Producer; không dùng cho pipeline nghiệp vụ. Fixture gồm cùng `basket_id` khác line ID, duplicate cùng run, cùng line ID ở run khác, quantity/price sai, thiếu product ID, ngày sai và JSON hỏng.

Để thử watermark thật, dùng `--query stream_windows` **không có `--end`**, bắt đầu job trước khi phát sự kiện. Gửi 00:00:10, 00:00:50, 00:01:20; chờ print sink emit window 00:00 rồi gửi event muộn 00:00:30; gửi các event phút sau để đóng window tiếp. Kết quả nằm trong log TaskManager với prefix `stage05-window>`. Một truy vấn bounded đọc toàn bộ 6–9 event quá nhanh có thể chưa phát watermark giữa các event, nên không được dùng nó để kết luận late drop. `verify_results.py --live-window-log ...` so bốn window live đã xuất.

## Checkpoint, savepoint và kết quả đã đo

Job unbounded dùng checkpoint mỗi 10 giây tại `file:///opt/flink/checkpoints`, nằm trong Docker named volume. Job ID đầu `32b4666f904cc5971dbbf5f909590d51` đã RUNNING; REST `/jobs/<id>/checkpoints` báo **10 COMPLETED, 0 FAILED**, checkpoint gần nhất lúc kiểm là ID 10, state size 15.972 byte. Đã dừng job bằng `flink stop --savepointPath file:///opt/flink/checkpoints/savepoints <job-id>`, nhận đường dẫn `savepoint-32b466-5c62c486c09e`. SQL Client khởi chạy lại với `SET 'execution.state-recovery.path'` qua `run_sql.py --restore-path ...`; job mới `a418e722b77d86952425c1c928fe5092` RUNNING và REST báo `restored=1` từ savepoint đó. Sau event mới, window 00:03 xuất **2 dòng, quantity 3, revenue 7.00**, gồm state trước savepoint. Job thứ hai đã dừng bằng savepoint để trả tài nguyên. Đây là bằng chứng recovery của job thử local, không chứng minh exactly-once cho PostgreSQL chưa có ở GĐ05.

Các kết quả bounded thực tế:

| Bộ thử | Raw | Invalid | Duplicate | Unique valid | Quantity | Revenue |
|---|---:|---:|---:|---:|---:|---:|
| Synthetic 1.000 | 1.000 | 0 | 0 | 1.000 | 2.985 | 310.265,83 USD mô phỏng |
| Fixture chất lượng | 10 | 5 | 1 | 4 | 8 | 9,50 USD mô phỏng |
| dunnhumby 100 | 100 | 0 | 0 | 100 | 145 | 223,95 **XXX** |

Đối soát theo store, product, store/product và 334 window synthetic đều khớp phép tính độc lập. Dunnhumby có 7 store, 95 product và 18 window theo timestamp lịch sử được chuyển đổi; `basket_id` không dùng để dedup, currency và timezone nguồn vẫn chưa được xác minh. Window live 00:00 xuất 2 dòng/5,00 trước khi event muộn 00:00:30 được gửi; window ấy không đổi thành 3 dòng/9,00. Log REST/print sink và JSON đối soát nằm ở `reports/runtime/flink/`; khi đưa vào báo cáo, chỉ chọn ảnh Flink UI RUNNING, checkpoint COMPLETED và bảng expected/actual đã lược thông tin không cần thiết.

Nguồn cú pháp: [Flink Kafka SQL](https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/connectors/table/kafka/), [SQL functions](https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/dev/table/functions/systemfunctions/), [SQL Client và restore](https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/dev/table/sqlclient/), [Savepoints](https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/ops/state/savepoints/).
