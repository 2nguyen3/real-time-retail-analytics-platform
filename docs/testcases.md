# Giai đoạn 07 — Integration, chất lượng dữ liệu và Gate B

## Cách tái chạy

Yêu cầu: branch có commit GĐ06, Docker Compose local đã chạy Kafka/Flink/PostgreSQL, `.venv` có `producer/requirements.txt` và `tests/requirements.txt`, SSD trống tối thiểu 5 GiB (8 GiB để chạy TC11). Runner không xóa topic, database hay volume. Mỗi lượt tự tạo `run_id` ngắn, khác lượt trước; lấy high offsets Kafka trước/sau, đối soát PostgreSQL theo từng khóa bằng Decimal. Bảng kiểm chứng ghi ra `reports/runtime/stage07/<batch>/` (Git ignore). Lệnh chạy:

```sh
.venv/bin/python -m pip install -r producer/requirements.txt -r tests/requirements.txt
.venv/bin/python tests/integration/run_stage07.py
.venv/bin/python -m pytest -q
RUN_STAGE07_INTEGRATION=1 .venv/bin/python -m pytest -q tests/integration/test_pipeline_e2e.py
```

`--cases TC01 TC02 ...` chọn nhóm cần chạy; `--batch` đặt tên lượt chạy chỉ gồm chữ thường, số và `_`. `--publish-evidence` chỉ dùng cho **đủ 11 TC** và từ chối ghi đè ba file evidence đã tồn tại. Lượt chạy ngày 17/11/2026 dùng batch `gateb_20261117_verified`; TC05 được kiểm bổ sung với batch `gateb_late_final` để thử cả event lệch thứ tự trong ngưỡng và tổng store/product. CSV ghi đường dẫn runtime riêng cho từng TC. Bằng chứng được lưu tại [ma trận](evidence/07-test-matrix.csv), [đối soát](evidence/07-validation-output.csv) và [restart log](evidence/07-restart-log.txt). Các run cũ GĐ01–06 không bị thay đổi hoặc cleanup.

## Ma trận test

| ID | Input và mục tiêu | Kỳ vọng | Kết quả thực tế |
|---|---|---|---|
| TC01 | 1.000 synthetic, Producer → Kafka → Flink → PostgreSQL | 1.000 ACK/Consumer/DB; ba bảng khớp | PASS; quantity 2.985, revenue 310.265,83 USD; 5 store, 373 store/product, 334 minute |
| TC02 | Duplicate cùng run, ID giống ở run khác, hai dòng cùng basket | Một duplicate; bốn dòng hợp lệ còn lại | PASS; khác run và khác transaction_id không bị loại |
| TC03 | Quantity `<=0` | Invalid, không vào doanh thu | PASS; Flink `quantity=1` trong bảng phân loại |
| TC04 | JSON hỏng, thiếu product, ngày sai, price âm | Phân loại riêng, không vào DB | PASS; `invalid_json`, `product_id`, `event_time`, `price` mỗi loại 1 |
| TC05 | 10 event: một event lệch 2 giây trong watermark 5 giây, một event quá muộn | Window 00:00 đã đóng giữ 2 dòng/5,00; 00:01 nhận event lệch thứ tự; store/product nhận 10 | PASS; 00:01 có 2 dòng/quantity 4/revenue 2,50; store và store/product đều quantity 15/revenue 26,50; late bị loại khỏi window **suy ra từ before/after**, chưa có counter trực tiếp |
| TC06 | Hai phiên Producer: dòng 1–10 rồi tiếp tục 11–20 | 10+10 ACK, 20 Kafka/Consumer/DB | PASS; hai phiên đều `pending=0`, ba bảng khớp nguồn |
| TC07 | Flink checkpoint, stop/savepoint, restore rồi gửi thêm | `restored=1`, 21 ACK/Consumer/DB, 20 window đã đóng | PASS; checkpoint ID 1, DB và window khớp expected |
| TC08 | Restart PostgreSQL khi không có Flink job chạy | DB healthy và tổng trước/sau bằng nhau | PASS; 5 store rows, 1.000 dòng, quantity 2.985, revenue 310.265,83 giữ nguyên |
| TC09 | Bounded JDBC job chạy lại cùng offset TC01 | UPSERT giữ một row mỗi PK, không nhân đôi tổng | PASS; row counts 5/373/334 trước và sau bằng nhau; ba bảng khớp |
| TC10 | Đối soát chất lượng và danh mục | `raw=invalid+duplicate+unique`; currency, NUMERIC, dimension đúng | PASS; normal 1.000=0+0+1.000; fixture 10=5+1+4; không thiếu dimension, `NUMERIC(28,2)` |
| TC11 | 10.000 synthetic trên Mac local | 10.000 ACK/Consumer/DB và ba bảng khớp | PASS; quantity 29.867, revenue 2.983.773,00 USD; 400 store/product, 3.334 minute |

TC02–TC04 dùng **cùng một fixture và một lần phát**, vì vậy có chung job ID/thời gian trong CSV. `07-validation-output.csv` so từng khóa và tổng **riêng mỗi bảng**, không cộng ba bảng với nhau. Bài 10.000 dòng có payload Kafka được ACK là 4.742.027 byte trong lượt này; đây là phép thử tích hợp local, không phải benchmark >4 GiB hoặc throughput cloud.

## Quy tắc chất lượng và nơi kiểm

| Quy tắc | Producer | Flink | PostgreSQL / đối soát |
|---|---|---|---|
| JSON Schema đầy đủ, kiểu, required/null, timestamp UTC | Validate trước phát thường; raw fixture đi đường kiểm thử riêng | Raw JSON giữ cả malformed; SQL kiểm các trường nghiệp vụ chính, **chưa thay thế toàn bộ JSON Schema** | Consumer probe kiểm schema; TC04 đối chiếu nhóm lỗi thực tế |
| Quantity, price, revenue | Contract và Decimal | `TRY_CAST`, khoảng hợp lệ, quan hệ tiền; `SUM(line_revenue)` | `NUMERIC(28,2)`, CHECK; đối soát Decimal từng khóa |
| Trùng và basket | `(run_id, transaction_id)` là danh tính dòng | Invalid trước dedup, first valid wins; không dedup basket | PK aggregate chứa run/currency; TC02, TC09 và CSV xác nhận kết quả cuối |
| Currency | Dùng mã nguồn, `XXX` vẫn chưa xác định | Group theo currency ở ba JDBC sink | PK chứa currency; TC10 kiểm run synthetic chỉ có USD |
| Event time / late | Không đổi event lịch sử khi replay | Watermark trễ 5 giây, idle partition 5 giây; event sau window đóng không vào minute sink | TC05 so window trước/sau; store/product vẫn nhận event hợp lệ |
| Quan hệ dimension | Seed chỉ ID/thuộc tính đã quan sát | Sink không phụ thuộc thứ tự seed | TC10 xác nhận không thiếu store/product trong run chuẩn |

Với fixture có các nhóm loại trừ nhau: **raw 10 = invalid 5 + duplicate 1 + unique valid 4**. Late event hợp lệ không được ghi là invalid; nó chỉ bị window bỏ theo watermark. Hiện **chưa có late counter/side output**, nên TC05 xác minh gián tiếp qua cửa sổ 00:00 trước/sau khi gửi event muộn. Dedup state có TTL 1 giờ; kiểm thử này không bảo đảm bản trùng sau TTL cũng bị loại.

## Reliability và Gate B

TC06 là **tiếp tục có kiểm soát từ dòng nguồn đã lưu sau hai phiên Producer đều nhận đủ ACK**. Nó không mô phỏng crash khi còn message chưa ACK. TC07 ghi riêng 10 ACK đầu, Kafka offset, Flink checkpoint/savepoint, REST `restored=1`, 11 ACK sau restore, Consumer 21 và DB cuối; trong **phạm vi sự kiện đã ACK của bài này**, không thấy mất dữ liệu. TC08 chỉ kiểm PostgreSQL persist khi Flink không chạy; chưa kiểm JDBC sink đang ghi trong lúc DB mất kết nối. TC09 chứng minh **idempotent final state** khi chạy lại đúng offset, không chứng minh exactly-once xuyên ba JDBC sinks. Các mốc trước/sau nằm trong restart log.

**Gate B: PASS cho pipeline local và 15 điều kiện nghiệm thu nêu trong yêu cầu GĐ07**, dựa trên 11/11 TC PASS, 21 unit tests PASS và 2 pytest integration opt-in PASS. Trong lúc phát triển, một lượt chạy FAIL vì SQL Client rút ngắn `run_id` dài khi in kết quả tableau; đã đổi test `run_id` sang mã ngắn ổn định và chạy lại toàn bộ ma trận PASS. Không sửa SQL ETL, data contract hay baseline cũ để làm khớp phép đo.

Kết quả này củng cố **R06** (cleaning, dedup, watermark/window) và **R09** (ETL tự động Producer → Kafka → Flink → PostgreSQL) ở phạm vi local. Nó không nghiệm thu Azure, dashboard, benchmark >4 GiB, throughput cloud hoặc latency giữa region. Trước triển khai cloud cần xác minh quota/region Azure, quyền sử dụng dunnhumby trên cloud, chi phí và chính sách late event cho vận hành dài hạn. Tag `local-pipeline-v1` chưa tồn tại; chỉ đề xuất tạo sau khi người dùng nghiệm thu và commit, **không tạo trong GĐ07**.
