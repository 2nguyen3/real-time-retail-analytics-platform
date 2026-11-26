# Ma trận rubric R01–R20

**Nguồn chấm điểm:** workbook `Tiêu chí đánh giá đồ án.xlsx`, chỉ tab `Bài tập Lớn`, các hàng 2–44. Kế hoạch DOCX v2.0 cung cấp mã R01–R20 và giai đoạn. Chọn duy nhất nhánh **Trực quan dữ liệu** ở nhóm hiện thực. `PASS` chỉ được ghi khi sản phẩm và phép thử có minh chứng; tại GĐ01 tất cả tiêu chí chấm điểm vẫn `PENDING`.

| Mã | Tiêu chí rubric | Điểm | GĐ | Công việc / sản phẩm dự kiến | Minh chứng để xét PASS | Trạng thái |
|---|---|---:|---|---|---|---|
| R01 | Giới thiệu loại bài toán: lưu trữ, thu thập, trực quan, xử lý | 0,25 | 01, 12 | `architecture.md`, phần giới thiệu báo cáo | Sơ đồ và mô tả bốn nhóm trong báo cáo được rà soát | PENDING |
| R02 | Loại dữ liệu | 0,25 | 02, 12 | Data dictionary, nguồn dataset, ví dụ giao dịch, bảng DB | File nguồn/provenance và dữ liệu mẫu có thể kiểm tra | PENDING |
| R03 | Kích thước dữ liệu và dung lượng bộ nhớ cho xử lý; mức >4 GB, so sánh truyền thống/cloud | 0,75 | 02, 10–11 | Manifest, workload đối chiếu, số đo RAM/CPU/disk | Tổng bytes >4 GB, số dòng Flink thực xử lý và kết quả so sánh có log | PENDING (đang đo lại bằng dunnhumby Sort-of-Real, 4,625 GiB; các lần đo synthetic trước chỉ là kiểm thử, đã xóa khỏi repo, còn trong commit 627840e) |
| R04 | Liệt kê và phân loại các thành phần cloud: IaaS, PaaS, FaaS, SaaS | 0,25 | 01, 08, 12 | Bảng phân loại trong kiến trúc và báo cáo | Dịch vụ thực tế, ảnh resource, nêu FaaS không dùng | PENDING |
| R05 | Cơ sở lý thuyết về định dạng lưu trữ | 0,50 | 02, 12 | CSV/JSON/PostgreSQL/Blob, lý do lựa chọn | Tài liệu lý thuyết gắn với dữ liệu và cấu hình thật | PENDING |
| R06 | Cơ sở lý thuyết về thuật toán xử lý | 0,50 | 05–07, 12 | Mô tả lọc, dedup, window/watermark, aggregate | Dataflow, SQL, ví dụ expected/actual | PENDING |
| R07 | Trình bày chi tiết các dịch vụ sử dụng cloud | 0,50 | 08, 12 | Deployment, cấu hình, mạng, region, cost | Ảnh resource và cấu hình đã tạo, mô tả trong báo cáo | PENDING |
| R08 | Tốc độ cho phép đọc ghi | 0,50 | 10–11 | Benchmark Kafka/Flink/DB, query latency | Ba lần đo, throughput, p50/p95, log và cấu hình | PENDING (đang đo lại trên dunnhumby; chờ tổng hợp minh chứng) |
| R09 | Thiết lập luồng xử lý dữ liệu tự động ETL | 0,50 | 04–07 | Producer → Kafka → Flink → PostgreSQL | Demo tự động và đối soát SQL không chuyển file thủ công | PENDING |
| R10 | Đo độ trễ khi thiết lập server ở region khác | 0,50 | 08, 11 | Hai VM/region cùng workload, DB cố định | Region, timestamp, RTT và query latency p50/p95 | PASS về số đo (24/11/2026): hai VM cùng SKU ở East Asia và India South Central, DB cố định, ba lượt mỗi VM, RTT và p50/p95 (`docs/evidence/11-*`); chưa có ảnh Portal, chưa đo throughput ghi qua vùng xa; truy vấn đo trên dữ liệu synthetic đã nạp, cần xác nhận lại sau khi đổi sang dunnhumby |
| R11 | Giải pháp tối ưu lưu trữ và cải thiện đọc ghi từ vùng lưu trữ sang ứng dụng | 0,50 | 11 | A/B một biến, đo Blob → reader hoặc DB → BI | Baseline/sau tối ưu, throughput/latency và đánh đổi | PENDING |
| R12 | Deploy dashboard SaaS, ít nhất bốn report | 0,75 | 09 | Bốn report online: tổng quan, chi tiết, hai report có bộ lọc | URL và ảnh bốn report riêng dưới tài khoản Viewer | PENDING |
| R13 | Button/navigation giữa các report | 0,25 | 09 | Liên kết điều hướng qua bốn report | Video click thực dưới quyền Viewer | PENDING |
| R14 | Cập nhật dữ liệu tức thời từ mô hình lên dashboard | 0,50 | 01, 09 | POC refresh; phép đo event → DB → dashboard | Ba lượt cập nhật mới, timestamp và video; giảng viên xác nhận mức chấp nhận | PENDING |
| R15 | Chia sẻ dashboard và ràng buộc từng nhóm người chỉ xem dữ liệu được phép | 1,00 | 01, 09 | Chia sẻ, Viewer, RLS theo cửa hàng | Ba tài khoản/nhóm, ma trận thử truy cập chéo, quyền thật | PENDING |
| R16 | Responsive để xem dashboard trên mobile | 0,50 | 09 | Layout mobile cho bốn report | Ảnh/video thử trên thiết bị thật | PENDING |
| R17 | PowerPoint báo cáo theo định dạng yêu cầu | 0,50 | 12 | Slide báo cáo | File slide, hình/bảng/nguồn, rà font/chính tả | PENDING |
| R18 | Word báo cáo theo định dạng yêu cầu | 0,50 | 12 | Báo cáo Word | File Word, hình/bảng/nguồn, kết quả đo thật | PENDING |
| R19 | Trình bày PowerPoint và demo | 0,50 | 12 | Kịch bản demo và phân vai nhóm | Video/thuyết trình/demo chạy thực tế | PENDING |
| R20 | Quản lý dự án trên cloud; cùng làm trên một resource, GitHub bổ trợ, chi phí/quota | 0,50 | 01, 08, 12 | Issue/PR/commit, Azure IAM và cost/quota | Hoạt động ba thành viên, quyền Azure, ảnh chi phí/quota | PENDING |

## Kiểm tổng điểm

| Nhóm | Thành phần | Tổng |
|---|---|---:|
| Giới thiệu | R01–R04 | 1,50 |
| Cơ sở lý thuyết | R05–R07 | 1,50 |
| Mô hình dữ liệu | R08–R11 | 2,00 |
| Hiện thực: nhánh trực quan | R12–R16 | 3,00 |
| Báo cáo và quản lý | R17–R20 | 2,00 |
| **Toàn bộ** | **R01–R20** | **10,00** |

Rubric nêu ví dụ bốn report: tổng quan, chi tiết, filter 1, filter 2. Kế hoạch đặt tên Overview/Product/Store/Time. Cần ánh xạ rõ hai bộ lọc và xác nhận cách giảng viên hiểu “report”; xem `stage_01_status.md`.

## Checklist minh chứng theo tiêu chí

**Hình trong báo cáo** là hình/bảng thực sự giúp giảng viên thấy kiến trúc, sản phẩm hoặc kết quả so sánh. **Số liệu/log** là file gốc để kiểm chứng; không cần chụp Terminal cho từng lệnh. **Nội bộ** là phép kiểm của nhóm, chỉ nêu trong phương pháp hoặc phụ lục khi cần. Checklist này định hướng các giai đoạn sau, chưa xác nhận mục nào đã hoàn thành.

| Mã | Hình/bảng nên đưa vào báo cáo | File số liệu/log cần giữ | Kiểm tra nội bộ, không cần ảnh riêng |
|---|---|---|---|
| R01 | Sơ đồ bốn nhóm và luồng dữ liệu | Không bắt buộc | Rà mô tả đúng bài toán |
| R02 | Bảng từ điển dữ liệu và vài giao dịch mẫu có chú thích nguồn | Dataset provenance, schema, sample nhỏ | Kiểm kiểu/trường bắt buộc |
| R03 | Biểu đồ/tổng hợp dung lượng >4 GB và RAM/CPU/disk; bảng local–cloud | Manifest bytes, số dòng Flink, raw metrics, cấu hình, kết quả đối soát | Kiểm đơn vị GB/GiB, checksum |
| R04 | Bảng dịch vụ thực tế gắn IaaS/PaaS/SaaS; ảnh Azure resource nếu hữu ích | Resource inventory/region | Kiểm FaaS không dùng, không nhận là đã triển khai khi mới dự kiến |
| R05 | Bảng so sánh CSV/JSON/PostgreSQL/Blob | Định dạng mẫu và nguồn tài liệu | Rà cấu trúc file |
| R06 | Sơ đồ ETL/window hoặc ví dụ input→output | SQL Flink, fixture expected/actual | Kiểm dedup, watermark, lỗi |
| R07 | Sơ đồ triển khai Azure có vùng/mạng/dịch vụ | Cấu hình resource đã lược secret, inventory/cost | Kiểm quyền và mạng |
| R08 | Biểu đồ/bảng throughput, độ trễ p50/p95 | CSV benchmark ba lượt, log cấu hình và truy vấn | Kiểm đồng nhất workload/đơn vị |
| R09 | Sơ đồ pipeline kèm một kết quả SQL đối soát | Producer/Kafka/Flink/DB logs theo `run_id`, expected/actual | Smoke test và restart |
| R10 | Biểu đồ độ trễ hai region, ghi rõ vị trí | CSV RTT/query timing nhiều lượt, region/SKU/timestamp | Kiểm cùng workload và DB cố định |
| R11 | Biểu đồ/bảng A/B storage→ứng dụng | Raw query plan, CSV trước/sau, cấu hình một biến | Kiểm sai số và đánh đổi read/write |
| R12 | Ảnh chụp bốn report **riêng** có tên/mục đích | Bốn URL/ID và nguồn semantic model | Mở từng report bằng Viewer |
| R13 | Một hình sơ đồ điều hướng nếu cần; không cần ảnh mỗi nút | Ma trận link→đích, video ngắn **sau khi dashboard chạy** nếu cần chứng minh thao tác | Click mọi link dưới Viewer |
| R14 | Biểu đồ/bảng độ trễ event→DB→visual | Timestamp ba lần đo và log `run_id`; video sau khi có dashboard nếu hữu ích | Kiểm không bấm refresh thủ công để thay thế auto-update |
| R15 | Bảng quyền và kết quả ba vai trò, ảnh đã che danh tính nếu cần | Ma trận expected/actual truy cập chéo, cấu hình RLS đã lược secret | Thử URL/filter/export, tài khoản Viewer thật |
| R16 | Ảnh bố cục mobile đại diện đủ bốn report | Danh sách thiết bị/kích thước và kết quả thao tác | Thử filter/navigation trên điện thoại |
| R17 | Slide PowerPoint là sản phẩm; không cần ảnh riêng | File slide và danh mục nguồn/hình | Rà font, chính tả, số hình/bảng |
| R18 | Báo cáo Word là sản phẩm; không cần ảnh riêng | File Word, trích dẫn, bảng số đo gốc | Rà bố cục, nguồn và số liệu |
| R19 | Không cần hình riêng nếu video/demo đã rõ | Kịch bản demo và bản ghi buổi trình bày nếu được phép | Chạy thử đủ điểm chạm |
| R20 | Ảnh Azure quota/region, IAM/cost và hoạt động nhóm **khi có thật**; chọn vài hình tổng hợp | Issue/PR/commit history, resource inventory, cost/quota export | Git branch, Python, SSD, `.venv`, tạo thư mục: chỉ kiểm nội bộ |

**Giai đoạn 01:** Chỉ cân nhắc ảnh Azure quota/region khi bảng quota hiện dữ liệu và ảnh/bảng kết quả Power BI POC nếu đã thử bằng tài khoản thật. Không chụp riêng Git branch, Python, RAM, SSD hay `.venv`; không yêu cầu video dashboard khi dashboard chưa tồn tại. Ghi kết quả kỹ thuật trong `stage_01_status.md`. Trước khi lưu ảnh, che email, ID, IP, bí mật và thông tin thanh toán.
