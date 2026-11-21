# Report Spec

**Trạng thái:** ĐÃ DUYỆT (19/11/2026). Đang triển khai.

**Điều chỉnh thiết kế theo yêu cầu của người dùng (20/11/2026), thay thế các mục tương ứng trong hợp đồng YAML bên dưới:**
- Đổi giao diện theo mẫu người dùng gửi: khung bo tròn nhiều lớp, thẻ "Menu" trắng bên trái chứa nút điều hướng dạng viên thuốc và bộ lọc dạng danh sách có ô tick (Vùng, Cửa hàng; Nhóm hàng dạng dropdown), thẻ KPI và biểu đồ trắng bo góc có bóng đổ, bản đồ nhiệt cho hai ma trận. Bảng màu indigo `#21145F` giữ nguyên.
- Tiêu đề trang đổi thành `Retail Analytics Dashboard - <tên trang>`, bỏ các tiêu đề dạng câu hỏi.
- **Bỏ nút "Tiếp theo"** (đã có thanh điều hướng).
- **Bỏ ô kết luận** (`overview_takeaway`); ô trống của trang Tổng quan thay bằng ma trận "Tóm tắt theo vùng và cửa hàng". Measure `Takeaway Overview` còn trong mô hình nhưng không dùng nữa.
- Thẻ KPI bỏ thanh nhấn màu, nhãn đặt phía trên giá trị. Bộ lọc Ngày chỉ có ở trang Thời gian, đặt ở góc phải trên.

**Điều chỉnh thiết kế lần 2 (20/11/2026), theo báo cáo mẫu "Supply Chain & Sales Analytics" người dùng gửi ảnh:** thanh bên trắng (tên, 5 nút điều hướng viên thuốc, bộ lọc dạng chọn Vùng/Cửa hàng/Nhóm hàng, nút "Xóa bộ lọc"); dải tiêu đề indigo chứa hàng **5 thẻ KPI**; mỗi trang 3 biểu đồ ở hàng trên và 2 ở hàng dưới (biểu đồ có nhãn, màu indigo kèm điểm nhấn vàng cam, ma trận tô màu theo giá trị); toàn bộ tên hiển thị tiếng Việt. Mô hình thêm hai measure (`Store Count`, `Minute Transactions`) và bỏ `Takeaway Overview`. Ghi chú về bố cục lưới ở YAML bên dưới đã lỗi thời; thiết kế hiện hành nằm trong bộ sinh báo cáo và các file PBIR.

**Ghi chú triển khai:** khi viết mô hình (TMDL) tên đối tượng được đổi cho dễ đọc theo hướng dẫn của Microsoft: bảng `Store`, `Product`, `Sales`, `Sales by Minute`; cột `Store ID`, `Region`, `Product ID`, `Category`, `Date`, `Hour`; role `Admin`, `Region North`, `Store S001`. Thiết kế, bố cục và nội dung từng trang không đổi. Không ghi mật khẩu, connection string hay email vào file này.

## Report identity
- Report name: Retail Analytics Dashboard (tên file dự kiến `RetailAnalytics`)
- Semantic model: `RetailAnalytics.SemanticModel` (chưa tồn tại; tạo sau khi duyệt)
- Audience: Ban điều hành chuỗi; quản lý vùng; quản lý cửa hàng (ba vai trò, khớp ba role RLS)
- Primary purpose: Theo dõi doanh thu bán lẻ và trả lời theo mạch kể: tình hình chung, ở đâu, bán gì, khi nào, bằng chứng chi tiết
- Delivery target: PBIP cục bộ trong `dashboard/`; người dùng tự publish lên workspace `retail-analytics`

## Semantic model binding
- Entry mode: No Model -> Local Model (mô hình tạo bằng TMDL trong `dashboard/RetailAnalytics.SemanticModel`, sau khi duyệt)
- Workspace name / ID, Model ID: không áp dụng (chưa publish)
- Model name: RetailAnalytics
- connectionString: Local Model, `byPath ../RetailAnalytics.SemanticModel`

## User decisions and constraints
- Scope: một dashboard, **một report năm trang**. Yêu cầu của thầy: "Deploy 1 dashboard lên SaaS, ít nhất có 4 report: trang tổng quan, trang chi tiết, trang filter 1, filter 2... dùng button, navigation để điều hướng giữa các report". Nhóm coi mỗi trang là một "report" (thầy chưa xác nhận).
- Page count: 5 (Tổng quan, Cửa hàng = filter 1, Sản phẩm = filter 2, Thời gian, Chi tiết)
- Interactivity: thanh điều hướng bên trái (page navigator) kèm bộ lọc chung đồng bộ giữa các trang (Sync slicers); mỗi trang có nút "Tiếp theo" (PageNavigation) để đi hết mạch kể
- Design direction: storytelling, light mode, màu chính `#21145F`, màu hợp bán hàng, phù hợp vai trò người xem
- Publishing: người dùng tự làm; không publish từ phiên này
- Tooling: Power BI Desktop (chưa mở), `powerbi-report-author` CLI, modeling MCP (chỉ đọc), TMDL
- Model edit permissions: được tạo mô hình, quan hệ, measure, 3 role RLS bằng TMDL trong `dashboard/`
- Accessibility: tương phản đạt WCAG AA cho mọi cặp chữ/nền; alt text cho mọi biểu đồ; không dùng màu đơn độc để truyền nghĩa
- Data caveats:
  - Dữ liệu là mô phỏng (synthetic), đơn vị USD mô phỏng, thời gian rơi vào 01–03/01/2024 (UTC), không phải thời điểm hiện tại.
  - Mô hình chỉ nạp **một run**: `run_id = s07_efde7a9e73_tenk` (10.000 dòng, 5 cửa hàng, 80 sản phẩm, 8 nhóm hàng). Cộng nhiều run sẽ nhân đôi số liệu.
  - Các bảng tổng hợp có độ chi tiết khác nhau: chỉ `sales_by_store_minute` có thời gian; `sales_by_store` không có sản phẩm. Vì vậy mọi trang trừ "Thời gian" dùng `sales_by_store_product` làm bảng sự kiện chính (cùng tổng doanh thu) để các bộ lọc Vùng, Cửa hàng, Nhóm hàng chạy đúng trên mọi trang. Bảng `sales_by_store` không đưa vào mô hình.
  - Bộ lọc **Ngày** chỉ có ý nghĩa với dữ liệu theo phút, nên chỉ đặt ở trang "Thời gian". Biểu đồ xu hướng ở trang "Tổng quan" dùng bảng theo phút nên chịu ảnh hưởng của Vùng và Cửa hàng, **không** chịu ảnh hưởng của Nhóm hàng.
  - `store_region` là nhãn demo gán cho 5 cửa hàng (S001–S003 North, S004–S005 South), không phải dữ liệu nguồn.
  - Ở vai trò quản lý cửa hàng, RLS chỉ cho thấy cửa hàng của họ nên các thẻ "so với trung bình chuỗi" phải ghi rõ phạm vi so sánh.

## Narrative
- Core story: Chuỗi đang bán thế nào -> cửa hàng nào kéo doanh thu -> sản phẩm nào bán chạy -> bán vào giờ nào -> bằng chứng chi tiết để hành động.
- Audience promise: Mỗi trang trả lời đúng một câu hỏi, kết thúc bằng nút dẫn sang trang kế.
- Key questions answered: Tổng doanh thu và đến từ đâu? Cửa hàng nào tốt/kém hơn trung bình? Sản phẩm và nhóm hàng nào dẫn đầu? Giờ cao điểm là khi nào? Cửa hàng nào bán sản phẩm nào, bao nhiêu?

## Design identity
- Tone: Corporate retail indigo (nền sáng, dữ liệu là trung tâm, nhấn cam cho điểm đáng chú ý)
- Signature: cột điều hướng indigo `#21145F` bên trái, chứa tên dashboard, điều hướng trang và bộ lọc chung đồng bộ; mỗi trang mở đầu bằng tiêu đề dạng câu hỏi
- Brownfield delta: không áp dụng (greenfield)

## Page plan
1. **Tổng quan** (nhãn nút "Tổng quan")
   - Archetype: Executive Summary
   - Layout variant: A. Variant_rationale: trang mở đầu cần dải KPI, xu hướng và một nhận định, không cần bảng chi tiết.
   - Purpose: Bức tranh chung của chuỗi
   - Visuals: 4 thẻ KPI; đường doanh thu theo ngày; cột doanh thu theo cửa hàng; vành khuyên theo nhóm hàng; ô nhận định (textbox gắn measure)
   - Fields/measures: Sales[Revenue], Sales[Quantity], Sales[Transactions], Sales[Avg Revenue per Transaction], 'Sales by Minute'[Minute Revenue], Store[Store ID], Product[Category], [Takeaway Overview]
   - Slicers/interactions: Vùng, Cửa hàng, Nhóm hàng (đồng bộ)
2. **Cửa hàng** (filter 1)
   - Archetype: Comparative Benchmark. Layout variant: B. Variant_rationale: so sánh năm thực thể cùng thang đo, cần một xếp hạng chiếm ưu thế.
   - Purpose: Cửa hàng nào kéo doanh thu, so với trung bình
   - Visuals: 4 thẻ KPI; xếp hạng cửa hàng; so sánh vùng; ma trận cửa hàng x nhóm hàng
3. **Sản phẩm** (filter 2)
   - Archetype: Analytical Canvas. Layout variant: A. Variant_rationale: hai góc nhìn (sản phẩm, nhóm hàng) cộng bảng đối chiếu.
   - Purpose: Sản phẩm và nhóm hàng bán chạy
   - Visuals: 4 thẻ KPI; top 10 sản phẩm; doanh thu theo nhóm hàng; bảng sản phẩm
4. **Thời gian**
   - Archetype: Analytical Canvas. Layout variant: B. Variant_rationale: dữ liệu theo phút cần xu hướng, so sánh ngày và bản đồ nhiệt giờ x ngày.
   - Purpose: Giờ cao điểm và xu hướng
   - Visuals: 4 thẻ KPI; đường doanh thu theo giờ; so sánh theo ngày; ma trận nhiệt giờ x ngày
   - Slicers: Vùng, Cửa hàng, Ngày (không có Nhóm hàng vì dữ liệu theo phút không có sản phẩm)
5. **Chi tiết**
   - Archetype: Analytical Canvas. Layout variant: C. Variant_rationale: trang bằng chứng, bảng là trung tâm.
   - Purpose: Bằng chứng cửa hàng x sản phẩm đầy đủ số liệu
   - Visuals: 4 thẻ KPI; bảng chi tiết (hero); doanh thu theo cửa hàng và theo nhóm hàng cho phần đang lọc

## Design system summary
- Theme name + base palette: `RetailIndigo`: chính `#21145F`, chính nhạt `#6C5CE7`, nhấn `#F26B3A`, tốt `#1E9E6A`, kém `#D64545`, trung tính `#8A87A3`; nền trang `#F7F6FB`, thẻ `#FFFFFF`, viền `#E4E1F2`
- Color semantics: Revenue = `#21145F`; Quantity = `#6C5CE7`; Transactions = `#F26B3A`; Avg Revenue per Transaction = `#8A87A3`; xanh/đỏ chỉ dùng cho so với trung bình (tốt/kém); cam chỉ dùng cho hình lớn hoặc điểm nhấn (thanh top 1, thanh accent của thẻ), không làm màu chữ nhỏ
- Typography pairing: Segoe UI Semibold (tiêu đề) + Segoe UI (nội dung), chữ số cùng độ rộng
- Layout pattern: canvas FHD 1920 x 1080, lưới 12 x 12, lề 32, khoảng cách 24; cột trái 2 cột (indigo) + vùng nội dung 10 cột
- Accessibility commitments: WCAG AA cho mọi cặp chữ/nền (đặc biệt chữ trắng trên `#21145F` và chữ trong slicer); alt text cho mọi biểu đồ; thứ tự tab theo mạch kể

## Model requirements
- Existing measures: không có (chưa có mô hình)
- New tables (từ PostgreSQL `retail_analytics`, Import, lọc tham số `RunId = s07_efde7a9e73_tenk`): `Stores` (stores), `Products` (products), `Sales` (sales_by_store_product), `SalesByMinute` (sales_by_store_minute)
- New measures: `Sales[Revenue]`, `Sales[Quantity]`, `Sales[Transactions]`, `Sales[Avg Revenue per Transaction]`, `Sales[Revenue Share]`, `Sales[Revenue vs Store Avg]`, `Sales[Store Rank]`, `Sales[Top 10 Product Share]`, `Sales[Distinct Products]`, `Sales[Takeaway Overview]`, `'Sales by Minute'[Minute Revenue]`, `'Sales by Minute'[Avg Revenue per Hour]`, `'Sales by Minute'[Peak Hour Revenue]`, `'Sales by Minute'[Busiest Hour]`
- Cột `Date` và `Hour` của `Sales by Minute` được tạo trong Power Query (M), không dùng cột tính DAX
- Relationship/sort requirements: `Sales[store_id]` -> `Store[Store ID]`; `Sales[product_id]` -> `Product[Product ID]`; `'Sales by Minute'[store_id]` -> `Store[Store ID]`; nhiều–một, một chiều từ bảng chiều sang bảng sự kiện
- Security roles (RLS): `Admin` (không lọc); `Region North` (`Store[Region] = "North"`); `Store S001` (`Store[Store ID] = "S001"`). RLS chỉ áp dụng cho người có role Viewer của workspace.
- Quản lý thông tin đăng nhập: mật khẩu `retail_reader` không nằm trong file; người dùng nhập khi Desktop yêu cầu ở lần Refresh đầu.

## Canonical design contract

```yaml
Design Brief:
  generated_by: powerbi-report-cli
  contract_version: 1
  mode: greenfield
  design_identity:
    tone: "Corporate retail indigo: nền sáng, dữ liệu là trung tâm, nhấn cam cho điểm đáng chú ý, chữ Segoe UI, mật độ vừa"
    signature: "Cột điều hướng indigo #21145F bên trái chứa tên dashboard, điều hướng trang và bộ lọc chung đồng bộ; mỗi trang mở đầu bằng tiêu đề dạng câu hỏi"
  archetype: Executive Summary
  navigation_model: page_navigator
  color_map:
    - measure: Sales[Revenue]
      color: "#21145F"
      tint: "#E6E3F5"
    - measure: Sales[Quantity]
      color: "#6C5CE7"
      tint: "#ECE9FD"
    - measure: Sales[Transactions]
      color: "#F26B3A"
      tint: "#FDE7DD"
    - measure: Sales[Avg Revenue per Transaction]
      color: "#8A87A3"
      tint: "#ECEBF1"
  pages:
    - name: Tổng quan
      role: landing
      archetype: Executive
      layout_variant: A
      variant_rationale: "Trang mở đầu cần dải KPI, xu hướng và một nhận định ngắn, không cần bảng chi tiết."
      navigation:
        - element: page_navigator
          action: PageNavigation
          label: "Điều hướng 5 trang"
        - element: button
          action: PageNavigation
          target: Cửa hàng
          label: "Tiếp theo: Cửa hàng nào kéo doanh thu"
      page_background: "#F7F6FB"
      layout_summary: "Cột trái indigo (tên, điều hướng, 3 bộ lọc); header có tiêu đề và nút tiếp theo; dải 4 thẻ KPI; xu hướng và xếp hạng cửa hàng; vành khuyên nhóm hàng và ô nhận định."
      layout_contract:
        canvas: { width: 1920, height: 1080, margin: 32, gutter: 24, snap: 8 }
        grid:
          columns: 12
          rows: 12
          regions:
            brand:        [1,  1,  3,  2]
            nav_rail:     [1,  2,  3,  6]
            filter_rail:  [1,  6,  3, 13]
            header:       [3,  1, 11,  2]
            next_nav:     [11, 1, 13,  2]
            kpis:         [3,  2, 13,  4]
            trend:        [3,  4,  8,  9]
            store_rank:   [8,  4, 13,  9]
            mix:          [3,  9,  8, 13]
            takeaway:     [8,  9, 13, 13]
        placements:
          - id: brand_title
            region: brand
            kind: textbox
            text: "Retail Analytics"
            purpose: "Tên dashboard ở đầu cột điều hướng."
          - id: page_navigator
            region: nav_rail
            kind: pageNavigator
            purpose: "Chuyển giữa 5 trang; trang hiện tại được tô sáng."
          - id: region_slicer
            region: filter_rail
            kind: slicer
            field_bindings: Store[Region]
            slicer_type: dropdown
            slot: 1
            of: 3
          - id: store_slicer
            region: filter_rail
            kind: slicer
            field_bindings: Store[Store ID]
            slicer_type: dropdown
            slot: 2
            of: 3
          - id: category_slicer
            region: filter_rail
            kind: slicer
            field_bindings: Product[Category]
            slicer_type: dropdown
            slot: 3
            of: 3
          - id: page_title
            region: header
            kind: textbox
            text: "Toàn chuỗi đang bán thế nào và doanh thu đến từ đâu?"
            purpose: "Nêu câu hỏi của trang trước mọi biểu đồ."
          - id: next_button
            region: next_nav
            kind: actionButton
            purpose: "Dẫn sang trang Cửa hàng."
          - id: revenue_card
            region: kpis
            kind: cardVisual
            purpose: "Tổng doanh thu là bao nhiêu?"
            field_bindings: Sales[Revenue]
            color_strategy: measure_match
            slot: 1
            of: 4
          - id: quantity_card
            region: kpis
            kind: cardVisual
            purpose: "Bán được bao nhiêu sản phẩm?"
            field_bindings: Sales[Quantity]
            color_strategy: measure_match
            slot: 2
            of: 4
          - id: transactions_card
            region: kpis
            kind: cardVisual
            purpose: "Có bao nhiêu dòng giao dịch?"
            field_bindings: Sales[Transactions]
            color_strategy: measure_match
            slot: 3
            of: 4
          - id: avg_txn_card
            region: kpis
            kind: cardVisual
            purpose: "Giá trị trung bình mỗi giao dịch?"
            field_bindings: Sales[Avg Revenue per Transaction]
            color_strategy: measure_match
            slot: 4
            of: 4
          - id: revenue_trend
            region: trend
            kind: lineChart
            purpose: "Doanh thu biến động thế nào theo ngày?"
            field_bindings: { Category: "'Sales by Minute'[Date]", Y: "'Sales by Minute'[Minute Revenue]" }
            color_strategy: measure_match
          - id: store_revenue
            region: store_rank
            kind: barChart
            purpose: "Cửa hàng nào có doanh thu cao nhất?"
            field_bindings: { Category: "Store[Store ID]", Y: "Sales[Revenue]" }
            sort_policy: value_desc
            color_strategy: measure_match
          - id: category_mix
            region: mix
            kind: donutChart
            purpose: "Nhóm hàng nào chiếm bao nhiêu phần doanh thu?"
            field_bindings: { Category: "Product[Category]", Y: "Sales[Revenue]" }
            sort_policy: value_desc
            color_strategy: unique
          - id: overview_takeaway
            region: takeaway
            kind: textbox
            purpose: "Nhận định ngắn cho người xem."
            field_bindings: Sales[Takeaway Overview]
            insight_basis: "Cửa hàng dẫn đầu chiếm bao nhiêu % doanh thu và cao hơn trung bình cửa hàng bao nhiêu; phạm vi so sánh nêu rõ theo RLS."
            callout_value_basis: "Tỷ trọng % và chênh lệch so với trung bình, không lặp giá trị tuyệt đối đã vẽ ở biểu đồ bên cạnh."
        space_audit:
          content_cell_count: 110
          placed_cell_count: 110
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region:
            name: trend
            pct_of_content: 23
          balance_rationale: "Dải KPI 2 hàng, hai biểu đồ chính cân nhau và hai ô phụ (nhóm hàng, nhận định) lấp kín vùng nội dung; không có dải trống."
    - name: Cửa hàng
      role: detail
      archetype: Comparative
      layout_variant: B
      variant_rationale: "So sánh năm cửa hàng cùng thang đo, cần một xếp hạng chiếm ưu thế."
      navigation:
        - element: page_navigator
          action: PageNavigation
          label: "Điều hướng 5 trang"
        - element: button
          action: PageNavigation
          target: Sản phẩm
          label: "Tiếp theo: Sản phẩm nào bán chạy"
      page_background: "#F7F6FB"
      layout_summary: "Cùng cột trái; dải 4 thẻ KPI; xếp hạng cửa hàng chiếm bên trái; so sánh vùng và ma trận cửa hàng x nhóm hàng bên phải."
      layout_contract:
        canvas: { width: 1920, height: 1080, margin: 32, gutter: 24, snap: 8 }
        grid:
          columns: 12
          rows: 12
          regions:
            brand:        [1,  1,  3,  2]
            nav_rail:     [1,  2,  3,  6]
            filter_rail:  [1,  6,  3, 13]
            header:       [3,  1, 11,  2]
            next_nav:     [11, 1, 13,  2]
            kpis:         [3,  2, 13,  4]
            ranking:      [3,  4,  8, 13]
            region_compare: [8, 4, 13,  8]
            store_category: [8, 8, 13, 13]
        placements:
          - id: brand_title
            region: brand
            kind: textbox
            text: "Retail Analytics"
            purpose: "Tên dashboard ở đầu cột điều hướng."
          - id: page_navigator
            region: nav_rail
            kind: pageNavigator
            purpose: "Chuyển giữa 5 trang; trang hiện tại được tô sáng."
          - id: region_slicer
            region: filter_rail
            kind: slicer
            field_bindings: Store[Region]
            slicer_type: dropdown
            slot: 1
            of: 3
          - id: store_slicer
            region: filter_rail
            kind: slicer
            field_bindings: Store[Store ID]
            slicer_type: dropdown
            slot: 2
            of: 3
          - id: category_slicer
            region: filter_rail
            kind: slicer
            field_bindings: Product[Category]
            slicer_type: dropdown
            slot: 3
            of: 3
          - id: page_title
            region: header
            kind: textbox
            text: "Cửa hàng nào đang kéo doanh thu của chuỗi?"
            purpose: "Nêu câu hỏi của trang trước mọi biểu đồ."
          - id: next_button
            region: next_nav
            kind: actionButton
            purpose: "Dẫn sang trang Sản phẩm."
          - id: store_revenue_card
            region: kpis
            kind: cardVisual
            purpose: "Doanh thu của phần đang lọc là bao nhiêu?"
            field_bindings: Sales[Revenue]
            color_strategy: measure_match
            slot: 1
            of: 4
          - id: share_card
            region: kpis
            kind: cardVisual
            purpose: "Phần đang lọc chiếm bao nhiêu % doanh thu?"
            field_bindings: Sales[Revenue Share]
            comparison_basis: "Tỷ trọng trên tổng trong phạm vi người xem được phép thấy"
            color_strategy: measure_match
            slot: 2
            of: 4
          - id: vs_avg_card
            region: kpis
            kind: cardVisual
            purpose: "Cao hay thấp hơn trung bình cửa hàng?"
            field_bindings: Sales[Revenue vs Store Avg]
            comparison_basis: "Trung bình các cửa hàng trong phạm vi RLS"
            color_strategy: semantic
            slot: 3
            of: 4
          - id: rank_card
            region: kpis
            kind: cardVisual
            purpose: "Xếp hạng doanh thu trong các cửa hàng được phép thấy?"
            field_bindings: Sales[Store Rank]
            color_strategy: measure_match
            slot: 4
            of: 4
          - id: store_ranking
            region: ranking
            kind: barChart
            purpose: "Thứ tự doanh thu các cửa hàng và cửa hàng nào cao hơn trung bình?"
            field_bindings: { Category: "Store[Store ID]", Y: "Sales[Revenue]" }
            sort_policy: value_desc
            color_strategy: semantic
          - id: region_column
            region: region_compare
            kind: clusteredColumnChart
            purpose: "Vùng nào đóng góp nhiều hơn?"
            field_bindings: { Category: "Store[Region]", Y: "Sales[Revenue]" }
            sort_policy: value_desc
            color_strategy: measure_match
          - id: store_category_matrix
            region: store_category
            kind: pivotTable
            purpose: "Mỗi cửa hàng mạnh ở nhóm hàng nào?"
            field_bindings: { Rows: "Store[Store ID]", Columns: "Product[Category]", Values: "Sales[Revenue]" }
            sort_policy: natural_order
            color_strategy: gradient
        space_audit:
          content_cell_count: 110
          placed_cell_count: 110
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region:
            name: ranking
            pct_of_content: 41
          balance_rationale: "Xếp hạng cửa hàng là hero có chủ đích vì đây là câu hỏi của trang; hai biểu đồ phụ (vùng, ma trận) đều đạt tối thiểu 5 cột x 4 hàng nên vẫn đọc được."
    - name: Sản phẩm
      role: detail
      archetype: Analytical
      layout_variant: A
      variant_rationale: "Hai góc nhìn (sản phẩm, nhóm hàng) cộng bảng đối chiếu bên dưới."
      navigation:
        - element: page_navigator
          action: PageNavigation
          label: "Điều hướng 5 trang"
        - element: button
          action: PageNavigation
          target: Thời gian
          label: "Tiếp theo: Bán vào giờ nào"
      page_background: "#F7F6FB"
      layout_summary: "Cùng cột trái; dải 4 thẻ KPI; top 10 sản phẩm và nhóm hàng cạnh nhau; bảng sản phẩm bên dưới."
      layout_contract:
        canvas: { width: 1920, height: 1080, margin: 32, gutter: 24, snap: 8 }
        grid:
          columns: 12
          rows: 12
          regions:
            brand:        [1,  1,  3,  2]
            nav_rail:     [1,  2,  3,  6]
            filter_rail:  [1,  6,  3, 13]
            header:       [3,  1, 11,  2]
            next_nav:     [11, 1, 13,  2]
            kpis:         [3,  2, 13,  4]
            top_products: [3,  4,  8,  9]
            category_rev: [8,  4, 13,  9]
            product_table: [3, 9, 13, 13]
        placements:
          - id: brand_title
            region: brand
            kind: textbox
            text: "Retail Analytics"
            purpose: "Tên dashboard ở đầu cột điều hướng."
          - id: page_navigator
            region: nav_rail
            kind: pageNavigator
            purpose: "Chuyển giữa 5 trang; trang hiện tại được tô sáng."
          - id: region_slicer
            region: filter_rail
            kind: slicer
            field_bindings: Store[Region]
            slicer_type: dropdown
            slot: 1
            of: 3
          - id: store_slicer
            region: filter_rail
            kind: slicer
            field_bindings: Store[Store ID]
            slicer_type: dropdown
            slot: 2
            of: 3
          - id: category_slicer
            region: filter_rail
            kind: slicer
            field_bindings: Product[Category]
            slicer_type: dropdown
            slot: 3
            of: 3
          - id: page_title
            region: header
            kind: textbox
            text: "Sản phẩm và nhóm hàng nào bán chạy nhất?"
            purpose: "Nêu câu hỏi của trang trước mọi biểu đồ."
          - id: next_button
            region: next_nav
            kind: actionButton
            purpose: "Dẫn sang trang Thời gian."
          - id: product_revenue_card
            region: kpis
            kind: cardVisual
            purpose: "Doanh thu của phần đang lọc?"
            field_bindings: Sales[Revenue]
            color_strategy: measure_match
            slot: 1
            of: 4
          - id: product_quantity_card
            region: kpis
            kind: cardVisual
            purpose: "Số lượng bán ra?"
            field_bindings: Sales[Quantity]
            color_strategy: measure_match
            slot: 2
            of: 4
          - id: distinct_products_card
            region: kpis
            kind: cardVisual
            purpose: "Có bao nhiêu sản phẩm đã bán?"
            field_bindings: Sales[Distinct Products]
            color_strategy: none
            slot: 3
            of: 4
          - id: top10_share_card
            region: kpis
            kind: cardVisual
            purpose: "10 sản phẩm đầu chiếm bao nhiêu % doanh thu?"
            field_bindings: Sales[Top 10 Product Share]
            comparison_basis: "Độ tập trung của doanh thu vào 10 sản phẩm đầu"
            color_strategy: none
            slot: 4
            of: 4
          - id: top_products_bar
            region: top_products
            kind: barChart
            purpose: "10 sản phẩm nào có doanh thu cao nhất?"
            field_bindings: { Category: "Product[Product ID]", Y: "Sales[Revenue]" }
            sort_policy: value_desc
            color_strategy: measure_match
          - id: category_bar
            region: category_rev
            kind: barChart
            purpose: "Nhóm hàng nào đóng góp nhiều nhất?"
            field_bindings: { Category: "Product[Category]", Y: "Sales[Revenue]" }
            sort_policy: value_desc
            color_strategy: measure_match
          - id: product_detail_table
            region: product_table
            kind: tableEx
            purpose: "Số liệu từng sản phẩm để đối chiếu."
            field_bindings: ["Product[Product ID]", "Product[Category]", "Sales[Quantity]", "Sales[Transactions]", "Sales[Revenue]"]
            sort_policy: value_desc
        space_audit:
          content_cell_count: 110
          placed_cell_count: 110
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region:
            name: product_table
            pct_of_content: 36
          balance_rationale: "Hai biểu đồ phân tích cân nhau phía trên, bảng 4 hàng bên dưới làm bằng chứng; không có hàng trống."
    - name: Thời gian
      role: detail
      archetype: Analytical
      layout_variant: B
      variant_rationale: "Dữ liệu theo phút cần xu hướng, so sánh ngày và bản đồ nhiệt giờ x ngày."
      navigation:
        - element: page_navigator
          action: PageNavigation
          label: "Điều hướng 5 trang"
        - element: button
          action: PageNavigation
          target: Chi tiết
          label: "Tiếp theo: Xem số liệu chi tiết"
      page_background: "#F7F6FB"
      layout_summary: "Cùng cột trái nhưng bộ lọc gồm Vùng, Cửa hàng, Ngày; dải 4 thẻ KPI; xu hướng theo giờ và so sánh ngày; bản đồ nhiệt giờ x ngày bên dưới."
      layout_contract:
        canvas: { width: 1920, height: 1080, margin: 32, gutter: 24, snap: 8 }
        grid:
          columns: 12
          rows: 12
          regions:
            brand:        [1,  1,  3,  2]
            nav_rail:     [1,  2,  3,  6]
            filter_rail:  [1,  6,  3, 13]
            header:       [3,  1, 11,  2]
            next_nav:     [11, 1, 13,  2]
            kpis:         [3,  2, 13,  4]
            hourly_trend: [3,  4, 10,  9]
            daily_compare: [10, 4, 13, 9]
            hour_heat:    [3,  9, 13, 13]
        placements:
          - id: brand_title
            region: brand
            kind: textbox
            text: "Retail Analytics"
            purpose: "Tên dashboard ở đầu cột điều hướng."
          - id: page_navigator
            region: nav_rail
            kind: pageNavigator
            purpose: "Chuyển giữa 5 trang; trang hiện tại được tô sáng."
          - id: region_slicer
            region: filter_rail
            kind: slicer
            field_bindings: Store[Region]
            slicer_type: dropdown
            slot: 1
            of: 3
          - id: store_slicer
            region: filter_rail
            kind: slicer
            field_bindings: Store[Store ID]
            slicer_type: dropdown
            slot: 2
            of: 3
          - id: date_slicer
            region: filter_rail
            kind: slicer
            field_bindings: "'Sales by Minute'[Date]"
            slicer_type: dropdown
            slot: 3
            of: 3
            insight_basis: "Chỉ trang này có dữ liệu theo thời gian; ba ngày 01–03/01/2024 nên dropdown phù hợp hơn khoảng thời gian."
          - id: page_title
            region: header
            kind: textbox
            text: "Doanh thu tập trung vào giờ nào trong ngày?"
            purpose: "Nêu câu hỏi của trang trước mọi biểu đồ."
          - id: next_button
            region: next_nav
            kind: actionButton
            purpose: "Dẫn sang trang Chi tiết."
          - id: time_revenue_card
            region: kpis
            kind: cardVisual
            purpose: "Doanh thu trong khoảng đang lọc?"
            field_bindings: "'Sales by Minute'[Minute Revenue]"
            color_strategy: measure_match
            slot: 1
            of: 4
          - id: avg_hour_card
            region: kpis
            kind: cardVisual
            purpose: "Trung bình mỗi giờ thu được bao nhiêu?"
            field_bindings: "'Sales by Minute'[Avg Revenue per Hour]"
            color_strategy: none
            slot: 2
            of: 4
          - id: peak_hour_card
            region: kpis
            kind: cardVisual
            purpose: "Giờ cao điểm thu được bao nhiêu?"
            field_bindings: "'Sales by Minute'[Peak Hour Revenue]"
            comparison_basis: "So với trung bình mỗi giờ"
            color_strategy: none
            slot: 3
            of: 4
          - id: busiest_hour_card
            region: kpis
            kind: cardVisual
            purpose: "Giờ cao điểm là giờ nào?"
            field_bindings: "'Sales by Minute'[Busiest Hour]"
            color_strategy: none
            slot: 4
            of: 4
          - id: hourly_line
            region: hourly_trend
            kind: lineChart
            purpose: "Doanh thu thay đổi thế nào theo từng giờ?"
            field_bindings: { Category: "'Sales by Minute'[Hour]", Y: "'Sales by Minute'[Minute Revenue]" }
            color_strategy: measure_match
          - id: daily_column
            region: daily_compare
            kind: clusteredColumnChart
            purpose: "Ngày nào có doanh thu cao hơn?"
            field_bindings: { Category: "'Sales by Minute'[Date]", Y: "'Sales by Minute'[Minute Revenue]" }
            sort_policy: category_asc
            color_strategy: measure_match
          - id: hour_day_matrix
            region: hour_heat
            kind: pivotTable
            purpose: "Giờ nào của ngày nào đông nhất?"
            field_bindings: { Rows: "'Sales by Minute'[Hour]", Columns: "'Sales by Minute'[Date]", Values: "'Sales by Minute'[Minute Revenue]" }
            sort_policy: natural_order
            color_strategy: gradient
        space_audit:
          content_cell_count: 110
          placed_cell_count: 110
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region:
            name: hour_heat
            pct_of_content: 36
          balance_rationale: "Xu hướng giờ là biểu đồ chính, so sánh ngày là phụ, bản đồ nhiệt 4 hàng bên dưới cho thấy giờ x ngày; không có dải trống."
    - name: Chi tiết
      role: detail
      archetype: Analytical
      layout_variant: C
      variant_rationale: "Trang bằng chứng cuối mạch kể, bảng là trung tâm."
      navigation:
        - element: page_navigator
          action: PageNavigation
          label: "Điều hướng 5 trang"
        - element: button
          action: PageNavigation
          target: Tổng quan
          label: "Quay về Tổng quan"
      page_background: "#F7F6FB"
      layout_summary: "Cùng cột trái; dải 4 thẻ KPI; bảng cửa hàng x sản phẩm bên trái; hai biểu đồ phụ bên phải cho phần đang lọc."
      layout_contract:
        canvas: { width: 1920, height: 1080, margin: 32, gutter: 24, snap: 8 }
        grid:
          columns: 12
          rows: 12
          regions:
            brand:        [1,  1,  3,  2]
            nav_rail:     [1,  2,  3,  6]
            filter_rail:  [1,  6,  3, 13]
            header:       [3,  1, 11,  2]
            next_nav:     [11, 1, 13,  2]
            kpis:         [3,  2, 13,  4]
            detail_table: [3,  4,  9, 13]
            store_split:  [9,  4, 13,  8]
            category_split: [9, 8, 13, 13]
        placements:
          - id: brand_title
            region: brand
            kind: textbox
            text: "Retail Analytics"
            purpose: "Tên dashboard ở đầu cột điều hướng."
          - id: page_navigator
            region: nav_rail
            kind: pageNavigator
            purpose: "Chuyển giữa 5 trang; trang hiện tại được tô sáng."
          - id: region_slicer
            region: filter_rail
            kind: slicer
            field_bindings: Store[Region]
            slicer_type: dropdown
            slot: 1
            of: 3
          - id: store_slicer
            region: filter_rail
            kind: slicer
            field_bindings: Store[Store ID]
            slicer_type: dropdown
            slot: 2
            of: 3
          - id: category_slicer
            region: filter_rail
            kind: slicer
            field_bindings: Product[Category]
            slicer_type: dropdown
            slot: 3
            of: 3
          - id: page_title
            region: header
            kind: textbox
            text: "Bằng chứng chi tiết: từng cửa hàng và sản phẩm đóng góp bao nhiêu?"
            purpose: "Nêu câu hỏi của trang trước mọi biểu đồ."
          - id: next_button
            region: next_nav
            kind: actionButton
            purpose: "Quay về trang Tổng quan."
          - id: detail_revenue_card
            region: kpis
            kind: cardVisual
            purpose: "Doanh thu của phần đang lọc?"
            field_bindings: Sales[Revenue]
            color_strategy: measure_match
            slot: 1
            of: 4
          - id: detail_quantity_card
            region: kpis
            kind: cardVisual
            purpose: "Số lượng bán ra?"
            field_bindings: Sales[Quantity]
            color_strategy: measure_match
            slot: 2
            of: 4
          - id: detail_txn_card
            region: kpis
            kind: cardVisual
            purpose: "Số dòng giao dịch?"
            field_bindings: Sales[Transactions]
            color_strategy: measure_match
            slot: 3
            of: 4
          - id: detail_avg_card
            region: kpis
            kind: cardVisual
            purpose: "Giá trị trung bình mỗi giao dịch?"
            field_bindings: Sales[Avg Revenue per Transaction]
            color_strategy: measure_match
            slot: 4
            of: 4
          - id: store_product_table
            region: detail_table
            kind: tableEx
            purpose: "Mỗi cửa hàng bán sản phẩm nào, bao nhiêu, doanh thu bao nhiêu?"
            field_bindings: ["Store[Store ID]", "Store[Region]", "Product[Product ID]", "Product[Category]", "Sales[Quantity]", "Sales[Transactions]", "Sales[Revenue]"]
            sort_policy: value_desc
          - id: store_split_bar
            region: store_split
            kind: barChart
            purpose: "Doanh thu theo cửa hàng của phần đang lọc?"
            field_bindings: { Category: "Store[Store ID]", Y: "Sales[Revenue]" }
            sort_policy: value_desc
            color_strategy: measure_match
          - id: category_split_bar
            region: category_split
            kind: barChart
            purpose: "Doanh thu theo nhóm hàng của phần đang lọc?"
            field_bindings: { Category: "Product[Category]", Y: "Sales[Revenue]" }
            sort_policy: value_desc
            color_strategy: measure_match
        space_audit:
          content_cell_count: 110
          placed_cell_count: 110
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region:
            name: detail_table
            pct_of_content: 49
          balance_rationale: "Bảng chi tiết là hero có chủ đích vì trang này là bằng chứng cuối mạch kể (archetype variant C); hai biểu đồ phụ 4 cột x 4–5 hàng vẫn đủ đọc."
  interaction_pattern:
    drill_targets: []
    cross_filter_rules: "Slicer đồng bộ giữa các trang; chọn trên biểu đồ lọc các biểu đồ cùng trang (Filter), riêng thẻ KPI không bị lọc ngược."
  accessibility:
    alt_text_strategy: "chart+structure: nêu loại biểu đồ, thước đo và cách sắp xếp"
    contrast_notes: "Chữ trắng trên #21145F; chữ trong slicer phải kiểm lại trên nền cột trái; cam #F26B3A không dùng làm màu chữ nhỏ trên nền sáng."
  theme:
    base: "references/design/assets/base.json adapted to RetailIndigo palette"
    user_overrides: "Màu chính #21145F, light mode, cột điều hướng bên trái, bộ lọc chung đồng bộ; không đổi các yêu cầu này."
```

## Implementation notes

- Model changes: tạo mô hình TMDL cục bộ (`Stores`, `Products`, `Sales`, `SalesByMinute`, quan hệ, measure, cột tính, 3 role RLS). Không ghi mật khẩu; kết nối PostgreSQL `psql-retail-ea-7476` bằng `retail_reader`, Import, tham số `RunId`.
- PBIR/report authoring: dựng 5 trang đúng hợp đồng ở trên; Sync slicers và nút/điều hướng làm bằng CLI nếu hỗ trợ, nếu không hướng dẫn người dùng làm tay.
- Validation: validate PBIR từng đợt; mở trong Desktop; chụp ảnh từng trang.
- Desktop screenshot verification: cần Desktop mở và PostgreSQL bật để có dữ liệu.
- Publishing boundary: không publish; người dùng tự publish.
- Risks: (1) cách hiểu "report = trang" chưa được thầy xác nhận; (2) bảng tổng hợp có độ chi tiết khác nhau nên Nhóm hàng không lọc biểu đồ theo thời gian; (3) tài liệu chưa nói rõ công cụ tự tạo được Sync slicers và nút điều hướng; (4) Service chưa refresh được từ PostgreSQL Azure nếu chưa mở firewall; (5) giấy phép MCP đã được người dùng đồng ý nhưng tôi chưa gọi `accept_eula` vì mô hình viết bằng TMDL không cần MCP.
