# Phương pháp kiểm chứng

## Dữ liệu và công thức

- Nguồn Microsoft được ghim commit; từng CSV có URL, SHA-256, schema và số byte trong manifest.
- Hai fact có tổng 121.253 dòng; kiểm tra `line_id` duy nhất và ghép chiều nhiều-một.
- Doanh thu/giá vốn/lợi nhuận dùng số nguyên 1/10.000 USD; đối chiếu nguồn bằng số thập phân.
- SalesAmount đã trừ DiscountAmount. DiscountAmount là FLOAT trong nguồn; kiểm tra gross−discount−net cho phép sai số 0,0001 USD/dòng.
- Tiền âm, ngày lỗi, số lượng sai được cách ly; trùng khóa xung đột hoặc FK thiếu làm dừng nạp. Không loại lợi nhuận âm.

## Kiểm thử tự động

`python -m pytest -q` chạy toàn bộ test. `python -m src.utils.delivery --verify` lưu stdout/stderr thực và mã thoát vào `output/evidence/tests.log` và `test_status.json`.

Ngày 26/11/2026 trên Windows, bản `finish/retailinsight` cài sạch với Python 3.12.8 và Temurin 17. `pip check` báo không có xung đột. Kết quả gồm **58/58 test đạt**, **72/72 lượt mart 1×/5× khớp chính xác** và **80/80 lượt Q1–Q8 khớp chính xác**. `run.cmd dashboard` trả HTTP 200 ở điểm kiểm tra dịch vụ và AppTest đọc đủ 12 hàng so sánh. Xem [minh chứng lượt chạy](../output/evidence/README.md).

Ngày 17/11/2026, sau khi gom mã/SQL vào `src/benchmark/` và test vào `tests/benchmark/`: **57/57 test đạt**, mã thoát 0. Bao gồm thực thi Spark, dashboard AppTest, đóng gói ZIP và chạy `--help` các module từ gói đã giải nén.

| File | Phạm vi |
|---|---|
| test_retail.py | Độ chính xác tiền, chiết khấu, chất lượng, margin, calendar, grain, FK và công bố run |
| test_analytics.py | Cặp tháng đủ phạm vi, tháng trống, mẫu số 0, lọc bao gồm cuối ngày, tổng hợp, CSV và định dạng Việt |
| test_dashboard.py | Giá trị toàn kỳ, chọn kênh, kỳ tăng trưởng từng kênh, sản phẩm liên kết, reset, rỗng, ngày đảo, giao dịch lỗ |
| benchmark/test_mart.py | Spark SQL thực: fixture tính tay, NULL, rỗng, tiền lớn, lỗ/0, phân khúc sát ngưỡng, phát hiện sai nhóm dù tổng đúng, metadata và lỗi khởi động |
| benchmark/test_sql_benchmark.py | Q1–Q8: ngưỡng giá, JOIN/FK, NULL, năm-tháng, ties/top-N, tiền lớn, giữ nguyên raw và từ chối công bố kết quả sai |
| test_report.py | PDF/Markdown chứa số liệu thực, tính chất giả lập và kỳ so sánh đúng |
| test_delivery.py | ZIP có entrypoint/theme/CI/PDF, không chứa dữ liệu thô, bytecode, môi trường hoặc mã cũ |

AppTest thực thi ứng dụng và các biểu đồ/bảng nhưng không thay thế kiểm tra bằng mắt. Ngày 16/11/2026 đã lưu 9 ảnh cửa sổ Chrome thực tế: [xác nhận từng bước](SCREENSHOT_REVIEW.md). Đã quan sát các trang, bộ lọc Internet và reset; bản sửa reset loại cảnh báo mặc định ngày, kiểm tra ngày bị xóa và mở rộng ô ngày. Hình tổng hợp trong PDF vẫn là biểu đồ dữ liệu, được phân biệt với ảnh UI trong docs/screenshots.

## Benchmark

[Kế hoạch chi tiết và kết quả baseline mới](SPARK_SQL_TEST_PLAN.md) ghi cấu hình CPU/RAM, hash dữ liệu/SQL, cách đo và kế hoạch Q1–Q8 phù hợp AdventureWorks. CSV gốc không bị thay đổi.

Cùng Parquet, cột và phép tính cho pandas, DuckDB và Spark SQL. Mốc đo gồm đọc, tổng hợp, sắp xếp và nhận kết quả. Ba lượt cho mỗi công cụ và truy vấn, luân phiên thứ tự. Lượt pandas đầu làm tham chiếu và được giữ trong kết quả. Khởi động JVM ghi riêng, giữ cache OS. `assert_frame_equal` kiểm tra khóa và từng giá trị theo nhóm. Các truy vấn SQL ghi `NULLS LAST` để cùng thứ tự với pandas.

Tải 5× là bản sao 606.265 dòng, mã đơn/người mua có hậu tố từng bản sao. Không trộn dữ liệu này với dashboard kinh doanh. Chưa kiểm tra cụm phân tán, giới hạn bộ nhớ cực đại hoặc ngưỡng Spark vượt pandas.

## Bổ sung trong nhánh rà soát

Kiểm tra DimReseller nhiều-một, mã cửa hàng thiếu đúng nghĩa ở Internet, bộ lọc đại lý và reset. Mẫu bán hàng giữ 10 dòng mỗi kênh và mỗi lượt nạp có `pipeline.log`. Pytest dùng thư mục tạm riêng theo cơ chế mặc định để tránh va chạm với `.pytest-tmp` tồn tại từ lượt cũ. Cache kiểm thử nằm trong `.cache/pytest-cache`.
