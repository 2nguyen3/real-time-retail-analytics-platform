# GĐ11: kế hoạch đo độ trễ theo vùng (region) trên Azure

Trạng thái: **kế hoạch, chưa thực hiện thao tác Azure nào.** Mọi bước Azure dưới đây chỉ chạy sau khi người phụ trách duyệt từng bước. R10 chỉ ghi PASS khi có kết quả chạy thật.

## 1. Mục tiêu (R10)

R10: đo độ trễ khi thiết lập server ở region khác. Tiêu chí PASS trong `rubric_mapping.md`: hai VM ở hai region, cùng workload, **DB cố định**, ghi region, timestamp, RTT và độ trễ truy vấn p50/p95, nhiều lượt.

| Mã | Tiêu chí | PASS khi |
|----|----------|----------|
| C1 | Hai VM ở hai region khác nhau, DB không đổi | Bảng cấu hình ghi region, SKU, thời điểm |
| C2 | RTT mạng tới PostgreSQL | Mỗi VM, ít nhất 3 lượt, mỗi lượt 50 lần mở kết nối TCP, báo p50/p95/max |
| C3 | Độ trễ truy vấn SQL | Mỗi VM, 3 lượt, 30 lần mỗi truy vấn (`SELECT 1` và bốn truy vấn GĐ10), báo p50/p95/max |
| C4 | Cùng workload, cùng dữ liệu | Cùng `run_id` đã nạp trong PostgreSQL, cùng lệnh, cùng phiên bản mã |
| C5 | Tùy chọn: ảnh hưởng tới throughput ghi | Chạy lại `repeat` 200 000 dòng trên VM thứ hai (Kafka, Flink cục bộ trên VM đó, ghi sang PostgreSQL ở xa) |

## 2. Thiết kế (không chuyển kiến trúc)

- **PostgreSQL giữ nguyên** ở East Asia. Không chuyển Kafka, Flink hay dữ liệu sang vùng khác.
- **VM1** (đã có, East Asia): cùng vùng với DB, làm mốc.
- **VM2** (mới): một VM ở region khác. Đề xuất một region xa để thấy chênh lệch rõ (West Europe hoặc East US), người phụ trách chọn. Có thể thêm một region gần (Southeast Asia) nếu quota và ngân sách cho phép.
- Công cụ: `tests/benchmark/run_stage11.py`, chạy cùng một lệnh trên từng VM:
  `python tests/benchmark/run_stage11.py --region <region> --vm-sku <sku> --run-id <run_id đã có> --evidence-dir docs/evidence --label official`
- Bản ghi không chứa tên máy chủ hay thông tin đăng nhập của PostgreSQL.
- Dữ liệu để đo: dùng `run_id` đã nạp từ GĐ10 (ví dụ `bench10_c01_11220833`), không nạp thêm.

## 2.1 Kết quả bước S1 (23/11/2026, chỉ đọc)

| Region | `Standard_B2as_v2` | Họ Bsv2 | `Standard_D2as_v4` / `D2s_v4` | Quota |
|--------|-------------------|---------|-------------------------------|-------|
| West Europe | Không có trong danh mục | Có nhưng `NotAvailableForSubscription` | Không có | Tổng vCPU vùng 6 (đã dùng 0) |
| East US | Không có trong danh mục | Không có | **Có, không hạn chế** | Tổng vCPU vùng 6; họ DASv4 4 vCPU (đã dùng 0) |

**Phát hiện khi thử tạo VM2 ở East US (23/11/2026):** Azure từ chối (`RequestDisallowedByAzure`) vì subscription có chính sách "Allowed resource deployment regions". Danh sách vùng được phép (đọc từ policy assignment): `malaysiawest`, `uaenorth`, `japaneast`, `eastasia`, `indiasouthcentral`. Không có tài nguyên nào được tạo ở East US. West Europe và East US vì vậy không dùng được cho VM2.

| Region (được phép) | `Standard_B2as_v2` | Quota |
|--------------------|-------------------|-------|
| UAE North | Không có SKU ứng viên nào trong danh mục | Tổng vCPU vùng 6 |
| India South Central | **Có, không hạn chế** (cùng SKU với VM1) | Tổng vCPU vùng 6; họ Basv2 10 vCPU |

Kết luận cập nhật: **chọn India South Central** (Hyderabad, khoảng cách xa East Asia nhất trong các vùng dùng được) với `Standard_B2as_v2`, cùng SKU với VM1 nên so sánh sát hơn. Japan East và Malaysia West gần East Asia hơn, chỉ dùng thêm nếu cần điểm gần để vẽ biểu đồ.

## 3. Các bước Azure (cần duyệt từng bước)

| # | Việc | Loại | Chi phí |
|---|------|------|---------|
| S1 | Kiểm tra quota và SKU `Standard_B2as_v2` ở region được chọn (`az vm list-usage`, `az vm list-skus`) | Chỉ đọc | 0 |
| S2 | Bật PostgreSQL và VM1 | Bật dịch vụ | PostgreSQL 0,029 + VM1 0,114 USD/giờ |
| S3 | Tạo VM2 (Ubuntu, khóa SSH hiện có, NSG chỉ cho SSH từ IP người phụ trách) trong `rg-retail-analytics` | Tạo tài nguyên | Khoảng 0,114 USD/giờ (B2as_v2, tùy region) cộng đĩa và IP công cộng |
| S4 | Thêm luật tường lửa PostgreSQL cho IP công cộng của VM2 | Đổi cấu hình | 0 |
| S5 | Trên VM2: cài Docker (công cụ truy vấn dùng `postgres:17-alpine`), chép mã và `.env` qua SSH | Cài phần mềm trên VM | 0 |
| S6 | Chạy `run_stage11.py` trên VM1 và VM2 (3 lượt mỗi VM) | Đo | Theo giờ bật |
| S7 | Chép bằng chứng về `docs/evidence/`, chụp ảnh Portal (region của VM, Metrics) | Đọc | 0 |
| S8 | Xóa VM2 cùng đĩa, IP công cộng, NSG, mạng ảo của nó; xóa luật tường lửa của VM2; tắt VM1 và PostgreSQL khi người phụ trách báo | Xóa và tắt | Giảm chi phí |

Ước tính: khoảng 2 giờ bật, tổng khoảng **0,5 USD** (VM2 khoảng 0,23, VM1 và PostgreSQL khoảng 0,29). Bước S8 xóa tài nguyên, chỉ làm khi người phụ trách đồng ý rõ ràng.

## 4. Rủi ro

| Rủi ro | Xử lý |
|--------|-------|
| Quota `B2as_v2` ở region mới bằng 0 (tài khoản cá nhân thường bị giới hạn) | S1 kiểm tra trước. Nếu không có, dùng SKU nhỏ hơn (ví dụ `Standard_B1ms`) và ghi rõ SKU trong bằng chứng. Phép đo RTT và truy vấn không cần VM lớn |
| Khác SKU giữa hai VM làm sai lệch so sánh | Ghi SKU trong từng dòng kết quả. RTT và truy vấn nhẹ ít phụ thuộc CPU |
| Truy vấn `revenue_by_store` quét nhiều dòng nên độ trễ phụ thuộc xử lý ở DB | Ghi nhận; `SELECT 1` và `store_totals` phản ánh gần đúng RTT |
| Quên tắt hoặc xóa VM2 | Không có tắt tự động theo lịch; trước khi báo xong, kiểm tra danh sách tài nguyên còn bật |
| Quá ít lượt, nhiễu thời điểm | Ba lượt mỗi VM, ghi timestamp; nếu chênh lệch lớn giữa các lượt thì chạy thêm |

## 5. Việc chưa làm

- Chưa chọn region cho VM2 (người phụ trách quyết định).
- Chưa thực hiện S1–S8.
- Chưa chạy `run_stage11.py` trên môi trường thật (đã kiểm tra tham số và hàm đo TCP trên máy local).
