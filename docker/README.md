# Local stack — Giai đoạn 03

Yêu cầu: Docker Desktop bản **Apple Silicon** và lệnh `docker compose` hoạt động. Nếu chưa có, tải bản Apple Silicon từ [hướng dẫn chính thức](https://docs.docker.com/desktop/setup/install/mac-install/), kéo Docker.app vào Applications, mở ứng dụng và đợi Engine báo running. Trong **Settings → Resources**, bắt đầu với **4 CPU, 6 GB RAM**, giới hạn disk image khoảng **12–15 GB** rồi kiểm tra SSD trống trước khi kéo image. Bốn container chính dùng khoảng 4,6 GB giới hạn RAM cộng lại; chưa đo mức dùng thực tế. Chỉ Kafka/Flink/PostgreSQL local, chưa có pipeline hay benchmark.

## Chạy

Từ thư mục gốc repository, tạo `.env` cục bộ từ `.env.example`, thay `POSTGRES_PASSWORD` bằng mật khẩu riêng và giữ file này ngoài Git. Host dùng `localhost:9094` cho Kafka, `localhost:8081` cho Flink, `localhost:5433` cho PostgreSQL vì cổng 5432 trên Mac đang được SSH tunnel sử dụng. Container dùng tên `kafka:9092`, `flink-jobmanager:8081`, `postgres:5432`.

```bash
docker compose -f docker/compose.yaml config --quiet
docker compose -f docker/compose.yaml up -d --build
docker compose -f docker/compose.yaml ps --all
```

`kafka-volume-init` chỉ chạy ngắn hạn để đổi chủ sở hữu **named volume Kafka** sang UID/GID `1000:1000`; broker vẫn chạy bằng `appuser`, không chạy thường xuyên bằng root. `kafka-init` tạo topic `retail.sales.transactions` với 3 partitions, replication factor 1 rồi thoát mã 0. Kiểm thực tế:

Từ Giai đoạn 05, `flink-checkpoint-init` cũng chạy một lần để đổi chủ sở hữu **chỉ named volume checkpoint** sang UID/GID `9999:9999`; Flink JobManager/TaskManager vẫn chạy bằng user `flink`. Lần dựng cũ từng báo `Permission denied` khi TaskManager ghi `/opt/flink/checkpoints`; sau init đã kiểm được thao tác ghi/xóa file probe nhỏ bằng UID 9999. Xem [Flink job](../docs/flink-job.md) để chạy SQL và kiểm checkpoint.

```bash
docker compose -f docker/compose.yaml exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic retail.sales.transactions
docker compose -f docker/compose.yaml exec kafka sh -c 'id; stat -c "%u:%g %a %n" /tmp/kraft-combined-logs'
nc -vz 127.0.0.1 9094
curl -fsS http://localhost:8081/overview
docker compose -f docker/compose.yaml exec flink-jobmanager ls /opt/flink/lib/
docker compose -f docker/compose.yaml exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT 1"'
```

Flink `/overview` cần báo ít nhất một TaskManager và 2 slots. Bốn connector JAR trong image Flink phải có mặt; thử nạp connector SQL thực tế thuộc giai đoạn sau. Để kiểm volume PostgreSQL qua restart mà không tạo production schema, tạo một bảng kiểm tra nhỏ, restart container, đọc lại giá trị rồi có thể xóa bảng kiểm tra:

```bash
docker compose -f docker/compose.yaml exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "CREATE TABLE IF NOT EXISTS stage03_volume_probe (id integer PRIMARY KEY); INSERT INTO stage03_volume_probe VALUES (1) ON CONFLICT DO NOTHING;"'
docker compose -f docker/compose.yaml restart postgres
docker compose -f docker/compose.yaml exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT id FROM stage03_volume_probe"'
```

Nếu service lỗi, đọc `docker compose -f docker/compose.yaml logs --tail=100 <service>`. Giữ kết quả `ps`, mô tả topic, Flink UI và `SELECT 1` làm minh chứng khi đã chạy thật. **Dừng an toàn** bằng `docker compose -f docker/compose.yaml down`; không thêm `-v`, vì `-v` sẽ xóa volumes.

### Kafka báo `AccessDeniedException` tại `/tmp/kraft-combined-logs`

Docker có thể tạo named volume với chủ sở hữu `root`, trong khi image Kafka chạy bằng `appuser` (UID/GID `1000:1000`). Compose chạy `kafka-volume-init` **trước broker** để `chown -R 1000:1000` đúng volume này; service init thoát mã 0 rồi Kafka mới khởi động. Nếu volume cũ vẫn sai quyền, dừng riêng Kafka, chạy lại init và khởi động broker:

```bash
docker compose -f docker/compose.yaml stop kafka
docker compose -f docker/compose.yaml up --no-deps kafka-volume-init
docker compose -f docker/compose.yaml up -d kafka kafka-init
docker compose -f docker/compose.yaml exec kafka sh -c 'id; stat -c "%u:%g %a %n" /tmp/kraft-combined-logs'
```

Chỉ init service dùng root tạm thời để sửa quyền; không đặt `user: root` cho broker, không `chmod 777`, không `down -v` vì sẽ xóa dữ liệu Kafka và PostgreSQL.

## Phiên bản và giới hạn

- Kafka `apache/kafka:4.2.2` KRaft một broker, listener Docker/host tách biệt, retention 6 giờ và 128 MiB mỗi partition; image có ARM64 theo Docker Hub.
- Flink `flink:2.2.1-scala_2.12-java17`, JobManager 1024 MB, TaskManager 1536 MB/2 slots, checkpoint volume chung. Dockerfile ghim SHA-256 của Kafka SQL `5.0.0-2.2`, JDBC core/Postgres `4.1.0-2.2`, PostgreSQL JDBC `42.7.8` từ Maven Central. Image đã build ở GĐ03; kiểm nạp và dùng connector trong một Flink SQL job sẽ thực hiện ở giai đoạn ETL.
- PostgreSQL `postgres:17-alpine`, database từ `.env`, volume riêng. Không expose cổng ra ngoài máy (`127.0.0.1` only). Chưa cấu hình TLS/auth cho Kafka vì đây là stack local chỉ dùng loopback; không dùng cấu hình này để deploy cloud.

Nguồn kiểm phiên bản: [Apache Kafka Docker](https://kafka.apache.org/42/getting-started/docker/), [Flink Kafka SQL](https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/connectors/table/kafka/), [Flink JDBC SQL](https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/connectors/table/jdbc/), [Docker Flink ARM64](https://hub.docker.com/_/flink/tags).
