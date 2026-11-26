# Q1–Q8: pandas và Spark SQL

Trạng thái: **passed**.

Run: `20261126T084958558373Z`; số mẫu đã ghi: 80.

CPU: Intel(R) Core(TM) Ultra 7 155H; RAM: 16866729984 byte; CPU logic: 22.

OS: Windows-11-10.0.26300-SP0; Python: 3.12.8; pandas: 2.2.3; Spark: 4.0.1.

Spark startup: 7.1869277998339385 giây. Chi tiết cấu hình và giới hạn bộ nhớ: [environment.json](environment.json).

| Q | pandas median (s) | Spark median (s) | Spark/pandas | Dòng kết quả | Khớp |
|---|---:|---:|---:|---:|---|
| Q1 | 0.002200 | 0.147654 | 67.12× | 282 | 100% |
| Q2 | 0.060101 | 0.613807 | 10.21× | 635 | 100% |
| Q3 | 0.170845 | 1.351069 | 7.91× | 7 | 100% |
| Q4 | 0.080390 | 0.665267 | 8.28× | 64 | 100% |
| Q5 | 1.071699 | 1.175112 | 1.10× | 71 | 100% |
| Q6 | 0.084237 | 0.603353 | 7.16× | 169 | 100% |
| Q7 | 0.052837 | 0.661725 | 12.52× | 3 | 100% |
| Q8 | 0.065935 | 0.648700 | 9.84× | 10 | 100% |

Tỷ số >1 nghĩa là pandas nhanh hơn. Chỉ so sánh hai engine trong cùng Q.

Mốc đo: truy vấn bảng pandas trong bộ nhớ / temporary view Spark → JOIN/filter/group/window/sort → materialize về pandas. Không đọc Parquet. Không tính chuẩn bị nguồn, nạp bảng vào Spark, khởi động JVM, hash, đối chiếu, ghi CSV hoặc lấy execution plan.

Nạp bảng vào Spark: 2.864823100157082 giây. Không persist/cache dữ liệu ứng dụng; không xóa cache OS. Giữ lượt đầu, không bỏ warm-up. Thứ tự Q xáo bằng seed cố định; luân phiên engine.

Các truy vấn chẩn đoán EXPLAIN chạy sau các lượt đo để tránh làm nóng optimizer trước phép đo. Mỗi Q lưu formatted plan trước action và executed plan sau action.

Số tiền là số nguyên 1/10.000 USD; so khớp tuyệt đối từng ô sau sắp thứ tự. Q7 phân tích loại hình đại lý, không giả lập phương thức thanh toán.

Không đo peak memory, tải nền hoặc tốc độ ổ đĩa. Local[2] không chứng minh hiệu năng cụm phân tán.

Minh chứng: [measurements.csv](measurements.csv), [summary.csv](summary.csv), [input_manifest.json](input_manifest.json), [environment.json](environment.json), [benchmark.log](benchmark.log), thư mục `results/` và `plans/`. SQL và SHA-256 được lưu trong environment.json.
