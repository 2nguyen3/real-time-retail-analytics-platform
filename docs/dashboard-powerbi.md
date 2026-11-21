# Đặc tả dashboard Power BI

**Cập nhật:** 19/11/2026. Tài liệu hướng dẫn dựng dashboard (một report năm trang) từ dữ liệu thật trong PostgreSQL Azure. Các kết quả trong bảng minh chứng ở cuối chỉ được ghi PASS khi đã có phép thử thật. Không ghi mật khẩu, connection string hay email vào file này.

## 1. Nguồn dữ liệu

| Mục | Giá trị |
|---|---|
| Server | `<tên server>.postgres.database.azure.com`, cổng 5432 |
| Database | `retail_analytics`, bật SSL |
| Tài khoản | `retail_reader` (chỉ SELECT). Mật khẩu lấy từ `.env` local, khóa `AZURE_PG_READER_PASSWORD` |
| Run dùng cho dashboard | `s07_efde7a9e73_tenk` (10.000 dòng synthetic) |
| Firewall | Cần IP máy đang dùng nằm trong rule của server; Power BI Service chưa có đường vào (xem mục 7) |

**Số liệu thật của run (đọc 19/11/2026):** 5 cửa hàng, 400 dòng cửa hàng–sản phẩm, 3.334 dòng theo phút, `window_start` từ 2024-01-01 00:00 đến 2024-01-03 07:33 (UTC). Mỗi cửa hàng khoảng 2.000 giao dịch, doanh thu khoảng 588–608 nghìn (đơn vị USD mô phỏng). 80 sản phẩm, 8 nhóm hàng. Cột `store_region` hiện trống (0 vùng).

**Lưu ý quan trọng:**
- Database chứa nhiều run (kể cả run trùng nội dung như `cloud_run_01` và `s07_..._normal`). **Phải lọc theo một `run_id`**, nếu không doanh thu bị cộng nhiều lần.
- Dữ liệu là mô phỏng của tháng 01/2024, không phải thời điểm hiện tại. Trục thời gian sẽ hiển thị năm 2024.
- `window_start` lưu UTC (`timestamptz`). Giữ nguyên UTC trong Power Query để khỏi lệch giờ.

## 2. Power Query (Get data → PostgreSQL database, chế độ Import)

Tạo tham số `RunId` (Manage parameters, kiểu Text) với giá trị `s07_efde7a9e73_tenk`. Với từng bảng sales, thêm bước lọc theo tham số. Ví dụ cho `sales_by_store`:

```
let
  Source = PostgreSQL.Database("<tên server>.postgres.database.azure.com:5432", "retail_analytics"),
  T = Source{[Schema="public",Item="sales_by_store"]}[Data],
  Filtered = Table.SelectRows(T, each [run_id] = RunId)
in
  Filtered
```

Áp dụng tương tự cho `sales_by_store_product` và `sales_by_store_minute`. Hai bảng chiều `stores` và `products` lấy nguyên. Với `sales_by_store_minute`, thêm bước giữ UTC cho `window_start` (và `window_end`):

```
Table.TransformColumns(Filtered, {{"window_start", each DateTimeZone.RemoveZone(DateTimeZone.SwitchZone(_, 0)), type datetime}})
```

Khi đổi sang run khác chỉ cần sửa tham số `RunId`.

## 3. Mô hình (Model view)

Quan hệ nhiều–một, hướng lọc một chiều từ bảng chiều sang bảng sự kiện:

| Từ (nhiều) | Đến (một) |
|---|---|
| `sales_by_store[store_id]` | `stores[store_id]` |
| `sales_by_store_product[store_id]` | `stores[store_id]` |
| `sales_by_store_product[product_id]` | `products[product_id]` |
| `sales_by_store_minute[store_id]` | `stores[store_id]` |

## 4. Measure (mỗi bảng sự kiện có measure riêng, không dùng chung)

```
Total Revenue = SUM(sales_by_store[total_revenue])
Total Quantity = SUM(sales_by_store[total_quantity])
Transactions = SUM(sales_by_store[transaction_count])
Avg Revenue per Transaction = DIVIDE([Total Revenue], [Transactions])
Revenue Share = DIVIDE([Total Revenue], CALCULATE([Total Revenue], ALL(stores)))

Product Revenue = SUM(sales_by_store_product[total_revenue])
Product Quantity = SUM(sales_by_store_product[total_quantity])

Minute Revenue = SUM(sales_by_store_minute[total_revenue])
Minute Transactions = SUM(sales_by_store_minute[transaction_count])
```

Cột tính bổ sung trong `sales_by_store_minute` để vẽ theo giờ:
```
Hour = FORMAT(sales_by_store_minute[window_start], "yyyy-MM-dd HH:00")
Date = DATE(YEAR(sales_by_store_minute[window_start]), MONTH(sales_by_store_minute[window_start]), DAY(sales_by_store_minute[window_start]))
```

## 5. Thiết kế: một dashboard, một report, năm trang

**Yêu cầu của thầy (nguyên văn):** "Deploy 1 dashboard lên SaaS, ít nhất có 4 report: trang tổng quan, trang chi tiết, trang filter 1, filter 2... Sử dụng các button, navigation để điều hướng giữa các report."

**Quyết định của nhóm (19/11/2026):** làm **một report gồm năm trang** và coi mỗi trang là một "report" theo cách nói của thầy. Cách hiểu này chưa được thầy xác nhận; nếu thầy hiểu "report" là file riêng thì phải tách lại (mô hình và trang giữ nguyên được, chỉ đổi cách đóng gói).

### 5.1 Ngôn ngữ thiết kế (light mode)

| Vai trò màu | Mã màu | Dùng cho |
|---|---|---|
| Chính | `#21145F` | Thanh điều hướng bên trái, tiêu đề, cột/đường chính |
| Chính nhạt | `#6C5CE7` | Chuỗi dữ liệu thứ hai, trạng thái chọn |
| Nhấn bán hàng | `#F26B3A` | Điểm cần chú ý (đỉnh doanh thu, top 1). Chỉ dùng cho hình lớn, không dùng làm màu chữ nhỏ |
| Tăng / tốt | `#1E9E6A` | Chỉ số vượt trung bình |
| Giảm / kém | `#D64545` | Chỉ số dưới trung bình |
| Nền trang | `#F7F6FB` | Nền canvas |
| Thẻ | `#FFFFFF` | Nền khung visual, viền `#E4E1F2` |
| Chữ | `#1B1740` (chính), `#6B6889` (phụ) | |

Khổ canvas 1280 × 720 (16:9). Font Segoe UI. Kiểm tra độ tương phản chữ trên nền khi dựng (đặc biệt chữ trắng trên `#21145F` và chữ trong slicer).

### 5.2 Bố cục chung cho cả năm trang

- **Cột trái rộng khoảng 200 px, nền `#21145F`:** tên dashboard, rồi **năm nút điều hướng trang** (loại *Page navigation*, trang đang xem được tô sáng), rồi **bộ lọc chung** đặt ngay dưới nút điều hướng.
- **Bộ lọc chung áp dụng cho cả năm trang:** Vùng (`store_region`), Cửa hàng (`store_id`), Nhóm hàng (`category_id`), Ngày (`Date`). Dùng *Sync slicers* (View → Sync slicers) để mỗi slicer đồng bộ và hiển thị trên cả năm trang. Phải kiểm tra bộ lọc vẫn giữ khi chuyển trang.
- **Vùng nội dung bên phải:** hàng tiêu đề (câu hỏi của trang), một dòng kết luận ngắn, rồi thẻ KPI và biểu đồ.
- Tiêu đề động theo phạm vi người xem: `SELECTEDVALUE(stores[store_region], "Toàn chuỗi")`.

### 5.3 Câu chuyện năm trang (storytelling)

Mạch kể: **Tình hình chung → Ở đâu → Bán gì → Khi nào → Bằng chứng và việc cần làm.**

| # | Tên trang (nút) | Câu hỏi | Nội dung chính | Ánh xạ yêu cầu thầy |
|---|---|---|---|---|
| 1 | **Tổng quan** | Chuỗi đang bán thế nào? | Thẻ Total Revenue, Total Quantity, Transactions, Avg Revenue per Transaction; đường doanh thu theo ngày; cột doanh thu theo cửa hàng; một dòng nhận xét | Trang tổng quan |
| 2 | **Cửa hàng** | Cửa hàng nào kéo doanh thu? | Xếp hạng cửa hàng, tỷ trọng (Revenue Share), so với trung bình chuỗi, nhóm theo vùng | Trang filter 1 |
| 3 | **Sản phẩm** | Bán gì nhiều nhất? | Top 10 sản phẩm, doanh thu theo nhóm hàng, độ tập trung (top 10 chiếm bao nhiêu %) | Trang filter 2 |
| 4 | **Thời gian** | Khi nào bán tốt? | Đường doanh thu theo giờ, giờ cao điểm, so sánh các ngày | |
| 5 | **Chi tiết** | Bằng chứng và việc cần làm | Bảng cửa hàng × sản phẩm đủ số liệu, có sắp xếp; nút quay về từng trang | Trang chi tiết |

**Mỗi trang kết thúc bằng một nút "Tiếp theo" dẫn tới trang kế**, để người xem đi hết mạch kể mà không phải nhìn thanh điều hướng.

### 5.4 Điều chỉnh theo vai trò người xem (khớp ba role RLS ở mục 6)

| Vai trò | Quan tâm | Họ thấy gì |
|---|---|---|
| Admin (trụ sở) | Toàn chuỗi, vùng và cửa hàng nào tốt/kém | Cả năm trang, xếp hạng toàn chuỗi |
| Quản lý vùng | Các cửa hàng trong vùng | Dữ liệu chỉ trong vùng; trang Cửa hàng xếp hạng các cửa hàng của vùng |
| Quản lý cửa hàng | Sản phẩm và giờ cao điểm của cửa hàng mình | Dữ liệu chỉ cửa hàng mình; trang Sản phẩm và Thời gian là trọng tâm |

RLS lọc dữ liệu ở máy chủ nên các hàm `ALL(stores)` chỉ thấy phần được phép (quản lý cửa hàng không thấy chuỗi để so sánh). Cần thiết kế các thẻ "so với trung bình" cho phù hợp, và ghi chú rõ phạm vi so sánh trên trang.

### 5.5 Nút và điều hướng (R13)

- Cột trái: năm nút *Page navigation* (chuyển trang trong cùng report).
- Mỗi trang: nút "Tiếp theo" và (ở trang 5) nút quay về từng trang.
- Kiểm tra dưới quyền Viewer: mọi nút dẫn đúng trang, không báo lỗi, bộ lọc chung được giữ.

## 6. Phân quyền theo hàng (RLS, R15)

Tạo role ở Modeling → Manage roles, lọc trên bảng `stores` (bộ lọc lan sang các bảng sự kiện qua quan hệ):

| Role | Bảng | Biểu thức DAX |
|---|---|---|
| `Admin` | (không lọc) | |
| `Region_North` | `stores` | `[store_region] = "North"` |
| `Store_S001` | `stores` | `[store_id] = "S001"` |

- **Điều kiện:** `store_region` đang trống, nên role vùng chưa lọc được gì. Cần gán vùng cho cửa hàng (dữ liệu demo) hoặc dùng nguồn có vùng thật.
- **Trên Service:** vào semantic model → Security, gán tài khoản vào role. RLS chỉ áp dụng cho người có role **Viewer** của workspace. Admin, Member, Contributor có thể bỏ qua RLS.
- **Kiểm tra:** dùng View as ở Desktop và ở Service, thử URL trực tiếp và Export để chắc người xem không vượt quyền. Lọc visual không phải là kiểm soát truy cập.

## 7. Cập nhật dữ liệu (R14) và rủi ro

- Power BI Service nằm ngoài firewall PostgreSQL, nên **refresh tự động trên Service sẽ lỗi** nếu không mở đường (cho phép dịch vụ Azure truy cập, hoặc dùng gateway). Mỗi hướng có đánh đổi bảo mật; chọn và ghi lại cùng kết quả thử.
- Tài liệu Microsoft nêu automatic page refresh với DirectQuery trên shared capacity tối thiểu 30 phút. "Tức thời" có thể không đạt; kết quả đo thật mới là minh chứng.
- Quy trình đo (làm ba lần, không bấm Refresh thủ công): phát một nhóm sự kiện có `run_id` riêng, ghi `sent_at`, thời điểm hàng xuất hiện trong PostgreSQL, thời điểm visual tự đổi. Cần VM bật để chạy Producer và Flink (tốn tiền), nên làm một đợt gọn.

## 8. Mobile (R16)

Với mỗi trang: View → Mobile layout, kéo các visual chính vào khung điện thoại (thẻ tổng, một biểu đồ, slicer chính). Mở bằng ứng dụng Power BI trên điện thoại thật bằng tài khoản Viewer, thử slicer và nút điều hướng.

## 9. Bảng minh chứng (điền khi có kết quả thật)

| Hạng mục | Expected | Actual | Trạng thái |
|---|---|---|---|
| Workspace, publish, chia sẻ cho Viewer | Tạo workspace, publish `.pbix`, Viewer mở xem được | Đã thử: tạo workspace `retail-analytics`, publish một file thử, tài khoản khác role Viewer chỉ xem được | PASS cho phép thử license; chưa có ảnh |
| Kết nối Azure PostgreSQL bằng `retail_reader` | Desktop đọc được ba bảng sự kiện | | PENDING |
| Một report năm trang cùng một nguồn | Một URL/ID, năm trang | | PENDING |
| Điều hướng và bộ lọc chung | Năm nút ở cột trái và nút "Tiếp theo" dẫn đúng; bộ lọc giữ khi chuyển trang | | PENDING |
| RLS | Ba role thấy đúng hàng, không vượt quyền qua URL/export | | PENDING |
| Refresh trên Service | Dữ liệu cập nhật không cần bấm tay | | PENDING |
| Cập nhật event → DB → visual | Ba lượt đo, đơn vị giây | | PENDING |
| Mobile | Năm trang dùng được trên điện thoại thật | | PENDING |
