# Kịch bản demo 6–8 phút

Chuẩn bị bằng `run.cmd technical`, sau đó `run.cmd dashboard`. Nếu chỉ cần mở dashboard và chưa có mart, chạy `run.cmd pipeline` trước.

1. **Bài toán và nguồn — 1 phút.** Nêu hai câu hỏi kinh doanh trong README, người dùng quản lý bán hàng/tài chính. Giới thiệu dữ liệu mẫu Microsoft, hai kênh, giá vốn và chiết khấu; không gọi là dữ liệu doanh nghiệp thực.
2. **Pipeline — 1 phút.** Mở sơ đồ README và quality/manifest. Giải thích CSV `|`, schema ghim phiên bản, số nguyên tiền 1/10.000 USD, khóa có kênh, cách ly lỗi và công bố run sau khi kiểm tra xong.
3. **Dashboard — 2 phút.** Đối chiếu toàn kỳ: doanh thu 109.809.274,20 USD, lợi nhuận gộp 12.551.366,25 USD, biên 11,43%. Chọn Internet rồi Reseller; quan sát KPI và biểu đồ đổi cùng phạm vi. Chọn danh mục và tìm sản phẩm, đổi danh mục để kiểm tra tự đặt lại sản phẩm không phù hợp. Dùng nút đặt lại.
4. **Tháng và điều kiện biên — 1 phút.** Chọn kỳ chung hai kênh. Giải thích KPI tăng trưởng dùng cặp tháng trong phạm vi nguồn, tháng trước 0 trả không xác định. Chọn Internet + Linh kiện để thấy trạng thái không có giao dịch; đặt lại. Thử Reseller + AWC Logo Cap để thấy lợi nhuận âm vẫn được giữ.
5. **Benchmark — 1 phút.** Mở Dữ liệu và kiểm chứng → Hiệu năng và ba SQL. Cùng dữ liệu/phép tính, 3 lượt đo, JVM riêng, cache OS không xóa, kết quả khớp từng nhóm. pandas nhanh hơn ở quy mô local; không suy ra kết luận cho cụm phân tán. Tải 5× chỉ là bản sao thử tải.
6. **Quyết định và kiểm thử — 1 phút.** Rà soát chiết khấu/giá vốn Reseller; thử ngân sách có kiểm soát ở Internet; kiểm tra khả năng cung ứng Bikes. Nêu điều kiện marketing, vận hành, tồn kho còn thiếu. Mở log kiểm thử và khai báo AI.

Bộ ảnh tham chiếu và các thao tác đã xác nhận được lưu tại [SCREENSHOT_REVIEW.md](SCREENSHOT_REVIEW.md). Các biểu đồ tổng hợp trong báo cáo được sinh từ mart và phân biệt rõ với ảnh chụp dashboard.

Cần giải thích được vì sao không trừ DiscountAmount hai lần, không lấy trung bình biên từng dòng, không cộng số đơn giữa các nhóm nhiều danh mục, và không bỏ các giao dịch lỗ.
