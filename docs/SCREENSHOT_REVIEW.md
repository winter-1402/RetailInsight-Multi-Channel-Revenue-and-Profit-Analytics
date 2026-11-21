# Xác nhận dashboard qua giao diện thật

Kiểm tra ngày 16/11/2026 trên Chrome, cửa sổ 1440 × 852, tại `http://127.0.0.1:8501`. Đây là ảnh chụp cửa sổ ứng dụng thật, giữ nguyên nội dung và không ghép/dựng lại. Các ảnh 01–08 được chụp trước bản sửa bố cục ngày; ảnh 09 xác minh bản sửa cuối. File này ghi riêng thao tác đã quan sát trực tiếp và phạm vi được kiểm thử tự động.

| Bước | Nội dung xác nhận trực tiếp | Minh chứng |
|---|---|---|
| 1 | Toàn kỳ: doanh thu 109.809.274,20 USD; lợi nhuận gộp 12.551.366,25 USD; biên 11,43%; MoM tháng 10/2013 +36,50%; 31.455 đơn và 121.253 dòng | [01 — Tổng quan](screenshots/01-overview.png) |
| 2 | Biểu đồ danh mục và biên kênh; ba nhận xét Internet, Xe đạp và Southwest gắn với số liệu và điều kiện kiểm tra | [02 — Nhận xét](screenshots/02-overview-insights.png) |
| 3 | Bảng kênh: Internet doanh thu 29.358.677,22 USD, lợi nhuận 12.080.883,64 USD; Reseller doanh thu 80.450.596,98 USD, lợi nhuận 470.482,60 USD | [03 — Kênh](screenshots/03-channels.png) |
| 4 | Biểu đồ vùng theo kênh và bảng USD; giữ cả dòng lỗ, ví dụ Southwest/Reseller −15.619,90 USD | [04 — Vùng](screenshots/04-regions.png) |
| 5 | Bảng xếp hạng sản phẩm và biểu đồ dùng đơn vị USD, có doanh thu, lợi nhuận, biên, số đơn và số lượng | [05 — Sản phẩm](screenshots/05-products.png) |
| 6 | Bảng trước–sau cho 8 bảng nguồn, số dòng hợp lệ, trùng, cách ly và tỷ lệ thiếu; không tự tạo số dòng lỗi | [06 — Chất lượng](screenshots/06-quality-benchmark.png) |
| 7 | Biểu đồ/bảng pandas và Spark SQL, thời gian trung vị theo giây và cột khớp chính xác; trang này ghi rõ dùng toàn run, không chịu bộ lọc kinh doanh | [07 — Benchmark](screenshots/07-benchmark.png) |
| 8 | Chọn Internet: KPI thành 29.358.677,22 USD, lợi nhuận 12.080.883,64 USD, biên 41,15%, MoM tháng 12/2013 +5,25%; donut chỉ còn Internet | [08 — Sau lọc](screenshots/08-filter-internet.png) |
| 9 | Đặt lại: trở về hai kênh và số liệu toàn kỳ; bản sửa cuối không còn cảnh báo trùng giá trị mặc định ngày | [09 — Reset](screenshots/09-reset.png) |

## Lỗi phát hiện và đã sửa

Khi reset, callback gán ngày qua Session State nhưng widget cũng truyền giá trị mặc định, gây cảnh báo Streamlit. Đã thống nhất giá trị ban đầu trong Session State, bỏ mặc định trùng, mở rộng ô ngày thành hàng riêng và kiểm tra khi ngày bị xóa. Kiểm thử hồi quy tái hiện lỗi trước khi sửa, sau đó kiểm tra không có warning/exception và tổng tiền trở lại đúng.

## Giới hạn của lượt quan sát

Lượt này trực tiếp kiểm tra các trang và thao tác lọc kênh/reset ở kích thước desktop. Bộ lọc vùng/danh mục/sản phẩm/đại lý, ngày đảo, dữ liệu rỗng và CSV còn có kiểm thử tự động; không gọi các trường hợp đó là đã thao tác bằng tay trong lượt chụp này. Chưa xác nhận trên thiết bị di động hoặc trình duyệt khác.
