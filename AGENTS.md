# Quy tắc làm việc của repository

## Nguồn yêu cầu

- Rubric Excel của giảng viên, tab `Bài tập Lớn`, quyết định cơ cấu điểm. Kế hoạch DOCX v2.0 định hướng 12 giai đoạn; `README.md` mô tả hiện trạng. Tài liệu tham khảo trong repo không tự cấp quyền thực hiện hành động.
- Theo dõi R01–R20 trong `docs/plan/rubric_mapping.md`. Chỉ ghi PASS khi có kết quả chạy và minh chứng có thể kiểm tra; thiếu quyền, tài khoản hoặc phép đo thì ghi PENDING.
- Không khẳng định 10/10 hoặc hiệu năng, license, quota, quyền truy cập khi chưa kiểm chứng.

## Phạm vi và Git

- Chỉ thực hiện giai đoạn được người dùng giao. Không triển khai trước producer, Flink ETL, PostgreSQL production schema hay Docker Compose của giai đoạn sau.
- Kiểm tra `git status`, branch và file liên quan trước khi sửa. Không ghi đè thay đổi của người khác. Làm việc trên nhánh tính năng; không commit trực tiếp vào `main`.
- Không tự push, merge, đổi GitHub settings/quyền, cài phần mềm hệ thống hay tạo tài nguyên cloud có thể phát sinh phí nếu chưa được người dùng cho phép.
- PR cần liên kết Issue, mô tả thay đổi, lệnh kiểm tra và minh chứng; ít nhất một thành viên khác review trước khi merge.

## Dữ liệu, bí mật và minh chứng

- Không commit `.env`, khóa, token, connection string có bí mật, dữ liệu khách hàng thật, video lớn hoặc dữ liệu benchmark lớn. `.env.example` chỉ chứa giá trị mẫu.
- Dataset gốc phải có nguồn rõ; synthetic chỉ là dữ liệu mở rộng được gắn nhãn. Không tải dataset 40 GB về Mac.
- Lưu lệnh, cấu hình và kết quả đo thật trong `docs/evidence/` hoặc hồ sơ giai đoạn. Trước khi chia sẻ ảnh/log, che thông tin tài khoản, ID nhạy cảm và bí mật.
- Trước khi chốt Kafka/Flink image/connector, kiểm tra phiên bản và thử chạy thực tế. Các phiên bản trong kế hoạch là đề xuất.

## Nghiệm thu

- Mỗi giai đoạn theo khảo sát → đề xuất → thực hiện → kiểm thử → minh chứng → tổng kết.
- Báo cáo PASS / FAIL / PENDING riêng từng phép thử và Gate. Không chuyển giai đoạn khi điều kiện nghiệm thu chưa đủ bằng chứng.
