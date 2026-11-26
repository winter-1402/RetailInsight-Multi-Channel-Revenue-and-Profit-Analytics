# Phân tích doanh thu và lợi nhuận bán lẻ đa kênh

Báo cáo kỹ thuật RetailInsight. Nguồn Microsoft AdventureWorksDW, dữ liệu doanh nghiệp **giả lập**, giấy phép MIT.

## 1 Bài toán và phạm vi

Người dùng cuối là quản lý bán hàng và tài chính. Hai câu hỏi: kênh doanh thu cao có đồng thời tạo hiệu quả giá vốn cao không; danh mục/vùng nào đóng góp lợi nhuận gộp đáng ưu tiên kiểm tra?

Phạm vi: 121,253 dòng bán hàng, 31,455 đơn, 2010-12-29 đến 2014-01-28. Internet kết thúc ngày 28/01/2014; Reseller kết thúc ngày 29/11/2013. Không coi khác biệt thời gian ghi nhận là biến động nhu cầu.

## 2 Dữ liệu và quản lý chất lượng

Commit nguồn: `b47eadc85277f72843647223cde53aa1b85ffcb8`. [Nguồn và link tải](DATA_SOURCES.md). CSV UTF-8, phân cách `|`, không có header; đọc tên cột từ DDL chính thức, không thực thi DDL.

| Bảng | Đầu vào | Hợp lệ | Trùng đã loại | Cách ly |
|---|---:|---:|---:|---:|
| FactInternetSales | 60,398 | 60,398 | 0 | 0 |
| FactResellerSales | 60,855 | 60,855 | 0 | 0 |
| DimProduct | 606 | 606 | 0 | 0 |
| DimProductSubcategory | 37 | 37 | 0 | 0 |
| DimProductCategory | 4 | 4 | 0 | 0 |
| DimSalesTerritory | 11 | 11 | 0 | 0 |
| DimCurrency | 105 | 105 | 0 | 0 |
| DimReseller | 701 | 701 | 0 | 0 |

Giữ nguyên nguồn; loại trùng hoàn toàn; chuẩn hóa trường dùng trong phân tích; cách ly dòng sai ngày/tiền/số lượng. Dừng khi khóa chính xung đột hoặc khóa ngoại thiếu. Không loại các giao dịch có giá vốn lớn hơn doanh thu. Các ô thiếu ở trường mô tả/ảnh tùy chọn được giữ, không tự điền thành số tiền.

Mỗi file có URL, SHA-256, số byte và schema trong manifest; quality JSON lưu số ô thiếu trước–sau theo cột. DiscountAmount là FLOAT, cho phép sai số đối soát 0,0001 USD/dòng; SalesAmount và TotalProductCost được giữ chính xác với 4 chữ số thập phân.

## 3 Pipeline và mô hình dữ liệu

Nguồn Microsoft → Python kiểm tra/làm sạch → Parquet Silver → mart một dòng mặt hàng → đối chiếu công cụ → dashboard và quyết định. Dashboard tính lại từ cùng mart khi lọc, trang kiểm chứng đọc đầu ra Spark và benchmark toàn run.

Khóa dòng: kênh + SalesOrderNumber + SalesOrderLineNumber. Khóa đơn thêm tiền tố kênh. Chiều sản phẩm → nhóm → danh mục, vùng, đại lý DimReseller và tiền tệ được ghép nhiều-một; có kiểm tra không nhân đôi doanh thu. DimReseller có 701 đại lý, 635 có giao dịch; Internet không có mã cửa hàng vật lý. Mỗi run có thư mục riêng; chỉ chuyển current.txt khi nạp thành công.

## 4 KPI và kết quả đo

| KPI | Công thức | Kết quả toàn kỳ |
|---|---|---:|
| Doanh thu thuần | SUM(SalesAmount) | 109.809.274,20 USD |
| Lợi nhuận gộp | SUM(SalesAmount − TotalProductCost) | 12.551.366,25 USD |
| Biên gộp | Tổng lợi nhuận / tổng doanh thu × 100 | 11,4302% |
| Tăng trưởng 2013-10 | (Doanh thu tháng / tháng lịch trước − 1) × 100 | +36,4968% |

SalesAmount đã trừ chiết khấu nên không trừ thêm DiscountAmount. Không cộng TaxAmt/Freight vào doanh thu. Biên dùng tỷ lệ của các tổng, không lấy trung bình tỷ lệ từng dòng. Mẫu số bằng 0 hoặc thiếu kỳ trước: không xác định.

KPI tăng trưởng chọn tháng đủ phạm vi nguồn gần nhất và yêu cầu tháng trước cũng đủ phạm vi. Cờ này chỉ xét biên thời gian; không bảo đảm nguồn không thiếu giao dịch. Lợi nhuận gộp chưa trừ vận hành, marketing, thuế thu nhập và hoàn trả chưa có trong nguồn.

| Kênh | Doanh thu USD | Giá vốn USD | Lợi nhuận gộp USD | Biên % |
|---|---:|---:|---:|---:|
| Internet | 29.358.677,22 | 17.277.793,58 | 12.080.883,64 | 41,15 |
| Reseller | 80.450.596,98 | 79.980.114,38 | 470.482,60 | 0,58 |

![Doanh thu và lợi nhuận theo kênh](figures/channel_results.png)

*Biểu đồ tổng hợp sinh từ mart, không phải ảnh chụp giao diện.*

## 5 Baseline và thực nghiệm

Các truy vấn tổng hợp theo tháng/kênh, vùng/kênh, danh mục/kênh và phân khúc người mua. Các công cụ đọc cùng Parquet và dùng cùng phép tính. Kết quả được đối chiếu từng nhóm với pandas.

Mỗi công cụ chạy 3 lần/truy vấn, thứ tự luân phiên; không loại lượt đầu; không dùng persist/cache Spark; không xóa cache OS. JVM khởi động riêng 26.92 giây. Mốc đo gồm đọc, groupby/distinct, sort và collect, không bao gồm tải nguồn hoặc tạo mart.

Cấu hình: Windows-11-10.0.26300-SP0; Python 3.12.8; Spark 4.0.1; 22 CPU logic; local[2], 4 shuffle partitions; JDK trong metadata.

| Truy vấn | pandas (s) | DuckDB (s) | Spark SQL (s) | Khớp |
| --- | ---: | ---: | ---: | --- |
| monthly | 0.1040 | 0.0259 | 0.9143 | Chính xác |
| region | 0.1081 | 0.0287 | 0.6163 | Chính xác |
| category | 0.1065 | 0.0293 | 0.5403 | Chính xác |
| customer_segments | 0.0958 | 0.0187 | 0.5573 | Chính xác |

Thử tải 5×: 606,265 dòng nhân bản, mã đơn/người mua có hậu tố. Đây là bản sao đo tải, không phải giao dịch kinh doanh mới. Bảng từng lần đo nằm trong evidence.

Thời gian trung vị phụ thuộc truy vấn và cấu hình. Chi phí lập kế hoạch, shuffle và trả kết quả về Python ảnh hưởng các số đo Spark trên máy local. Giới hạn và năng lực cụm phân tán cần phép đo riêng.

## 6 Nhận xét và quyết định có điều kiện

1. Reseller chiếm 73,26% doanh thu nhưng biên gộp 0,58%. Rà soát giá vốn và chiết khấu trước khi tăng doanh số bằng giảm giá.
2. Bikes tạo 10.515.096,61 USD lợi nhuận gộp, 83,78% toàn kỳ. Kiểm tra năng lực cung ứng trước khi ưu tiên danh mục.
3. Southwest có doanh thu cao nhất, 24.184.609,60 USD, biên gộp khoảng 9,74%. Đánh giá chi phí phục vụ và biên gộp cùng với doanh thu trước khi mở rộng.

| Hành động | Chi phí/rủi ro | Điều kiện áp dụng |
|---|---|---|
| Thử ngân sách nhỏ ở Internet | Chi phí thu hút khách có thể ăn hết biên gộp | Bổ sung marketing/vận hành, đo nhóm thử nghiệm |
| Rà soát discount Reseller | Mất đại lý hoặc doanh số nếu cắt ưu đãi mạnh | Kiểm tra hợp đồng và nhóm sản phẩm lỗ trước |
| Ưu tiên kiểm tra Bikes | Phụ thuộc danh mục và nguy cơ thiếu hàng | Bổ sung tồn kho, lead time và chi phí cung ứng |

## 7 Dashboard kiểm thử và tái lập

Bốn trang: Tổng quan; Kênh và thị trường; Sản phẩm; Dữ liệu và kiểm chứng. Bộ lọc gọn có Tất cả, ngày/kỳ chung, kênh/vùng/danh mục/đại lý, tìm sản phẩm liên kết và nút đặt lại. KPI, biểu đồ, bảng và CSV dùng chung scope. Sản phẩm lỗ vẫn hiển thị; ngày đảo/rỗng có thông báo; bảng xuất dùng USD thay vì đơn vị lưu trữ.

Các ca kiểm thử, phương pháp đối chiếu và giới hạn kiểm tra UI: [VALIDATION.md](VALIDATION.md). Hướng dẫn chạy: [README](../README.md). Demo: [DEMO.md](DEMO.md). Log và dữ liệu mẫu: [output/evidence](../output/evidence).

[Repository dự án](https://github.com/winter-1402/RetailInsight-Multi-Channel-Revenue-and-Profit-Analytics). Trạng thái CI cần kiểm tra trên đúng commit ở GitHub Actions. Ảnh giao diện thật và xác nhận từng bước: [SCREENSHOT_REVIEW.md](SCREENSHOT_REVIEW.md).

## 8 Nguồn và công cụ AI

[Microsoft AdventureWorksDW](DATA_SOURCES.md); MIT license được giữ nguyên trong evidence. [Sử dụng công cụ AI](AI_USAGE.md). Dữ liệu, số đo và hình minh họa có nguồn truy vết. Kết quả cần được kiểm chứng lại trên môi trường triển khai trước khi sử dụng để ra quyết định.
