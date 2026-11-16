# Data dictionary và hợp đồng dòng giao dịch v1.0.0

**Đơn vị dữ liệu:** một JSON message là **một dòng sản phẩm trong một hóa đơn**. Nhiều dòng có thể cùng `basket_id`; `transaction_id` là định danh duy nhất của *dòng*, còn `run_id` xác định một lượt tạo/phát. File chuẩn là `data/schema/transaction.schema.json`, mã hóa UTF-8, mỗi dòng JSONL là một object. Bộ mẫu GĐ02 chỉ là synthetic, chưa phải giao dịch đã phát Kafka.

## Trường và quy tắc

Các key trong danh sách `required` của JSON Schema phải xuất hiện trong object; `store_region` và `event_time_precision` là key tùy chọn để giữ tương thích bộ synthetic GĐ02. “Nullable” cho phép giá trị JSON `null`, khác với thiếu key. Giá trị ví dụ chỉ minh họa cấu trúc. Cột nguồn dưới đây ưu tiên sample **dunnhumby Let's Get Sort-of-Real đã kiểm CSV trực tiếp**; xem `source_provenance.md` để biết giới hạn.

| Trường | Kiểu / nullable | Ví dụ | Ý nghĩa, validate và nguồn dự kiến |
|---|---|---|---|
| `schema_version` | string, không null | `1.0.0` | Phiên bản contract, cố định. Bổ sung bởi pipeline. |
| `transaction_id` | string ≤128 ký tự, không null | `demo_001:line:00000001` | ID dòng duy nhất trong một run. Dữ liệu nguồn không có ID dòng độc lập: tạo từ checksum file + số dòng vật lý; không dùng `basket_id` đơn lẻ. |
| `basket_id` | string hoặc null | `demo_001:basket:000001` | ID hóa đơn, nhiều dòng dùng chung. Sample Sort-of-Real có `BASKET_ID` bị rút thành số khoa học, không khôi phục được nên converter ghi null; synthetic tạo theo nhóm dòng. |
| `product_id` | string, không null | `P00042` | Mã sản phẩm; từ `product_id` nguồn hoặc synthetic. |
| `customer_id` | string hoặc null | `C0025` | Mã khách đã ẩn danh. Từ `CUST_CODE`; 2.770 dòng sample trống vì không có thẻ loyalty nên giữ null, không bịa ID. Synthetic luôn có ID. |
| `store_id` | string, không null | `S003` | Mã cửa hàng; từ `STORE_CODE` nguồn hoặc synthetic. |
| `store_region` | string hoặc null, key tùy chọn | `E02` | Vùng cửa hàng từ `STORE_REGION`; generator synthetic cũ không cung cấp. |
| `category_id` | string hoặc null | `D00002` | Nhóm sản phẩm; Sort-of-Real lấy `PROD_CODE_40`, một cấp trong hierarchy nguồn; synthetic gán từ product một cách tất định. |
| `quantity` | integer 1–100000, không null | `2` | Số đơn vị trong dòng. `<=0`, không phải integer hoặc vượt trần test bị loại. Trần này là chính sách của pipeline, không phải thuộc tính dataset gốc. |
| `price` | decimal **dạng string**, tối đa 10 chữ số nguyên, đúng 8 chữ số thập phân, không null | `1.25000000` | Đơn giá **suy ra** từ `SPEND / QUANTITY` bằng Decimal, không phải giá niêm yết. Làm tròn 8 chữ số rồi kiểm nhân ngược về cents; nếu không khớp thì dừng. |
| `line_revenue` | decimal string 2 chữ số thập phân, không null | `2.50` | Doanh thu dòng có thẩm quyền: Sort-of-Real lấy nguyên giá trị `SPEND`, chuẩn hóa 2 chữ số; synthetic = `quantity × price` làm tròn cents. Không thay `SPEND` bằng tích đơn giá đã làm tròn. |
| `event_time` | RFC 3339 UTC `...Z`, không null | `2024-01-01T00:00:00Z` | Với Sort-of-Real là **đầu khung giờ** từ `SHOP_DATE` + `SHOP_HOUR` sau khi áp dụng offset được khai báo; không phải phút/giây giao dịch thực. Nguồn chưa công bố timezone. Synthetic dùng mốc cố định. |
| `event_time_basis` | enum, không null | `synthetic` | `source_utc`, `assumed_timezone` hoặc `synthetic`; công khai cơ sở thời gian. |
| `event_time_precision` | enum, key tùy chọn | `hour` | `hour` cho Sort-of-Real, `second` khi nguồn thật có độ chính xác giây; key vắng trong mẫu synthetic GĐ02 hiện có. |
| `emitted_at` | RFC 3339 UTC hoặc null | `null` | Thời điểm **thực tế phát** vào Kafka, producer GĐ04 mới điền. Generator GĐ02 để null để tái tạo byte chính xác; tuyệt đối không lấy `event_time` thay thế. |
| `run_id` | string 1–64, không null | `demo_001` | Nhận diện lần tạo/phát, dùng để đối soát và cô lập kết quả. |
| `source_type` | enum, không null | `synthetic` | `original`, `transformed`, `synthetic`. GĐ02 generator luôn `synthetic`; bản gốc chuyển sang contract là `transformed`, không giả nhận original. |
| `source_dataset` | string, không null | `stage02-synthetic-v1` | Tên nguồn/phiên bản. Converter dùng `dunnhumby-sort-of-real-sample-2k`; checksum ZIP được ghi trong provenance. |
| `currency` | mã ISO 4217 ba chữ hoa, không null | `XXX` | `XXX` là nhãn **chưa xác minh đơn vị tiền** của Sort-of-Real; không được trình bày là USD/GBP/VND. Synthetic GĐ02 dùng USD mô phỏng. |

JSON Schema kiểm cấu trúc/kiểu. `producer/audit_data.py` kiểm thêm tính hợp lệ của ngày, số Decimal, cùng `run_id`, quy tắc tiền và trùng ID. Không dùng JSON number cho tiền trong contract.

## Chính sách chất lượng và đối soát

1. Đọc theo thứ tự file. **Kiểm invalid trước, duplicate sau.** Bản ghi thiếu key, sai kiểu, `quantity <= 0`, `price < 0`, thời gian không phải UTC hợp lệ hoặc `line_revenue` không khớp đều là invalid và **không chiếm** `transaction_id`.
2. Bản ghi hợp lệ về cấu trúc nhưng có `transaction_id` đã được chấp nhận trước đó trong cùng `run_id` là duplicate; không cộng doanh thu/số lượng lần hai. Hai dòng cùng `basket_id` nhưng khác `transaction_id` vẫn hợp lệ.
3. `valid_count + invalid_count + duplicate_count = message_count`. `unique_transaction_id_count` đếm ID string có mặt ở mọi message (kể cả bản ghi invalid) để kiểm đặc tính file, không phải số dòng doanh thu.
4. Cộng `quantity` và `line_revenue` của **valid sau dedup** bằng `int` và `Decimal`, theo store, product và giờ UTC của `event_time`. Với tiền, làm tròn `ROUND_HALF_UP` đến 0,01; không dùng float.
5. Bộ đối soát GĐ02 **không loại late event**: chưa có watermark hay clock của Flink. `event_time` chỉ dùng nhóm theo giờ; chính sách late sẽ được định nghĩa/thử ở GĐ05–07. Giá trị `emitted_at=null` không được dùng để tính latency.
6. Với Flink và PostgreSQL về sau, doanh thu phải cộng từ `line_revenue` dạng `DECIMAL` sau lọc/dedup theo `transaction_id`. `price` là giá suy ra để kiểm hợp đồng, không thay thế số `SPEND` nguồn. Nếu `basket_id=null`, không tính số hóa đơn từ sample này; tuyệt đối không dedup theo `basket_id`.

## Dữ liệu nguồn và synthetic

Nguồn ưu tiên là Sort-of-Real do dunnhumby mô phỏng; sample CSV đã kiểm trực tiếp, còn quyền sử dụng, basket ID, timezone và đơn vị tiền ở trạng thái PENDING trong `source_provenance.md`. Không gán các thuộc tính chưa biết cho dữ liệu. Dữ liệu do generator tạo từ seed chỉ phục vụ kiểm hợp đồng/ETL tương lai; không dùng để tuyên bố đã xử lý bộ đầy đủ hoặc >4 GB.

## Tái tạo bộ mẫu

```bash
.venv/bin/python producer/generate_data.py --count 10000 --seed 2026 --run-id stage02_demo --output data/samples/synthetic_10000.jsonl --manifest data/manifests/synthetic_10000.json
.venv/bin/python producer/audit_data.py --input tests/fixtures/quality_cases.jsonl --manifest data/manifests/quality_cases.json --seed 0 --run-id fixture_001
```

Generator không phát Kafka. Auditor là chương trình độc lập đọc **file thực tế** để tính expected và SHA-256; manifest có số byte và kết quả theo store/product/giờ. Các lệnh trên không ghi đè file đã có. JSON Schema kiểm hình dạng dữ liệu; auditor kiểm thêm ngày lịch hợp lệ và quan hệ giữa các trường. Mẫu 10.000 dòng là synthetic, không phải mẫu trích từ nguồn dunnhumby.

Fixture `tests/fixtures/quality_cases.jsonl` có 8 message: 3 hợp lệ, 4 lỗi (quantity, price, thiếu product_id, ngày không tồn tại) và 1 bản trùng `transaction_id`. Hai dòng hợp lệ cùng `basket_id` được tính riêng. Expected sau lọc/dedup là quantity `6`, revenue `6.50 USD`; bảng theo store/product/giờ và checksum nằm trong `data/manifests/quality_cases.json`. Đây là giá trị đối soát đã kiểm bằng test, không phải kết quả Flink.
