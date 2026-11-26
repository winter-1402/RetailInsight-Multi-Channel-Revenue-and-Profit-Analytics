# Quy trình phát triển và phát hành

[Repository RetailInsight](https://github.com/winter-1402/RetailInsight-Multi-Channel-Revenue-and-Profit-Analytics). Bản hoàn chỉnh ở nhánh `finish/retailinsight`.

## Bộ hồ sơ

`python -m src.utils.delivery --verify --package` lưu log kiểm thử, xuất minh chứng từ run hiện hành và tạo `output/AdventureWorks_Retail_BI_GitHub.zip`.

ZIP gồm mã nguồn, SQL, test, giao diện, README, giấy phép, workflow CI, bản công khai PDF và Word của báo cáo CO4033 cùng dữ liệu mẫu và minh chứng. Gói ZIP tải lại dữ liệu nguồn bằng script. Thư mục `.venv`, `.cache` và dữ liệu chạy do pipeline tạo được giữ cục bộ.

## Kiểm tra trước khi xuất bản

1. Chạy `setup.cmd` và `run.cmd technical`. Kiểm tra `output/evidence/test_status.json` có `exit_code = 0`.
2. Mở dashboard bằng `run.cmd dashboard` và đối chiếu KPI. Xem báo cáo kỹ thuật sinh từ lượt chạy và bản CO4033 trong `docs/reports/`.
3. Kiểm tra không có `.env`, khóa/API token, dữ liệu cá nhân, môi trường ảo hoặc tài liệu không được phép tái phát hành.
4. Đọc LICENSE, THIRD_PARTY_NOTICES và AI_USAGE; giữ thông báo nguồn và tuân thủ giấy phép khi phân phối.
5. Xem workflow **Verify pipeline and dashboard** trong tab Actions cho đúng commit sau khi push. CI chỉ dùng nguồn công khai, quyền đọc repository và không deploy. Kết quả local không thay thế kết quả CI.

## Làm việc theo nhánh

Các thay đổi tiếp theo cần có commit rõ mục đích và được review trước khi merge. Không push trực tiếp vào main hoặc ghi đè lịch sử.

```bash
git switch -c ten-nhanh-cong-viec
git status --short
git add .
git diff --cached --stat
git commit -m "Describe the change"
```

Clone repository ở trên và checkout nhánh triển khai để chạy ứng dụng. Nếu dùng ZIP, giải nén trước, tạo môi trường và tải nguồn theo README. Xem trạng thái kiểm chứng tại [COMPLIANCE_REVIEW.md](COMPLIANCE_REVIEW.md).
