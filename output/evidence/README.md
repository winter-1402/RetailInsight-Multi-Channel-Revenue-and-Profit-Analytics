# Minh chứng thực thi

- `manifest.json`, `pipeline.log` và `quality_summary.csv` ghi lần nạp, nguồn đã ghim và chất lượng trước–sau.
- `sample_sales.csv`, `monthly_sales.csv` và các tệp `Fact*before.csv` / `Fact*after.csv` dùng để đối chiếu KPI, kiểu tiền và biến đổi dữ liệu.
- `benchmark*.csv`, các tệp kết quả từng công cụ và `sql_plans.txt` ghi chi tiết bốn truy vấn mart 1×. Các tệp `load_scale_5_*` ghi phép thử tải mô phỏng.
- `tests.log` và `test_status.json` giữ kết quả kiểm thử cục bộ. `github_ci_status.json` là bản ghi GitHub Actions lịch sử, có nhánh và commit riêng.

[Bộ Q1–Q8 và EXPLAIN](../sql_benchmark/README.md) · [Báo cáo CO4033 và số đo tham chiếu](../../docs/reports/README.md)
