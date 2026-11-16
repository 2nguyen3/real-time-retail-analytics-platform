# POC khả thi Power BI Service và dashboard SaaS

**Ngày lập:** 15/11/2026. **Kết luận:** PENDING. Đã đăng nhập Power BI Service qua Chrome bằng tài khoản trường có sẵn. Hồ sơ hiển thị **Free account**; danh sách workspace chỉ hiển thị **My workspace**. Đây là trở ngại hiện tại cho publish/share tới người khác theo tài liệu license; chưa thử tạo report, quyền share, RLS hay độ trễ vì chưa có nguồn dữ liệu và ba Viewer. Không bật Free trial. Kết quả quan sát đã được lược thông tin tài khoản trong `../plan/stage_01_status.md`. Tài liệu Microsoft nêu điều kiện chung, chưa chứng minh tenant nhóm đáp ứng rubric.

## Điều kiện cần khóa trước khi dùng Power BI

- Rubric yêu cầu bốn **report**, button/navigation, dữ liệu cập nhật, chia sẻ theo nhóm và mobile. Mặc định tạo bốn report riêng: tổng quan; chi tiết sản phẩm; lọc cửa hàng; lọc thời gian. Bốn page của một report chỉ dùng nếu giảng viên chấp thuận.
- [Tài liệu Microsoft về automatic page refresh](https://learn.microsoft.com/power-bi/create-reports/desktop-automatic-page-refresh): với shared capacity, DirectQuery có khoảng làm mới trang tối thiểu 30 phút. PPU/dedicated capacity có điều kiện khác tùy quản trị viên. DirectQuery không tự đồng nghĩa giao dịch xuất hiện gần tức thời; phải đo tại workspace thực tế.
- [Chia sẻ và license](https://learn.microsoft.com/en-us/power-bi/collaborate-share/service-share-dashboards): tác giả và người nhận thường cần Pro/PPU nếu không có capacity đủ điều kiện. Kiểm từng tài khoản và workspace, không suy từ email trường.
- [RLS](https://learn.microsoft.com/power-bi/service-admin-rls): RLS cần role trong semantic model và áp dụng cho người xem có workspace role Viewer; quyền cao hơn có thể vượt hạn chế. Chỉ lọc visual không phải kiểm soát truy cập.
- [Power BI Desktop](https://learn.microsoft.com/en-us/power-bi/fundamentals/desktop-get-the-desktop) yêu cầu Windows. Nhóm cần máy Windows/VM được phép hoặc xác nhận chức năng soạn model trong Service đủ cho POC.
- [PostgreSQL connector chung](https://learn.microsoft.com/en-us/power-query/connectors/postgresql) ghi hỗ trợ DirectQuery; [Azure Database for PostgreSQL connector riêng](https://learn.microsoft.com/en-us/power-query/connectors/azure-database-postgresql) chỉ liệt kê Import. Cần thử đúng connector/mode, network và gateway trong môi trường được phép trước khi chốt thiết kế refresh.

## Cách thực hiện POC bằng tài khoản của nhóm

Không nhập mật khẩu, token hoặc connection string vào repository. Dùng dữ liệu thử vài dòng không nhạy cảm, ghi `run_id`, `store_id`, `product_id`, `quantity`, `price`, `event_time` và expected revenue. Nếu dùng PostgreSQL cloud cho thử nghiệm, chỉ tạo sau khi người dùng duyệt chi phí; ở GĐ01 có thể kiểm tra cấu trúc report/quyền bằng dữ liệu mẫu nhỏ sẵn có.

1. **Đăng nhập và license:** vào Power BI Service bằng từng tài khoản nhóm; ghi loại license và workspace capacity vào bảng expected/actual. Chỉ chụp một ảnh đã che email/tenant ID nếu cần chứng minh kết quả POC. Kiểm nút tạo workspace, publish và share có sẵn, không suy từ trạng thái đăng nhập.
2. **Bốn report:** tạo bốn report **riêng** từ cùng một semantic model thử nhỏ; đặt tên `01 Overview`, `02 Product Detail`, `03 Store Filter`, `04 Time Filter`. Ghi bốn URL/ID, thử mở từng report bằng Viewer. Xác nhận với giảng viên nếu muốn một report bốn page.
3. **Điều hướng:** đặt button/link từ mỗi report tới report khác; ghi ma trận link→đích và kết quả click đủ bốn dưới Viewer. Chỉ cân nhắc video khi dashboard đã chạy và cần chứng minh thao tác cho R13/GĐ09. Kiểm đường dẫn không báo 403 và không làm lộ report ngoài quyền.
4. **Ba Viewer và RLS:** tạo/áp dụng role Admin, Regional Manager, Store Manager (hoặc ba nhóm tương đương), gán ba tài khoản thử có quyền Viewer. Dữ liệu mẫu phải có ít nhất hai store và hai region. So sánh expected/actual cho visual, filter, URL, export và quyền xem semantic model. Tài khoản Store Manager không được nhìn store khác.
5. **Refresh/latency:** kiểm workspace capacity và mode kết nối. Với một nguồn dữ liệu được phép ghi, phát sự kiện có ID riêng, ghi `sent_at`, lúc SQL DB thấy hàng và lúc visual tự đổi **không bấm Refresh**. Lặp ba lần, ghi đơn vị giây vào bảng kết quả; video chỉ hữu ích khi dashboard chạy thật. Nếu chưa có nguồn DB/connector thì đánh PENDING, không thay bằng refresh thủ công hay số mẫu giả.
6. **Mobile:** tạo mobile layout của từng report; mở bằng tài khoản Viewer trên điện thoại thật/ứng dụng Power BI, thử filter và navigation. Lưu ảnh bốn report đã che thông tin nhạy cảm.
7. **Kết nối Azure PostgreSQL:** chỉ khi Azure được duyệt và sẵn có, kiểm host/TLS/firewall/gateway, connector/mode và RLS. Không mở DB công khai chỉ để thử.

## Ma trận expected / actual

| Kiểm tra | Expected để cân nhắc GO | Actual đã quan sát | Trạng thái |
|---|---|---|---|
| Service sign-in và license tác giả | Tác giả truy cập, license đủ publish/share | Đăng nhập được; hồ sơ hiển thị Free account | FAIL điều kiện license hiện tại |
| Workspace capacity | Xác định capacity của workspace dùng cho POC | Chỉ thấy My workspace; chưa kiểm capacity | PENDING |
| Publish và share | Tác giả publish, ba Viewer mở được | Chưa thử; Free account chưa đủ căn cứ cho share workspace thường | PENDING |
| Bốn report riêng | Bốn URL/ID report và cùng nguồn dữ liệu | Chưa tạo | PENDING |
| Cross-report navigation | Mỗi button dẫn đúng report dưới Viewer | Chưa thử | PENDING |
| RLS theo store/region | Ba vai trò thấy đúng hàng, không vượt quyền qua URL/export | Chưa thử | PENDING |
| Connector PostgreSQL/DirectQuery | Mode, network và gateway chạy thật | Chưa có nguồn DB được duyệt | PENDING |
| Cập nhật mới | Ba lượt có thời gian event → DB → visual và mức chấp nhận của giảng viên | Chưa đo | PENDING |
| Mobile | Bốn report dùng được trên điện thoại | Chưa thử | PENDING |
| Windows Desktop | Có máy Windows/đường soạn model hợp lệ | Chưa xác nhận | PENDING |

## Phương án SaaS khác để nghiên cứu nếu Power BI không đạt

- **Metabase Cloud:** [row and column security](https://www.metabase.com/docs/latest/permissions/data-sandboxes) chỉ có ở Pro/Enterprise; cần kiểm giá/license, refresh, login, quyền chia sẻ và mobile bằng tài khoản thật. Chưa chọn.
- **Grafana Cloud:** có [quyền dashboard](https://grafana.com/docs/grafana/latest/administration/user-management/manage-dashboard-permissions/) và cấu hình [auto-refresh](https://grafana.com/docs/grafana-cloud/learn-and-build/visualizations/dashboards/build-dashboards/modify-dashboard-settings/), nhưng phải chứng minh bảo vệ dữ liệu **theo hàng/store ở backend hoặc DB**, không chỉ theo dashboard. Chưa chọn.

Không đổi sang SaaS khác chỉ dựa trên danh sách này. So sánh phải có thử nghiệm cùng bộ tiêu chí, chi phí/quyền và ý kiến giảng viên về bốn report/cập nhật.

## Quyết định Gate A của nhánh dashboard

**PENDING.** GO chỉ khi bốn report/navigation, cập nhật ở mức giảng viên chấp nhận, chia sẻ/RLS và mobile có bằng chứng thật; NO-GO khi phép thử xác định không đáp ứng. Tài liệu sản phẩm hoặc demo mẫu không thay kết quả của tenant nhóm. Ở GĐ01, lưu bảng expected/actual và một ảnh kết quả POC đã che danh tính nếu có; chưa yêu cầu video.
