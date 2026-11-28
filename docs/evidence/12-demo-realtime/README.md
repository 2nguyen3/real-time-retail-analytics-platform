# Chạy thử demo realtime trên Azure (26/11/2026)

- Luồng: tệp đợt 1 đã tiền xử lý trên VM → Producer (50 giao dịch/giây) → Kafka → Flink streaming → Azure PostgreSQL.
- Producer được dừng bằng tay sau 75 251 giao dịch; job Flink không có điểm kết thúc.
- Đối soát bằng `sql/postgres/reconcile.py` (so từng khóa với tệp nguồn), kết quả trong `demo_rt_01_reconcile.csv`: cả ba bảng PASS, 0 khóa lệch.
- Bảng theo cửa sổ thời gian chỉ so các cửa sổ trước 2008-04-07T12:00:00Z (cửa sổ cuối chưa đóng): 74 399 giao dịch.
- Số 75 251 lấy từ tổng `transaction_count` trong PostgreSQL sau khi Producer đã dừng; đối soát khớp từng khóa với đúng số dòng đầu này của tệp nguồn. Chưa lưu bản in JSON của Producer.
- Sau đối soát, dữ liệu `demo_rt_01` đã được xóa để dùng lại mã lượt chạy.
- Chưa đo độ trễ đầu-cuối; thư mục này không phải minh chứng cho R14.

## Lượt chạy khi quay video (27/11/2026)

- Cùng luồng, mã lượt `demo_rt_01`; Producer dừng sau 27 115 giao dịch.
- Kết quả đối soát trong `demo_recorded_reconcile.csv`: cả ba bảng PASS, 0 khóa lệch. Bảng theo cửa sổ thời gian chỉ so cửa sổ đã đóng: 16 423 giao dịch.
