# Trạng thái Giai đoạn 01

**Cập nhật:** 15/11/2026. **Gate A: PENDING.** Phần chuẩn bị offline đã có; chưa chứng minh được dashboard SaaS đáp ứng cập nhật, chia sẻ/phân quyền và mobile, cũng chưa xác minh quota hai region Azure. Đây là trạng thái công việc, không phải điểm rubric. Các tiêu chí R01–R20 đều PENDING trong `rubric_mapping.md`.

## Kết quả đã kiểm tra

| Hạng mục | Kết quả quan sát | Trạng thái |
|---|---|---|
| Repository | `origin` đúng repository; ban đầu chỉ có `README.md`, working tree sạch. Đang ở `setup/project-scaffold`; chưa commit/push/merge và README không đổi. | PASS kiểm tra Git |
| Bảo vệ dữ liệu | `.gitignore` loại `.env`, `.venv`, dữ liệu raw, Docker volumes và video; `.env.example` chỉ có mật khẩu mẫu. Scan không thấy secret thật. | PASS kiểm tra offline |
| Mac | Apple M4, 10 lõi, RAM 16 GB, SSD còn khoảng 29–30 GiB. `sysctl` bị từ chối quyền; `memory_pressure` và `system_profiler` xác nhận RAM. | PASS khảo sát; SSD cần theo dõi |
| Python và công cụ | Python 3.12.15 và `.venv/bin/python` 3.12.15 chạy được; `python3` mặc định 3.14.7; Git 2.39.5, VS Code 1.146.0. | PASS kiểm tra phiên bản |
| Docker | Docker CLI 29.9.3 và `docker-compose` độc lập 5.7.1 có; `docker compose` không có, Colima chưa chạy, Docker Desktop không thấy trong `/Applications`. Chưa kéo image. | PENDING runtime |
| Power BI | Đăng nhập Service được bằng tài khoản trường; hồ sơ hiển thị **Free account**, chỉ thấy **My workspace**. Không bật trial, chưa tạo report, chưa thử ba Viewer/RLS/refresh/mobile. | PENDING; license hiện tại là trở ngại |
| Azure | Subscription **Azure for Students** Active; tài khoản hiện tại là Owner. Trang quota Compute báo provider chưa đăng ký cho subscription được chọn, bảng không có dữ liệu. Chưa kiểm hai region, credit, giá hoặc RBAC nhóm; không tạo resource. | PENDING quota/region |

Những thông tin máy/Git ở trên là kiểm tra kỹ thuật nội bộ; không cần ảnh riêng trong báo cáo. Dữ liệu tài khoản đã được lược email, tenant và subscription ID. Không có số liệu latency, benchmark hay chi phí dự án để công bố.

## Rủi ro và quyết định còn mở

| Vấn đề | Tác động và cách xử lý | Trạng thái |
|---|---|---|
| SSD, Docker và tương thích image/connector | Dùng sample nhỏ; đo SSD trước khi kéo image. Chọn runtime và kiểm Kafka/Flink/JDBC bằng smoke test ở GĐ03–06, không mặc nhiên dùng phiên bản trong kế hoạch. | OPEN |
| Power BI Free account, chưa có ba Viewer | Cần kiểm license/capacity của tác giả và người xem, quyền publish/share và ba tài khoản Viewer. Power BI vẫn là lựa chọn ưu tiên, chưa chốt hay đổi SaaS. | OPEN |
| Cập nhật gần thời gian thực | Tài liệu Microsoft nêu automatic page refresh DirectQuery trên shared capacity tối thiểu 30 phút; phải thử event → DB → visual trên workspace thật. Nếu không đạt, đánh giá SaaS khác có login và bảo vệ dữ liệu ở nguồn/server. | OPEN |
| Bốn report và nội dung lọc | Mặc định bốn report riêng. Rubric nêu tổng quan, chi tiết, filter 1, filter 2; kế hoạch dùng Overview/Product/Store/Time. Cần ánh xạ rõ hai bộ lọc và hỏi giảng viên trước khi dùng bốn page thay report. | OPEN |
| Azure quota/region/chi phí | Portal chưa hiện quota Compute. Chỉ kiểm tra khả năng đăng ký provider, quota từng region, VM/Blob/PostgreSQL, RBAC và giá; chưa thay đổi provider/quyền hay tạo resource. Budget là cảnh báo, không phải trần phí cứng. | OPEN |
| Dataset gốc và synthetic >4 GB | GĐ02 chọn nguồn có provenance; synthetic chỉ mở rộng có nhãn. Hỏi giảng viên có chấp nhận mốc >4 GB theo cách này không; GĐ10 phải chứng minh bytes và Flink thực xử lý. | OPEN |
| Bảo vệ bí mật và dữ liệu | Rà diff trước commit; không đưa `.env`, token, dữ liệu lớn hoặc ảnh chứa thông tin tài khoản lên GitHub. | OPEN liên tục |
| Cộng tác cloud | GitHub Issue/PR chỉ là minh chứng bổ trợ; R20 cần phân việc thật của ba người, Azure RBAC/cùng làm trên resource nếu triển khai cloud, chi phí và quota. | OPEN |

**Quyết định đã áp dụng:** dùng nhánh `setup/project-scaffold`; giữ README; dùng Python 3.12 hiện có; không cài hệ thống, không khởi động Docker/kéo image, không tạo Azure resource. **Quyết định chưa chốt:** dashboard SaaS, bốn report/page, hai region/SKU/ngân sách, synthetic >4 GB và runtime Docker cho GĐ03.

## Cộng tác tối thiểu

- Mỗi việc dùng nhánh riêng và PR liên kết Issue, ghi thay đổi, phép thử expected/actual, mã rubric và hạn chế. Thành viên khác review diff và kiểm secret trước merge. Chưa tạo Issue/Milestone/PR từ xa hoặc đổi quyền repository.
- Phân công **đề xuất**: Nguyên phụ trách hạ tầng/Kafka/Azure/benchmark; Ngân phụ trách dữ liệu/Flink/PostgreSQL/SQL; Thư phụ trách dashboard/RLS/mobile/báo cáo. Cả ba cùng review, demo và có đóng góp thực chất. Nhóm cần xác nhận phân công trước khi gán Issue.
- Backlog 12 giai đoạn nằm trong kế hoạch DOCX; chỉ tạo Issue/Milestone từ xa khi được người dùng cho phép và có việc thật để giao.

## Gate A và việc còn thiếu

- [x] Kiểm repo, nhánh, môi trường, `.venv`, bảo vệ file mẫu; kiến trúc và ma trận 20 tiêu chí tổng 10,0 điểm đã được kiểm tra cấu trúc.
- [ ] Xác minh license/capacity, quyền publish/share và ba Viewer; thử bốn report riêng, navigation, RLS, mobile và phép đo cập nhật. Hướng dẫn ở `../feasibility/powerbi_poc.md`.
- [ ] Xác minh quota vCPU và dịch vụ ở **hai region**, credit/ngân sách, giá SKU, quyền RBAC của ba thành viên. Hướng dẫn ở `../feasibility/azure_quota.md`.
- [ ] Nhận xác nhận giảng viên về bốn report, mức cập nhật chấp nhận và synthetic mở rộng cho mốc >4 GB.
- [ ] Ghi hoạt động cộng tác thật khi nhóm bắt đầu làm việc từ xa; chưa có bằng chứng để chấm R20.

**Minh chứng GĐ01 chỉ chụp khi có kết quả:** màn hình Azure quota/region đã che ID và màn hình/bảng kết quả POC Power BI đã che tài khoản. Chưa có dashboard chạy nên chưa cần video. Checklist hình/log cho toàn đồ án ở `rubric_mapping.md`.

Không đổi Gate A thành PASS chỉ vì đã tạo file hoặc đăng nhập thành công. Chưa bắt đầu GĐ02 và chưa phát sinh chi phí mới.
