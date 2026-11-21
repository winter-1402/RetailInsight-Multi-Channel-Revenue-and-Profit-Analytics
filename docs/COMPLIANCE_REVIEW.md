# Biên bản rà soát kỹ thuật

Ngày rà soát: 16/11/2026. Phạm vi: pipeline dữ liệu, độ chính xác KPI, dashboard, benchmark và khả năng tái lập. Mã triển khai nằm trên nhánh `feat/assignment-completion-20261116`.

## Kết quả đối chiếu

| Yêu cầu | Kết quả và minh chứng |
|---|---|
| Hai câu hỏi kinh doanh, người dùng cuối | README; báo cáo PDF/Markdown xác định quản lý bán hàng và tài chính, so sánh hiệu quả kênh và ưu tiên danh mục/vùng |
| Giao dịch, sản phẩm, cửa hàng/đại lý, kênh và chi phí | Hai fact và 6 chiều, gồm DimReseller. Mart có store_id/store/store_type; 701 đại lý trong chiều, 635 có giao dịch. Internet được ghi rõ không có mã cửa hàng vật lý, không tạo dữ liệu giả bổ sung |
| Nguồn, giấy phép, schema, thời gian, số dòng | DATA_SOURCES.md; manifest URL/SHA-256/kiểu cột; 121.253 dòng, 31.455 đơn; MIT license Microsoft |
| Làm sạch thiếu/trùng, ngày và ngoại lệ, trước–sau | clean_source; quality JSON/CSV; mẫu trước–sau hai fact; cách ly và kiểm tra khóa. Không loại giao dịch lỗ |
| Spark SQL tổng hợp và phân khúc | Bốn SQL trong sql/retail; đầu ra spark_monthly/region/category/customer_segments |
| Ít nhất ba ca kiểm thử | Kiểm thử tiền, discount, FK/grain, dòng trùng, tháng thiếu, nguồn cửa hàng, bộ lọc, CSV, Spark thực, PDF và đóng gói |
| Baseline pandas so Spark SQL cùng dữ liệu | Ba truy vấn, cùng Parquet và cột, 3 lượt/công cụ; kiểm tra chính xác từng nhóm, log môi trường và JVM startup riêng |
| Giới hạn hệ thống và quy mô | Báo cáo đúng quy mô local; thử tải 5× ghi rõ là bản sao; không gọi đây là chứng minh xử lý Big Data phân tán |
| KPI doanh thu thuần, biên lợi nhuận, tăng trưởng tháng | Công thức/đơn vị/phạm vi/giá trị thực trong README, báo cáo và dashboard. Không trừ discount hai lần, không lấy trung bình margin dòng |
| Dashboard có bộ lọc kênh, vùng, sản phẩm | Bốn trang; bộ lọc ngày/kỳ chung/kênh/vùng/danh mục/đại lý/sản phẩm và reset; các chỉ số/bảng/CSV cùng scope |
| Ba nhận xét theo số liệu và quyết định có điều kiện | Dashboard Tổng quan; báo cáo bảng hành động/chi phí/rủi ro/điều kiện; không suy ra lợi nhuận ròng từ lợi nhuận gộp |
| Mã, README tái lập, mẫu dữ liệu, PDF, demo | Được đưa vào nhánh và ZIP; dữ liệu raw có sẵn trong repo được tái sử dụng; mẫu mart thể hiện cả hai kênh |
| Log chạy pipeline và minh chứng chất lượng | Mỗi run có pipeline.log thực thi; output/evidence chứa pipeline.log, test_status, log kiểm thử, CSV và manifest |
| URL repository | https://github.com/winter-1402/RetailInsight-Multi-Channel-Revenue-and-Profit-Analytics |

## Trạng thái kiểm chứng và giới hạn

1. **Ảnh dashboard — đã bổ sung:** ngày 16/11/2026 lưu 9 ảnh cửa sổ Chrome thật, gồm tổng quan, nhận xét, kênh, vùng, sản phẩm, chất lượng, benchmark, lọc Internet và reset. Xem [xác nhận từng bước](SCREENSHOT_REVIEW.md). Không còn thiếu bộ ảnh; phạm vi quan sát desktop và giới hạn kiểm tra được ghi rõ.
2. **Môi trường vận hành:** đã kiểm chứng local; chưa kiểm tra triển khai phân tán, thiết bị di động, tải đồng thời hoặc xác thực cho dịch vụ công khai.
3. **Nguồn và phương pháp:** dữ liệu Microsoft là mẫu giả lập; chi phí dùng giá vốn, chưa đủ để tính lợi nhuận ròng. Việc sử dụng AI được mô tả tại [AI_USAGE.md](AI_USAGE.md).

Các chức năng có mã nguồn và bằng chứng tái lập tương ứng. Trạng thái local, CI và khả năng triển khai được đánh giá riêng; kết quả kiểm thử không được dùng để suy ra mức sẵn sàng production.
