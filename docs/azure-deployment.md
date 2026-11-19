# Nhật ký triển khai Azure

**Cập nhật:** 17–18/11/2026. **Trạng thái triển khai Azure: PENDING.** Mỗi bước dưới đây ghi: làm gì, vào đâu để xem, trường cần điền, tên đặt, kết quả thực tế và minh chứng cần chụp. Không ghi subscription ID, tenant ID, email, mật khẩu hay connection string vào file này; khi chụp ảnh phải che các thông tin đó.

**Nguyên tắc làm việc (đã thống nhất):**
- Trước mọi thao tác trên Azure phải nêu rõ việc sẽ làm và được người phụ trách Azure duyệt rồi mới chạy.
- Mỗi lần bật hoặc tắt project, hỏi thêm có bật hoặc tắt Azure không để tiết kiệm credit.
- **Azure chỉ chạy khi đang thực hiện việc.** Không dùng lịch tắt tự động theo giờ hay ngày. Khi người phụ trách báo tắt thì tắt hết dịch vụ, rồi liệt kê khoản còn tính (ổ đĩa, storage, IP).
- Trước mỗi bước **bắt đầu tính tiền** phải báo rõ khoản nào, đơn giá, và chờ duyệt.
- Tài khoản dùng: tài khoản cá nhân của người phụ trách Azure, gói **Azure for Students** (credit khoảng 100 USD). Mọi chi phí tính vào gói này.

## Quy ước đặt tên

| Loại | Mẫu | Tên dự kiến | Ghi chú |
|---|---|---|---|
| Resource group | `rg-<project>` | `rg-retail-analytics` | |
| Virtual network | `vnet-<project>-<region>` | `vnet-retail-ea` | `ea` = East Asia |
| Network security group | `nsg-<project>-<region>` | `nsg-retail-ea` | |
| Public IP | `pip-<project>-<region>-01` | `pip-retail-ea-01` | |
| VM | `vm-<project>-<region>-01` | `vm-retail-ea-01` | |
| PostgreSQL Flexible Server | `psql-<project>-<region>-<số>` | `psql-retail-ea-<số ngẫu nhiên>` | Tên phải duy nhất toàn Azure, chữ thường, số và dấu gạch |
| Storage account | `st<project><region><số>` | `stretailea<số ngẫu nhiên>` | 3–24 ký tự, chỉ chữ thường và số, duy nhất toàn Azure |
| Blob container | `<mục đích>` | `benchmark-data`, `manifests` | |

**Tag gắn cho mọi resource:** `project=retail-analytics`, `env=dev`.

## Bảng tiến độ

| Bước | Nội dung | Trạng thái |
|---|---|---|
| 0 | Cài Azure CLI và đăng nhập đúng subscription | PASS |
| 1 | Đăng ký provider Compute, PostgreSQL, Network | PASS |
| 2 | Kiểm quota, SKU, giá, chọn region | PASS khảo sát; PostgreSQL chưa xác nhận lúc tạo |
| 3 | Tạo resource group | PASS (18/11/2026) |
| 4 | Thêm thành viên vào resource group | Đã mời và gán quyền (18/11/2026); chờ thành viên chấp nhận lời mời |
| 5 | Đặt ngân sách và cảnh báo chi phí | PASS (18/11/2026) |
| 6 | Tạo mạng, VM | PASS (19/11/2026); VM đang chạy, **đang tính tiền** |
| 7 | Tạo PostgreSQL, firewall, chạy schema | PASS (19/11/2026); server đã dừng (còn tính storage) |
| 8 | Tạo Blob Storage | PASS (19/11/2026) |
| 9 | Dựng stack trên VM và chạy pipeline | PASS (19/11/2026) cho lượt 1.000 dòng |
| 10 | Chạy lại 11 test case trên cloud | PASS (19/11/2026), 11/11 |
| 11 | Quy trình bật/tắt và dọn dẹp | Phần bật/tắt: PASS (19/11/2026), đã tắt VM và PostgreSQL; phần dọn dẹp: chưa làm (chỉ khi kết thúc và được duyệt) |

---

## Bước 0. Cài Azure CLI và đăng nhập

- **Làm gì:** cài Azure CLI 2.93.0 bằng `winget install --id Microsoft.AzureCLI`, rồi `az login`.
- **Vào đâu:** terminal PowerShell. File gọi: `C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd`.
- **Phát hiện khi đăng nhập:**
  - Đăng nhập mặc định bị lỗi `AADSTS50076` (yêu cầu MFA) với hai tenant. Cách xử lý: `az login --tenant <tenant-id>` rồi hoàn tất MFA.
  - Tenant thứ nhất chỉ cho quyền ở một resource group của đề tài khác, không đủ quyền đăng ký provider. **Không dùng** subscription đó cho project này.
  - Tenant thứ hai là gói Azure for Students riêng, vai trò **Owner**, chưa có resource group nào.
- **Kiểm tra:** `az account list --query "[].{name:name,state:state,isDefault:isDefault}" -o table` phải thấy gói Azure for Students ở trạng thái Enabled và là mặc định (đúng tenant thứ hai).
- **Kết quả:** PASS. Mỗi lần thay đổi trên Azure phải kiểm lại bằng `az account show --query tenantId -o tsv` để chắc chắn đang ở đúng subscription.

## Bước 1. Đăng ký provider

- **Làm gì:** cho phép subscription dùng các loại dịch vụ cần thiết. Không tạo resource, không tốn phí.
- **Vào đâu (Portal):** Subscriptions → chọn gói → **Settings → Resource providers**, tìm từng tên.
- **Lệnh:**
  ```
  az provider register --namespace Microsoft.Compute
  az provider register --namespace Microsoft.DBforPostgreSQL
  az provider register --namespace Microsoft.Network
  ```
  Microsoft.Storage đã ở trạng thái Registered từ trước.
- **Kết quả (17/11/2026):** cả ba chuyển `Registered` sau khoảng 75 giây.
- **Minh chứng:** ảnh trang Resource providers có bốn provider ở trạng thái Registered (che subscription ID).

## Bước 2. Kiểm quota, SKU, giá và chọn region

- **Làm gì:** chỉ đọc, chọn region và kích cỡ dựa trên dữ liệu thật của subscription.
- **Vào đâu (Portal):** Subscriptions → **Usage + quotas** (lọc Microsoft.Compute theo region); hoặc Virtual machines → Create → ô **Size**.
- **Kết quả đọc được:**

  | Hạng mục | East Asia | Southeast Asia | Japan East |
  |---|---|---|---|
  | VM B-series | `B2as_v2`, `B2s_v2`, `B4as_v2` không bị hạn chế | **Bị khóa** (`Location/NotAvailableForSubscription`, đã xác nhận với `B2ms`) | Bị hạn chế |
  | Quota vCPU | Tổng 6; họ Basv2 và Bsv2 mỗi họ 10; họ BS cũ 4; đã dùng 0 | Tổng 6 | Tổng 6 |
  | PostgreSQL Burstable | Có B1ms, B2s, B2ms, B4ms | Có | Chưa kiểm |

- **Giá công khai (Azure Retail Prices API, USD):** VM `B2as_v2` khoảng 0,114/giờ (nhãn giá cần xác nhận trên Portal); PostgreSQL `B1ms` 0,0286/giờ; PostgreSQL storage 0,15/GB/tháng; Blob Hot LRS khoảng 0,024/GB/tháng. Chưa có giá ổ đĩa VM và IP công cộng.
- **Quyết định đề xuất:** region **East Asia**. VM `Standard_B2as_v2`, PostgreSQL Burstable `B1ms` (nâng lên `B2s` nếu thiếu RAM).
- **Ước tính theo cách dùng (chưa gồm ổ đĩa và IP):** chạy 24/7 khoảng 109 USD/tháng, vượt credit; 8 giờ/ngày khoảng 39; 4 giờ/ngày khoảng 22. Vì vậy **bắt buộc có lịch tắt**.
- **Còn mở:** hạn chế theo offer Students đối với PostgreSQL thường chỉ lộ ra lúc tạo; xác nhận khi tới bước 7.

## Bước 3. Tạo resource group

**Kết quả (18/11/2026): PASS.** `az group create` trả về `provisioningState=Succeeded`, region `eastasia`, tag `env=dev`, `project=retail-analytics`. Resource group rỗng nên **chưa tính tiền**.

- **Làm gì:** tạo một resource group chứa toàn bộ resource của project. Không tốn phí.
- **Vào đâu (Portal):** Resource groups → **Create**.
- **Trường cần điền:**

  | Trường | Giá trị |
  |---|---|
  | Subscription | Azure for Students (gói riêng của người phụ trách) |
  | Resource group | `rg-retail-analytics` |
  | Region | **East Asia** |
  | Tags | `project=retail-analytics`, `env=dev` |

- **Lệnh tương đương:**
  ```
  az group create --name rg-retail-analytics --location eastasia --tags project=retail-analytics env=dev
  ```
- **Kiểm tra:** `az group show --name rg-retail-analytics --query "{name:name,location:location,state:properties.provisioningState}" -o table` phải thấy `Succeeded`.
- **Minh chứng:** ảnh trang Overview của resource group (che subscription ID).

## Bước 4. Thêm thành viên vào resource group

- **Làm gì:** cấp quyền để các thành viên nhóm cùng dùng `rg-retail-analytics`.
- **Vào đâu (Portal):** Resource groups → `rg-retail-analytics` → **Access control (IAM)** → **Add → Add role assignment**.
- **Trường cần điền:**

  | Trường | Giá trị |
  |---|---|
  | Role | **Contributor** (cấp ở phạm vi resource group, không cấp trên cả subscription, không cấp Owner) |
  | Members | Chọn thành viên theo email |
  | Review + assign | Gán |

- **Lưu ý:**
  - Quyền truy cập resource group **không phụ thuộc region** hay subscription riêng của từng thành viên. Chỉ cần được gán quyền ở đây.
  - Nếu thành viên dùng tài khoản ngoài tenant của người phụ trách (ví dụ Gmail), cần **mời làm khách (guest)** trước: Microsoft Entra ID → Users → **Invite external user**. Họ nhận email mời và phải chấp nhận, rồi mới gán được vai trò.
  - Thành viên chỉ thấy resource group sau khi đổi sang đúng directory ở Portal (biểu tượng hồ sơ → Switch directory).
  - Hạn mức vCPU và hạn chế SKU tính theo subscription của người phụ trách, không theo tài khoản thành viên.
- **Kiểm tra:** từng thành viên đăng nhập vào đúng directory, mở `rg-retail-analytics`, thấy được Overview. Ghi kết quả từng người (PASS/FAIL) vào bảng bên dưới.
- **Minh chứng:** ảnh trang Role assignments (che email nếu cần).

| Thành viên | Vai trò gán | Đã chấp nhận lời mời | Thấy được resource group |
|---|---|---|---|
| Thành viên 1 | Contributor (phạm vi `rg-retail-analytics`) | Chờ (`PendingAcceptance`) | Chưa kiểm |
| Thành viên 2 | Contributor (phạm vi `rg-retail-analytics`) | Chờ (`PendingAcceptance`) | Chưa kiểm |

**Đã làm (18/11/2026):** gửi lời mời khách qua Microsoft Graph (`POST /invitations`, `sendInvitationMessage=true`) cho hai tài khoản trường, rồi `az role assignment create --role Contributor` ở phạm vi resource group. Kiểm bằng `az role assignment list --scope <resource group>`: thấy hai gán `Contributor` loại `User`. Hai lời mời đang `PendingAcceptance`; cần từng người mở email, chấp nhận, đổi sang đúng directory trên Portal rồi cập nhật bảng này.

## Bước 5. Ngân sách và cảnh báo chi phí

- **Làm gì:** tạo budget để nhận email cảnh báo khi chi phí tăng. Budget chỉ cảnh báo, không tự dừng resource.
- **Vào đâu (Portal):** Cost Management + Billing → Cost Management → **Budgets** → Add.
- **Trường đề xuất:** Name `budget-retail`; Scope subscription; Reset period Monthly; Amount 80 USD (thấp hơn credit để còn dư địa); cảnh báo Actual ở 50% và 80%, Forecasted ở 100%; email người phụ trách.
- **Kết quả (18/11/2026): PASS.** Tạo budget `budget-retail` ở phạm vi subscription qua Azure Resource Manager (`Microsoft.Consumption/budgets`): 80 USD/tháng, hiệu lực 01/11/2026–01/11/2027, ba cảnh báo (Actual >50%, Actual >80%, Forecasted >100%) gửi tới email tài khoản chủ subscription. Đọc lại từ Azure thấy đủ ba cảnh báo `enabled=True`; chi phí hiện tại 0,00 USD. Budget chỉ cảnh báo, không tự dừng resource; dữ liệu chi phí có thể trễ vài giờ.
- **Minh chứng:** ảnh trang Budgets (che email).

## Bước 6. Tạo mạng và VM (chưa làm)

- **Vào đâu (Portal):** Virtual machines → **Create → Azure virtual machine**.
- **Trường đề xuất:**

  | Trường | Giá trị |
  |---|---|
  | Resource group | `rg-retail-analytics` |
  | Virtual machine name | `vm-retail-ea-01` |
  | Region | East Asia |
  | Availability options | Không cần dự phòng hạ tầng |
  | Image | Ubuntu Server 24.04 LTS (x64 Gen2) |
  | Size | `Standard_B2as_v2` (2 vCPU, 8 GB) |
  | Authentication | SSH public key; username `azureuser` |
  | Inbound ports | SSH (22), nhưng giới hạn nguồn là IP của thành viên (không mở cho toàn internet) |
  | OS disk | Standard SSD, 64 GB, bật Delete with VM |
  | Auto-shutdown | **Không bật lịch.** Tắt thủ công khi người phụ trách báo (`az vm deallocate`) |
  | Tags | như quy ước |

- **Kết quả (19/11/2026): PASS.** Đã tạo theo thứ tự: `vnet-retail-ea` (10.10.0.0/16, subnet `snet-retail` 10.10.1.0/24), `nsg-retail-ea` với một rule `allow-ssh-admin` (ưu tiên 100, chỉ cho cổng 22 từ IP của người phụ trách, dạng `/32`), `pip-retail-ea-01` (Standard, tĩnh), rồi `vm-retail-ea-01` (`Standard_B2as_v2`, Ubuntu 24.04 LTS Gen2, ổ OS Standard SSD 64 GB, xóa cùng VM, đăng nhập bằng khóa SSH ed25519 không passphrase, user `azureuser`). Khóa riêng nằm ở thư mục `.ssh` của người phụ trách, không đưa vào repo. SSH thử thành công: 2 vCPU, 7,9 GB RAM, đĩa gốc 61 GB (dùng 1,9 GB).
- **Khoản tính tiền từ bước này:** compute VM khoảng 0,105 USD/giờ khi chạy; ổ OS khoảng 4,8 USD/tháng (tính cả khi VM tắt); public IP tĩnh khoảng 3,6 USD/tháng (chưa xác minh giá, tính cả khi VM tắt). VNet và NSG miễn phí.
- **Việc sau khi tạo:** cài Docker, kéo repo, tạo `.env` trên VM (không commit), dựng stack.
- **Minh chứng:** ảnh Overview của VM và trang Networking (che IP nếu cần).

## Bước 7. Tạo PostgreSQL (chưa làm)

- **Vào đâu (Portal):** Azure Database for PostgreSQL flexible servers → **Create**.
- **Trường đề xuất:**

  | Trường | Giá trị |
  |---|---|
  | Resource group | `rg-retail-analytics` |
  | Server name | `psql-retail-ea-<số ngẫu nhiên>` |
  | Region | East Asia |
  | PostgreSQL version | 17 (khớp image local; xác nhận có sẵn khi tạo) |
  | Workload type | Development |
  | Compute + storage | Burstable `B1ms`, 32 GiB, tắt High availability, tắt geo-redundant backup |
  | Authentication | PostgreSQL authentication |
  | Admin username | `retail_admin` (khác tài khoản ứng dụng) |
  | Password | Mật khẩu mạnh, lưu trong trình quản lý mật khẩu, **không** đưa vào Git |
  | Networking | Public access; thêm firewall rule cho IP của VM và của từng thành viên (không chọn "Allow all") |
  | Database | `retail_analytics` |

- **Kết quả (19/11/2026): PASS.**
  - Server `psql-retail-ea-7476`: trạng thái Ready, PostgreSQL 17.11, Burstable `Standard_B1ms`, 32 GB, không High availability, không geo-redundant backup, backup giữ 7 ngày, `require_secure_transport=on`, tag `env=dev`/`project=retail-analytics`.
  - Lỗi gặp khi dùng Azure CLI 2.93.0: `--high-availability Disabled` và `--database-name` không dùng được với `flexible-server create` (cả hai chỉ áp dụng cho trường hợp khác); bỏ hai tham số, rồi tạo database bằng `az postgres flexible-server db create --server-name ... --name retail_analytics`. Các lệnh con `firewall-rule` và `db` dùng `--server-name` (không phải `-n`) cho tên server.
  - Firewall: một rule cho IP máy người phụ trách (tạo cùng server) và `allow-vm-retail` cho IP tĩnh của VM. Không có rule "cho tất cả".
  - Database `retail_analytics`; đã chạy `01_schema.sql` và `03_indexes.sql` bằng tài khoản admin: đủ 6 bảng (`pipeline_runs`, `products`, `sales_by_store`, `sales_by_store_minute`, `sales_by_store_product`, `stores`). Chưa chạy seed dimension.
  - Tài khoản ứng dụng `retail_app` (quyền SELECT/INSERT/UPDATE/DELETE trên schema `public`, không có quyền tạo bảng): kiểm thực tế đọc được, ghi được (đã rollback), tạo bảng bị từ chối.
  - Mật khẩu admin và ứng dụng sinh ngẫu nhiên, lưu trong `.env` local (gitignore) với các khóa `AZURE_PG_*`; không ghi vào tài liệu.
- **Khoản tính tiền từ bước này:** compute `B1ms` khoảng 0,0286 USD/giờ khi chạy; storage 32 GB khoảng 4,8 USD/tháng; backup trong hạn mức đi kèm storage (chưa xác minh). Server vẫn tính compute cho đến khi dừng (`az postgres flexible-server stop`).
- **Việc còn lại:** seed dimension, kiểm tra kết nối từ VM, đổi Flink JDBC sink sang server này.
- **Kết nối Power BI sau này:** cần rule firewall cho dịch vụ Power BI; xử lý ở giai đoạn dashboard.
- **Minh chứng:** ảnh Overview và Networking của server (che tên và IP nếu cần).

## Bước 8. Tạo Blob Storage (chưa làm)

- **Vào đâu (Portal):** Storage accounts → **Create**.
- **Trường đề xuất:** Resource group `rg-retail-analytics`; Storage account name `stretailea<số ngẫu nhiên>`; Region East Asia; Performance Standard; Redundancy LRS; Access tier Hot; tắt Allow Blob anonymous access. Tạo container `benchmark-data` và `manifests` (Public access level: Private).
- **Kết quả (19/11/2026): PASS.** Storage account `stretailea76866` (StorageV2, Standard_LRS, Hot, TLS tối thiểu 1.2, chỉ HTTPS, tắt truy cập blob công khai), tag `env=dev`/`project=retail-analytics`; hai container `benchmark-data` và `manifests`, đều private. Tên account lưu trong `.env` local với khóa `AZURE_STORAGE_ACCOUNT`. Tạo container bằng khóa tài khoản (đọc tạm, không lưu); chưa gán vai trò Storage Blob Data Contributor cho ai.
- **Chi phí:** Hot LRS khoảng 0,024 USD/GB/tháng cộng phí giao dịch; chưa có dữ liệu nên gần như 0. Sẽ tăng khi tải dữ liệu benchmark lớn.
- **Minh chứng:** ảnh trang Containers.

## Bước 9. Dựng stack và chạy pipeline trên cloud

- **Kết quả (19/11/2026): PASS (lượt 1.000 dòng synthetic, bounded).**
  - Bật VM và PostgreSQL lúc 21:59 (giờ máy người phụ trách). VM giữ nguyên IP tĩnh; rule firewall của PostgreSQL và NSG vẫn khớp.
  - Trên VM: cài `docker.io`, `docker-compose-v2`, `python3-venv` từ kho Ubuntu (Docker 29.1.3, Compose 2.40.3, Python 3.12.3). Chuyển mã nguồn bằng `tar` chỉ gồm file Git theo dõi, không có `.env`; tạo `.env` riêng trên VM (quyền 600) chứa thông tin kết nối Azure PostgreSQL.
  - Dựng bằng Compose chỉ các dịch vụ Kafka, kafka-init, Flink JobManager và TaskManager (image Flink build ngay trên VM). Không dựng PostgreSQL local. Kafka healthy, các container init thoát mã 0.
  - Seed dimension vào Azure PostgreSQL: 5 store, 80 product, PASS.
  - Producer replay 1.000 dòng với `run_id=cloud_run_01`: `delivered=1000`, `pending=0`, khoảng 930 sự kiện/giây (số đo trên VM, chưa phải benchmark). Offset Kafka sau gửi: 397 / 0 / 603.
  - Flink job JDBC bounded (`run_jdbc.py`) ghi vào Azure PostgreSQL: `job_state=FINISHED`.
  - Đối soát độc lập với nguồn (`reconcile.py`): `sales_by_store` 5 dòng, `sales_by_store_product` 373 dòng, `sales_by_store_minute` 334 dòng; mỗi bảng doanh thu 310.265,83 (USD mô phỏng), 0 lệch khóa, cả ba PASS. Kết quả trùng với lượt chạy local.
- **Thay đổi mã để chạy với PostgreSQL ngoài (chưa commit):** `05_jdbc_sinks.sql` dùng `{{JDBC_URL}}`; `run_jdbc.py` đọc `JDBC_URL`, `JDBC_USER`, `JDBC_PASSWORD` nếu có, mặc định vẫn dùng container local; `reconcile.py` và `seed_dimensions.py` đọc `PG_HOST`, `PG_USER`, `PG_PASSWORD`, `PG_DB` nếu có (chạy psql qua `postgres:17-alpine` với SSL), mặc định vẫn dùng container local. 21 unit test vẫn đạt sau khi sửa.
- **Chưa kiểm:** chế độ chạy liên tục (không `--end`), và hành vi local sau thay đổi (stack local đang tắt; mới có unit test).

## Bước 10. Kiểm thử trên cloud

- **Kết quả (19/11/2026): 11/11 test case PASS.**
  - Chạy `tests/integration/run_stage07.py` (batch `cloud_gateb_01`) **trên VM**, ghi vào PostgreSQL Azure, với TC01–TC07, TC09, TC10, TC11 (TC02–TC04 chung một lần phát). Danh sách `failed` rỗng. Số liệu khớp bản local: TC01 1.000 dòng, 2.985, 310.265,83; TC11 10.000 dòng, 29.867, 2.983.773,00 (payload 4.742.027 byte); TC10 raw = invalid + duplicate + unique_valid.
  - **TC08** (restart PostgreSQL) làm riêng từ máy người phụ trách vì cần Azure CLI: `az postgres flexible-server restart`, mất khoảng 66 giây (22:20:14–22:21:20 giờ máy), tổng trước và sau đều `5 | 1000 | 2985 | 310265.83`, đối soát ba bảng PASS. Runner ở chế độ cloud bỏ qua TC08 (`SkipCase`) và bản làm tay này thay thế.
  - Bằng chứng: [cloud-test-matrix.csv](evidence/cloud-test-matrix.csv), [cloud-validation-output.csv](evidence/cloud-validation-output.csv), [cloud-restart-log.txt](evidence/cloud-restart-log.txt) (đã quét, không có mật khẩu hay IP).
- **Thay đổi runner (chưa commit):** thêm chế độ cloud khi đặt `PG_HOST`, `PG_USER`, `PG_PASSWORD` (hàm `pg()` chạy psql qua `postgres:17-alpine` với SSL, bỏ kiểm tra container postgres, TC08 bỏ qua). Mặc định vẫn là PostgreSQL local.
- **Giới hạn (giữ nguyên từ bản local):** chưa có bộ đếm late event trực tiếp; không chứng minh exactly-once; TC06 chỉ là tiếp tục có kiểm soát sau khi đã nhận ACK; kiểm thử này không phải benchmark trên 4 GB hay đo độ trễ hai region.
- **Chưa kiểm:** thử restart Flink job liên tục dài ngày; chi phí thực tế (xem Cost Management).
- Chạy lại ma trận 11 test case GĐ07 (`tests/integration/run_stage07.py`) và so với kết quả local. Ghi chú: runner hiện tìm PostgreSQL trong container local, cần điều chỉnh khi DB nằm ở Azure.
- Minh chứng: log đối soát đã che bí mật, ảnh Flink UI, bảng expected/actual.

## Bước 11. Bật/tắt và dọn dẹp

**Nguyên tắc:** chỉ bật khi đang làm việc; tắt khi người phụ trách báo; không dùng lịch tự động. Mọi lệnh dưới đây chạy sau khi xác nhận đúng subscription (`az account show --query tenantId -o tsv` phải ra tenant của gói riêng).

**Tắt (đã thực hiện 19/11/2026):**
```
az vm deallocate -g rg-retail-analytics -n vm-retail-ea-01
az postgres flexible-server stop -g rg-retail-analytics -n <tên server>
```
Kiểm tra: VM hiện `VM deallocated`, PostgreSQL hiện `Stopped`. Máy chạy từ 21:59 đến 22:23, ước tính khoảng 0,05 USD compute (0,105 + 0,0286 USD/giờ, giá công khai).

**Khoản vẫn tính khi đã tắt (ước tính từ giá công khai, chưa phải hóa đơn):** ổ OS 64 GB khoảng 4,8 USD/tháng; public IP tĩnh khoảng 3,6 USD/tháng (chưa xác minh giá); storage PostgreSQL 32 GB khoảng 4,8 USD/tháng; Blob gần như 0 khi chưa có dữ liệu. Tổng cố định khoảng 13–15 USD/tháng. VNet, NSG, giao diện mạng miễn phí. Azure có thể tự bật lại PostgreSQL sau khoảng 7 ngày dừng liên tục (chưa xác minh trên gói này): nếu để lâu cần kiểm tra trạng thái.

**Bật lại:**
```
az vm start -g rg-retail-analytics -n vm-retail-ea-01
az postgres flexible-server start -g rg-retail-analytics -n <tên server>
```
Sau khi VM chạy lại, các container không tự khởi động. Trên VM chạy: `cd ~/retail && sudo docker compose --env-file .env -f docker/compose.yaml up -d kafka-init flink-jobmanager flink-taskmanager`. IP của VM giữ nguyên (tĩnh). Nếu IP máy người phụ trách đổi thì SSH bị chặn: cập nhật nguồn của rule `allow-ssh-admin` trong `nsg-retail-ea` và rule firewall của PostgreSQL.

**Dọn dẹp (chưa làm, chỉ khi kết thúc và được người phụ trách duyệt):** xóa toàn bộ bằng `az group delete --name rg-retail-analytics` (xóa VM, ổ đĩa, IP, PostgreSQL và Blob cùng dữ liệu, không khôi phục được). Trước khi xóa: xuất dữ liệu cần giữ, lưu ảnh và log minh chứng, xác nhận không còn việc cần dùng cloud.
