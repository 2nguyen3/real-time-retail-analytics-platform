# Kiểm tra khả thi Azure, quota và chi phí

**Ngày lập:** 15/11/2026. **Kết luận:** PENDING. Azure CLI không có trong máy. Đã đọc Azure Portal qua Chrome: có một subscription **Azure for Students**, trạng thái **Active**, tài khoản hiện tại có vai trò **Owner**. Không ghi subscription ID/email vào repo. Trang `Usage + quotas`, Provider Compute, Region All báo provider chưa đăng ký cho subscription được chọn và **không có dữ liệu quota**. Chưa kiểm hai region, IAM của thành viên khác, credit, giá theo SKU hoặc tạo resource. Kết quả quan sát đã được lược thông tin tài khoản ở `../plan/stage_01_status.md`.

## Checklist Azure Portal cho chủ tài khoản

1. Vào `portal.azure.com` → **Subscriptions**. Ghi tên/loại offer, trạng thái active, credit còn lại và người có quyền. Che subscription ID trước khi chia sẻ ảnh. Nếu chỉ có trial/student credit, ghi ngày hết hạn và hạn chế dịch vụ.
2. Tại subscription → **Access control (IAM)**, kiểm vai trò của người tạo Resource Group và khả năng cấp quyền tối thiểu cho ba thành viên. Chỉ kiểm tra, chưa thay đổi quyền. Ghi ai có quyền đọc Cost Management.
3. Tại **Quotas** hoặc subscription → **Usage + quotas**, lọc Microsoft.Compute theo từng region ứng viên. Ghi *regional vCPU* và *VM family vCPU* `current usage/limit`, VM size dự kiến; quota đủ chưa bảo đảm còn capacity. Chụp cả region và thời điểm.
4. Chọn hai region có thể dùng. Kiểm VM size ở cả hai, Blob Storage account và Azure Database for PostgreSQL Flexible Server ở region DB; kiểm quota/giới hạn riêng của từng dịch vụ. Không tự giả định hai region ví dụ trong kế hoạch đều khả dụng.
5. Mở Azure Pricing Calculator hoặc trang giá của subscription, lập dự toán theo VM size × số giờ, disk VM, PostgreSQL compute × giờ, storage/backup, Blob GB × tháng, read/write transactions, egress giữa region và chi phí Power BI nếu cần. Ghi tiền tệ, region, SKU, ngày giá và link/screenshot. Chưa thể điền tổng chi phí thực vì chưa có SKU/giá/quota của tài khoản.
6. Vào **Cost Management → Budgets** để xem khả năng tạo Budget, các ngưỡng actual/forecast và email cảnh báo. Budget chỉ cảnh báo, **không tự dừng tiêu thụ**. Chỉ tạo Budget sau khi chủ tài khoản duyệt nếu thao tác làm thay đổi tài khoản.
7. Xác nhận lịch vận hành và dọn tài nguyên cho GĐ08. Stop VM vẫn có thể còn phí disk/IP; với PostgreSQL Flexible Server, stop compute không có nghĩa storage/backup miễn phí và trạng thái dừng có giới hạn thời gian. Kiểm trên trang giá thực trước triển khai.

## Ma trận expected / actual

| Mục | Expected trước Gate A | Actual | Trạng thái |
|---|---|---|---|
| Subscription và loại offer | Active, hiểu giới hạn/credit | Azure for Students, Active; credit chưa xem | PASS nhận diện; PENDING credit |
| Quyền tạo Resource Group | Vai trò đủ theo scope được chọn | Vai trò Owner ở subscription; chưa thử thao tác tạo | PASS vai trò; PENDING khả năng triển khai thực tế |
| Hai region | VM/DB/Storage khả dụng theo kiến trúc | Chưa kiểm | PENDING |
| Quota vCPU | Regional và family quota đủ cho VM định chọn | Portal báo provider Compute chưa đăng ký; bảng quota không có dữ liệu | BLOCKED |
| VM, Blob, PostgreSQL Flexible Server | SKU và kết nối khả thi | Chưa kiểm | PENDING |
| RBAC ba thành viên | Có thể cấp quyền tối thiểu và minh chứng cộng tác | Chưa kiểm | PENDING |
| Chi phí/budget | Có ước tính SKU/giờ/GB, ngân sách và cảnh báo | Chưa có dữ liệu giá theo lựa chọn | PENDING |

## Lệnh CLI chỉ đọc, nếu Azure CLI đã được cài và đăng nhập hợp lệ

Không cài CLI trong GĐ01 khi chưa được người dùng cho phép. Không đưa kết quả chứa ID/email/token vào Git.

```bash
az account list --query '[].{name:name,state:state,isDefault:isDefault}' -o table
az vm list-usage --location <region-a> -o table
az vm list-usage --location <region-b> -o table
az provider show --namespace Microsoft.DBforPostgreSQL --query registrationState -o tsv
az provider show --namespace Microsoft.Storage --query registrationState -o tsv
```

Các lệnh trên không thay thế kiểm quyền Resource Group/IAM, giá hoặc khả năng cấp VM size cụ thể. Không chạy `az group create`, `az vm create`, `az postgres ... create` hay `az storage account create` ở GĐ01.

## Nguồn để kiểm tra lại khi có subscription

- [Azure VM vCPU quotas](https://learn.microsoft.com/azure/virtual-machines/quotas)
- [Azure Quotas trong Portal](https://learn.microsoft.com/en-us/azure/quotas/view-quotas)
- [Azure Cost Management budgets](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets): cảnh báo không dừng resource.
- [PostgreSQL Flexible Server stop](https://learn.microsoft.com/en-us/azure/postgresql/configure-maintain/how-to-stop-server)

Minh chứng dự kiến `01-azure-quotas.png` phải hiện hai region, quota/usage và thời điểm; che subscription ID, email và thông tin thanh toán. Chi phí/quota không được ghi PASS nếu chỉ có ảnh trang giá chung.
