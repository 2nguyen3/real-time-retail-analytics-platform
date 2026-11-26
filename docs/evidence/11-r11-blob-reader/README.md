# R11: đọc từ Blob Storage đến chương trình, CSV không nén so với gzip (26/11/2026)

## Thiết lập

| Mục | Giá trị |
|---|---|
| Biến thay đổi | Cách lưu tệp trên Blob: CSV không nén (trước) hoặc gzip mức 6 (sau) |
| Dữ liệu | 3 tệp tuần dunnhumby (200807–200809): 1 144 356 908 byte CSV, 8 019 568 dòng |
| Nơi đọc | VM Azure `Standard_D4as_v4`, East Asia, cùng vùng với Blob (tầng Hot) |
| Công cụ | `tests/benchmark/blob_reader.py`: tải qua HTTPS bằng managed identity (không dùng khóa), giải nén và đọc từng dòng CSV trong bộ nhớ, không ghi đĩa |
| Đoạn đo | Từ lúc gửi yêu cầu tải tệp đầu tiên đến lúc đọc xong dòng cuối của tệp thứ ba (3 tệp đọc lần lượt) |
| Số lượt | 1 lượt làm nóng (không ghi) và 3 lượt mỗi cấu hình, chạy xen kẽ |
| Kiểm tra đúng | Cả 6 lượt cùng 8 019 568 dòng và tổng số lượng 12 067 777; số dòng khớp số đếm trên CSV gốc |

## Kết quả (trung vị 3 lượt)

| Số đo | Không nén | Gzip | Thay đổi |
|---|---:|---:|---|
| Dung lượng lưu trên Blob (byte) | 1 144 356 908 | 124 662 335 | giảm 89,1% (còn khoảng 1/9) |
| Byte truyền khi đọc | 1 144 356 908 | 124 662 335 | giảm 89,1% |
| Thời gian đọc đầu-cuối (giây) | 14,40 (13,89–14,48) | 15,07 (14,96–15,21) | chậm hơn khoảng 4,7% |
| Dòng/giây | 556 789 | 532 026 | giảm khoảng 4,4% |
| MB CSV gốc/giây | 79,45 | 75,92 | giảm khoảng 4,4% |
| Thời gian CPU (giây) | 13,94 | 14,87 | tăng khoảng 6,7% |
| Chờ byte đầu tiên (ms, trung vị) | 80,4 | 69,7 | dao động 51–82 ms, không kết luận |

Chi phí phía ghi: nén gzip mất 4,8–5,1 giây mỗi tệp khoảng 381 MB (đo trên máy phát triển, một lần mỗi tệp; `r11-compress-time.txt`), không phải trên VM.

## Nhận xét

- Nén gzip giảm mạnh dung lượng lưu và dữ liệu truyền qua mạng.
- Tốc độ đọc đến chương trình **không cải thiện**: gzip chậm hơn một chút. Thời gian CPU gần bằng tổng thời gian ở cả hai cấu hình, nên trong thiết lập này giới hạn là CPU của chương trình đọc (Python, một luồng: giải mã và tách CSV), không phải đường truyền trong cùng vùng. Giải nén thêm việc cho CPU.
- Đánh đổi: nếu ưu tiên chi phí lưu trữ và truyền dữ liệu thì chọn gzip; nếu ưu tiên thời gian đọc trong cùng vùng với chương trình đọc này thì hai cách gần nhau, không nén nhanh hơn một chút.

## Giới hạn

- Chỉ đo trong cùng vùng, một loại VM, một chương trình đọc một luồng. Chưa đo qua mạng chậm hơn; không suy ra kết quả cho trường hợp đó.
- Đo đọc, không đo tốc độ ghi lên Blob. Pipeline benchmark không đọc dữ liệu từ Blob.
- Dung lượng và tỷ lệ nén đo trên 3 trong 13 tệp.
