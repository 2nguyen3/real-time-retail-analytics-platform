# Tiền xử lý dữ liệu dunnhumby Let's Get Sort-of-Real (dùng cho benchmark GĐ10)

Công cụ: `producer/convert_dunnhumby_weeks.py` (quy tắc chuyển đổi từng dòng dùng chung với `producer/convert_dunnhumby.py`). Dữ liệu là **dữ liệu mô phỏng do dunnhumby công bố**, không phải giao dịch khách hàng thật và không phải dữ liệu nhóm tự sinh. Tệp nguồn và tệp chuyển đổi không đưa vào Git.

## 1. Dữ liệu nguồn (đo trên toàn bộ tệp, 26/11/2026)

| Chỉ số | Giá trị |
|--------|---------|
| Tệp | 13 tệp `transactions_200807.csv` đến `transactions_200819.csv`, kèm `time.csv` |
| Dung lượng CSV gốc | 4 966 475 591 byte = 4,97 GB = 4,625 GiB |
| Số dòng | 34 802 918 |
| Số cột | 22, giống nhau ở 13 tệp |
| Khoảng thời gian | 07/04/2008 đến 06/07/2008, giờ 8 đến 22 |
| Cửa hàng, sản phẩm, khách, hóa đơn | 761, 4 997, 375 793, 5 330 071 |
| Tổng QUANTITY, tổng SPEND | 52 382 957; 66 743 729,18 |
| Dòng không có mã khách | 6 731 083 |
| Dòng lỗi số cột, số lượng <= 0, SPEND âm, thiếu sản phẩm hoặc cửa hàng | 0 |

13 tuần liên tiếp, tuần đầu cách tuần đầu của bộ dữ liệu 104 tuần, khớp vị trí phần 9 (suy ra từ số tuần; tên phần do nhóm xác nhận khi tải).

## 2. Các bước tiền xử lý

| # | Bước | Chi tiết | Lý do |
|---|------|----------|-------|
| 1 | Chọn cột | Dùng `SHOP_DATE`, `SHOP_HOUR`, `QUANTITY`, `SPEND`, `PROD_CODE`, `PROD_CODE_40`, `CUST_CODE`, `BASKET_ID`, `STORE_CODE`, `STORE_REGION`; các cột phân khúc không dùng | Đúng hợp đồng dữ liệu của hệ thống |
| 2 | Đổi tên và kiểu | `PROD_CODE` thành `product_id`, `STORE_CODE` thành `store_id`, `PROD_CODE_40` thành `category_id`, `QUANTITY` thành số nguyên | Khớp schema v1.0.0 |
| 3 | Doanh thu và đơn giá | `line_revenue` = `SPEND` (giữ nguyên, 2 chữ số thập phân, tính bằng Decimal); `price` = `SPEND / QUANTITY` làm tròn 8 chữ số, có kiểm tra `price × quantity` khớp lại `SPEND` | Nguồn không có đơn giá niêm yết |
| 4 | Mã giao dịch | `transaction_id` = checksum tệp + tên tệp + số dòng | Nguồn không có mã dòng |
| 5 | Giá trị thiếu | `customer_id` trống giữ là null | Không tạo dữ liệu giả |
| 6 | Thời gian | `event_time` = ngày + giờ mua, đặt ở đầu giờ, **giả định múi giờ UTC**; đánh dấu `event_time_basis = assumed_timezone`, `event_time_precision = hour` | Nguồn chỉ có ngày và giờ, không công bố múi giờ |
| 7 | Đơn vị tiền | **Giả định USD** (quyết định của nhóm, nguồn không công bố đơn vị) | Để báo cáo và dashboard có đơn vị thống nhất |
| 8 | Sắp theo thời gian | Sắp theo ngày, giờ, rồi theo vị trí trong tệp nguồn; không đổi giá trị nào | Tệp nguồn không theo thứ tự thời gian: ở tuần đầu, 98,7% dòng có giờ cũ hơn một dòng đứng trước; Flink sẽ coi là dữ liệu đến muộn và loại khỏi cửa sổ |
| 9 | Chia đợt | Mỗi đợt tối đa 1 000 000 dòng, mỗi đợt một `run_id`, có manifest kiểm tra (số dòng, hợp lệ, trùng, tổng số lượng, doanh thu, SHA-256) | Giới hạn bộ nhớ Flink và để đối soát từng đợt |

Nhãn trong dữ liệu: `source_type = transformed`, `source_dataset = dunnhumby-sort-of-real-weeks`.

## 3. Điều phải ghi khi trình bày

- Múi giờ UTC và đơn vị USD là **giả định**, không phải thông tin do nguồn xác nhận.
- Độ chính xác thời gian là giờ, nên bảng `sales_by_store_minute` thực chất tổng hợp theo giờ.
- Quy mô dữ liệu tính theo **CSV gốc** (4,625 GiB). Tệp JSON sau chuyển đổi lớn hơn do định dạng, không dùng để nói về quy mô.
- Quyền lưu và biến đổi dữ liệu trên cloud: trang nguồn nêu mục đích bài tập lớp và nghiên cứu; chưa tìm thấy giấy phép dataset cụ thể (xem `source_provenance.md`).

## 4. Lệnh chạy

```
python producer/convert_dunnhumby_weeks.py --input-dir data/raw --out-dir data/generated/part9 --prefix sor10 --source-utc-offset +00:00 --currency USD
```
