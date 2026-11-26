# Phạm vi chức năng và tiêu chí kiểm chứng

Tài liệu ánh xạ các yêu cầu phân tích bán lẻ đa kênh với mã nguồn, kết quả thực thi và tài liệu tương ứng.

| Yêu cầu | Minh chứng |
|---|---|
| Hai câu hỏi kiểm chứng và người dùng cuối | README; báo cáo PDF và Markdown |
| Nguồn, giấy phép, schema, thời gian, số dòng | DATA_SOURCES.md; manifest.json; MICROSOFT_LICENSE.txt |
| Cửa hàng/đại lý và chi phí | DimReseller; store_id/store/store_type trong mart; TotalProductCost làm giá vốn; Internet không có mã cửa hàng vật lý |
| Thiếu/trùng, thời gian, ngoại lệ và trước–sau | clean_source; quality_summary.csv; data_quality.json; mẫu before/after |
| Pipeline thu thập → làm sạch → lưu → phân tích → BI | src/ingestion/source.py; src/cleaning/source.py; src/pipeline/retail.py; src/benchmark/mart.py; dashboard/dashboard.py |
| Spark SQL tổng hợp và phân khúc | sql/retail; spark_monthly/region/category/customer_segments.csv |
| Dashboard kênh, vùng, sản phẩm và bộ lọc | Bốn trang, lựa chọn Tất cả, kỳ chung, bộ lọc liên kết và reset |
| Doanh thu thuần, biên lợi nhuận, tăng trưởng tháng | analytics.py; KPI dashboard; công thức và giá trị trong báo cáo |
| Ít nhất 3 kiểm thử | tests/test_retail.py, tests/test_analytics.py, tests/test_dashboard.py, tests/benchmark/ |
| Baseline pandas, DuckDB và Spark SQL; thời gian và độ khớp | Bốn truy vấn ở 1× và 5×, benchmark.csv, summary, environment và EXPLAIN. Bộ Q1–Q8 đo riêng. |
| Cấu hình, cùng dữ liệu và giới hạn hệ thống | Phương pháp đo trong báo cáo; môi trường benchmark; tải 5× riêng |
| Ít nhất 3 nhận xét và quyết định có điều kiện | Trang Tổng quan; báo cáo kết quả; bảng chi phí/rủi ro/điều kiện |
| Mã, README, dữ liệu mẫu hoặc script tải | Gói GitHub whitelist; pipeline --download; output/evidence |
| Báo cáo PDF/DOCX, kiến trúc, thực nghiệm, sai số | PDF và docs/BAO_CAO.md; sơ đồ pipeline; dung sai tiền; kỳ biên |
| Slide/demo | docs/DEMO.md; ứng dụng Streamlit chạy local |
| Log và mẫu đầu ra | output/evidence; --verify lưu mã thoát và stdout thực |
| Hình minh chứng | 9 ảnh cửa sổ Chrome thật và bảng xác nhận tại docs/SCREENSHOT_REVIEW.md; biểu đồ từ mart được phân biệt với ảnh UI |
| Liên kết repository | [RetailInsight, nhánh finish/retailinsight](https://github.com/winter-1402/RetailInsight-Multi-Channel-Revenue-and-Profit-Analytics/tree/finish/retailinsight) |
| Minh bạch việc sử dụng công cụ AI | docs/AI_USAGE.md; phần phương pháp trong báo cáo |

Phạm vi kiểm chứng hiện tại là môi trường local. Các phép đo không chứng minh khả năng mở rộng trên cụm phân tán hoặc mức sẵn sàng vận hành production. Trạng thái CI và giới hạn kiểm tra giao diện được ghi riêng trong biên bản rà soát.


Rà soát ngày 16/11/2026 và trạng thái các minh chứng: [COMPLIANCE_REVIEW.md](COMPLIANCE_REVIEW.md).
