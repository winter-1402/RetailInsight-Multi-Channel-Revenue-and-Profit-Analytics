# Kiểm thử và đánh giá thời gian Spark SQL

## 1. Phạm vi và trạng thái

Dataset duy nhất là **Microsoft AdventureWorksDW** hiện có. Không dùng BRL/Olist và không sửa, xóa hoặc ghi đè CSV trong `data/raw`. Chỉ đọc nguồn; giữ bảng chuẩn hóa trong bộ nhớ và ghi kết quả đo vào thư mục dẫn xuất riêng. SHA-256 của nguồn trước/sau phải giữ nguyên.

Benchmark mart so sánh **pandas, DuckDB và Spark SQL** trên tháng/kênh, vùng/kênh, danh mục/kênh và phân khúc. Bộ Q1–Q8 đo JOIN và window trên các bảng đã chuẩn bị. Mã Python ở `src/benchmark/`, tám tệp SQL ở `sql/benchmarks/`.

## 2. Q1–Q8 điều chỉnh theo dataset

| Mã | Truy vấn phù hợp AdventureWorks | Bảng và phạm vi | Độ phức tạp dự kiến | Mục đích |
|---|---|---|---|---|
| Q1 | Sản phẩm có giá niêm yết ≥ **100 USD** | DimProduct; `ListPrice`, không phải giá bán thực tế `UnitPrice` | Thấp | Scan, filter, khả năng predicate pushdown |
| Q2 | Doanh thu theo **đại lý Reseller** | FactResellerSales JOIN DimReseller bằng ResellerKey | Thấp–TB | JOIN nhiều-một, GROUP BY, SUM |
| Q3 | Doanh thu theo danh mục và kênh | Hai fact UNION ALL thành sales; JOIN DimProduct → DimProductSubcategory → DimProductCategory | Trung bình | Ba JOIN qua bốn bảng logic; không ép thành ba bảng như schema Olist |
| Q4 | Doanh thu Reseller theo **quốc gia và bang/tỉnh của đại lý** | FactResellerSales → DimReseller → DimGeography | Trung bình | JOIN ba bảng; không đồng nhất địa chỉ đại lý với vùng bán SalesTerritory |
| Q5 | Doanh thu theo năm-tháng và kênh | Hai fact UNION ALL; JOIN DimDate bằng OrderDateKey → DateKey | Trung bình | JOIN, DATE, GROUP BY; giữ riêng năm để không gộp cùng tháng khác năm |
| Q6 | Top 3 đại lý theo doanh thu trong mỗi quốc gia/bang | Ba bảng của Q4; tổng hợp theo ResellerKey, sau đó ROW_NUMBER theo quốc gia/bang | Cao | JOIN, GROUP BY, window và sắp xếp |
| Q7 | Thống kê doanh thu/đơn theo **loại hình đại lý** | FactResellerSales JOIN DimReseller, nhóm theo `BusinessType` | Thấp–TB | GROUP BY, SUM, COUNT DISTINCT; thay thế phân tích thanh toán |
| Q8 | Top 10 khách hàng Internet theo chi tiêu | FactInternetSales JOIN DimCustomer bằng CustomerKey | Cao | JOIN, aggregation, ORDER BY, LIMIT |

AdventureWorks không có bảng phương thức thanh toán cho từng giao dịch tương đương yêu cầu gốc. Không suy diễn `DimReseller.MinPaymentType` thành phương thức thanh toán thực tế. Reseller là khách hàng/đại lý mua từ AdventureWorks, không phải seller marketplace. Q4/Q6 chỉ phản ánh địa chỉ đại lý; Q8 chỉ gồm khách hàng Internet, không gộp CustomerKey với ResellerKey.

`DimProduct` có lịch sử sản phẩm: Q1 trả về từng ProductKey; không tự khử trùng theo tên hoặc ProductAlternateKey. Giá NULL không đạt điều kiện ≥100. Mọi số tiền dùng int64 theo đơn vị 1/10.000 USD hoặc DECIMAL chính xác; ngưỡng Q1 tương ứng 1.000.000 đơn vị. Doanh thu là SalesAmount đã trừ chiết khấu.

## 3. Chuẩn bị dữ liệu cho bộ Q1–Q8

1. Lập manifest các CSV đầu vào với hash, schema và số dòng. Đọc chín bảng từ CSV hiện có qua hàm làm sạch dùng chung; giữ bảng trong bộ nhớ, không ghi Parquet hoặc thư mục `tables/`.
2. Giữ riêng các bảng chiều và fact. Ép kiểu một lần trước phép đo; ghi rõ cột được đọc, kiểu số tiền, khóa và số dòng bị từ chối. Không sửa nguồn hoặc làm thay đổi mart dashboard.
3. Kiểm tra khóa chiều duy nhất và quan hệ nhiều-một; thiếu khóa bắt buộc phải báo lỗi. Dùng LEFT JOIN cho chiều tùy chọn để giữ doanh thu không phân loại; thống kê nhóm NULL. pandas merge có thể ghép NULL với NULL khác SQL: khóa chiều phải không NULL, còn khóa ngoại NULL chỉ tạo dòng không ghép.
4. Cả pandas và Spark dùng **cùng dữ liệu đã kiểm tra**. Chuyển bảng pandas sang Spark qua Arrow và đăng ký temporary view một lần trước phép đo; giữ chính xác int64, NULL và schema bảng rỗng. Cả hai engine tự JOIN các bảng nguồn riêng.
5. Với mỗi truy vấn, thống nhất tập dòng trước so sánh. Q2/Q4/Q6/Q7 dùng Reseller; Q8 dùng Internet; Q3/Q5 dùng cả hai kênh. Không so sánh thời gian giữa các tập dòng khác nhau rồi quy toàn bộ chênh lệch cho độ phức tạp SQL.

## 4. Quy tắc kết quả và ca kiểm thử

| Ca | Áp dụng | Kết quả mong đợi |
|---|---|---|
| Fixture tính tay nhiều nhóm | Mọi Q | Khớp từng dòng/khóa/chỉ số, không chỉ tổng chung |
| Giá 99,9999; 100; 100,0001; NULL | Q1 | Chỉ giữ hai giá ≥100; không dùng epsilon float |
| Nhiều dòng cùng đơn | Q2/Q7/Q8 | SUM cộng đủ dòng; COUNT DISTINCT đếm mỗi đơn một lần trong nhóm |
| Khóa chiều trùng hoặc FK bắt buộc thiếu | Q2–Q8 có JOIN | Dừng kiểm tra đầu vào; không nhân đôi hoặc âm thầm mất doanh thu |
| Khóa nhóm/chiều tùy chọn NULL | Q3/Q4/Q7 | pandas giữ nhóm NULL tương đương SQL; không bỏ nhóm để làm khớp |
| Giao dịch lỗ, tổng 0, số tiền >2^53 | Các phép SUM | Giữ lợi nhuận âm và độ chính xác số nguyên; tổng còn trong int64 |
| Tháng 12 → tháng 1; cùng tháng khác năm | Q5 | Nhóm theo năm-tháng; không dùng riêng MONTH(date) |
| Đồng hạng, nhóm có dưới 3 đại lý | Q6 | `ROW_NUMBER() OVER (PARTITION BY CountryRegionCode, StateProvinceCode ORDER BY revenue DESC, ResellerKey ASC)`; tối đa 3 dòng/nhóm |
| Khách hàng bằng tổng chi tiêu | Q8 | ORDER BY tổng DESC, CustomerKey ASC; top 10 ổn định, không chọn tùy ý |
| Bảng rỗng giữ schema | Mọi Q | Kết quả rỗng hợp lệ |
| Cố ý lệch hai nhóm ±1 nhưng giữ tổng | Bộ so sánh | Báo thất bại; không đạt chỉ vì tổng chung bằng nhau |

Q6 dùng ROW_NUMBER để giữ tối đa ba kết quả, không dùng DENSE_RANK rồi vô tình trả hơn ba. Q8 chỉ công bố mã khách hàng và chỉ số cần thiết, không cần đưa email/địa chỉ vào benchmark.

## 5. Thiết kế đo thời gian

### Phép đo chính: truy vấn trong bộ nhớ

- Cùng máy, nguồn điện và trạng thái tải nền; không chạy test hoặc tương tác dashboard song song. Không có cache/persist ứng dụng; cache OS không bị xóa.
- Mốc thời gian: `time.perf_counter()` ngay trước chiếu cột pandas hoặc gọi `spark.sql` trên temporary view; dừng sau JOIN/filter/group/window/sort và materialize đầy đủ kết quả về pandas. Spark phải có action (`toPandas`); chỉ tạo DataFrame hoặc chỉ `count()` không thay cho công việc trả kết quả đầy đủ.
- Không tính tải CSV, chuẩn hóa, nạp bảng Spark, tạo hash, đối chiếu, ghi CSV vào thời gian truy vấn. Ghi thời gian chuẩn bị dữ liệu, khởi động Spark và `spark_table_setup_seconds` riêng.
- Việc đọc file để tính hash trước benchmark có thể làm nóng cache OS; không coi lượt đầu là phép đo đọc đĩa lạnh.
- Tối thiểu 5 lượt/engine/Q. Luân phiên engine đi trước; với bộ tám Q, đảo/xáo thứ tự Q bằng seed cố định giữa vòng, lưu thứ tự. Giữ và ghi nhãn lượt đầu; không gọi đó là cold disk vì cache OS không kiểm soát.
- Báo cáo toàn bộ mẫu và median/min/max. Tỷ số `median(Spark) / median(pandas)` >1 nghĩa là pandas nhanh hơn. Không khẳng định Spark phải thắng và không gán độ phức tạp lý thuyết từ một thời gian đo.

### Chẩn đoán JOIN/window

- Lưu `EXPLAIN FORMATTED` trước và executed plan sau action: filter pushdown, sort, exchange/shuffle, broadcast/sort-merge join và window. Ghi AQE, autoBroadcastJoinThreshold, shuffle partitions, timezone, Arrow, ANSI và bộ nhớ driver/executor.
- Đo chính dùng cấu hình mặc định đã ghi nhận; không tự broadcast chỉ cho Spark rồi coi là cùng kịch bản. Nếu thử tối ưu, tạo experiment riêng và vẫn kiểm tra độ khớp.
- Q1 trả nhiều dòng hơn Q6/Q8 nên chi phí collect khác nhau; ghi input/output rows và bytes. Chỉ so engine trong cùng Q/tập dữ liệu. Kích thước đầu ra là một phần của kết quả đo.
- Run mới đo truy vấn trong bộ nhớ; không trộn hoặc so trực tiếp với số đo đọc Parquet của run cũ.
- Tải 5× chỉ là bản sao dẫn xuất có nhãn, mã đơn/người mua tách theo replica. Không đổi raw, không coi giao dịch nhân bản là mẫu kinh doanh mới, không dùng kết quả local để kết luận tốc độ cụm.

## 6. Cấu hình và minh chứng phải lưu

SQL thực thi nằm trong `environment.json` cùng hash; không sao chép sang thư mục `queries/`. `source_csv_bytes` là kích thước CSV gốc, không phải số byte đọc trong khoảng đo. Thư mục con của run mới chỉ có `results/` và `plans/`.

- CPU model, lõi vật lý/logic, RAM vật lý, hệ điều hành, kiến trúc; mô tả ổ lưu dữ liệu. Nếu không thu thập được thông tin nào phải ghi rõ.
- Python, pandas, PyArrow, Java, Spark; master/local threads, cấu hình thực tế và thời gian khởi động JVM.
- Hash/schema/rows/bytes của mỗi đầu vào, hash SQL và mã benchmark, thời điểm UTC, số vòng, thứ tự thực thi, chính sách cache và mốc đo.
- CSV từng lượt: experiment, Q, engine, vòng, thứ tự, thời gian, số dòng kết quả, exact match. CSV tóm tắt: median/min/max, độ khớp, số lượt hoàn thành; kết quả pandas/Spark đã sắp cùng thứ tự để tái kiểm tra.
- Chỉ nghiệm thu lượt đo có trạng thái `passed`, đủ số mẫu và 100% khớp theo từng nhóm/chỉ số. Lỗi khởi động hoặc kết quả sai phải giữ log, trạng thái `failed` và kết quả thực tế; không thay bằng 0 giây hoặc số ước lượng.

## 7. Các bước triển khai Q1–Q8

| Bước | Phụ thuộc | File/khu vực dự kiến | Điều kiện hoàn tất |
|---|---|---|---|
| A. Manifest và các bảng benchmark riêng | Không | src/benchmark/prepare.py | Raw hash giữ nguyên; khóa/schema/kiểu tiền hợp lệ |
| B. Q1, Q2, Q7 và baseline pandas | A | src/benchmark; tests/benchmark | Fixture giá, đơn nhiều dòng, NULL đạt |
| C. Q3, Q4, Q5 | A, B | src/benchmark; tests/benchmark | JOIN nhiều-một; tổng không mất/nhân đôi; năm-tháng đúng |
| D. Q6, Q8 | C | src/benchmark; tests/benchmark | Ties/top-N ổn định, bảng rỗng đạt |
| E. Chạy toàn bộ và báo cáo | B–D | output/sql_benchmark; docs | 8 × 2 × 5 = 80 mẫu, 100% khớp, plans/config/hash đầy đủ |

Đã hoàn tất A–E ngày 17/11/2026. Mã và SQL nằm trong `src/benchmark/`, kiểm thử trong `tests/benchmark/`. Chạy `python -m src.benchmark.runner --repeats 5` hoặc `run.cmd sql-benchmark`; kết quả được tạo mới theo run, không ghi vào dataset gốc. Các truy vấn lấy execution plan chạy sau toàn bộ lượt đo.

### Kết quả Q1–Q8 lịch sử (Parquet, trước thay đổi trong bộ nhớ)

Run **20261117T125908401490Z**: đủ **80/80 mẫu khớp tuyệt đối**, gồm 5 lượt × 2 engine × 8 truy vấn. Hai fact có 60.398 và 60.855 dòng, dùng cùng chín file Parquet cho cả hai engine. Toàn bộ 30 file nguồn giữ nguyên SHA-256; Parquet và SQL không đổi trong phép đo. Toàn bộ **57/57 kiểm thử đạt**.

[Các lượt Q1–Q8 được lưu trong repository](../output/sql_benchmark/README.md).

Trên máy local này, Spark nhanh hơn ở Q5 (median 1,003958 s so với pandas 1,182847 s); pandas nhanh hơn ở bảy Q còn lại. Đây là kết quả lịch sử của triển khai Parquet đã lưu, không phải số đo cho triển khai trong bộ nhớ hiện tại hoặc kết luận cho mọi SQL/dataset. Bộ mart bên dưới là lần đo độc lập trước đó.

## 8. Baseline đã đo ngày 17/11/2026

Mart: **121.253 dòng**, **2.433.440 byte**; SHA-256 trước/sau đều là `7bf741e0e0bcf55a05d01c274d42f4025711577143b5bf66891f9087a4cc287c`. Run dữ liệu: `20261117T024308566452Z`. Thời điểm bắt đầu đo: `2026-11-17T03:11:03.531419+00:00`.

Máy: **Intel Core i5-12450H, 8 lõi vật lý / 12 luồng**, RAM vật lý hệ thống nhận diện **16.852.574.208 byte (~15,70 GiB)**; Windows 11, AMD64. Đây không phải RAM còn trống hoặc peak memory của truy vấn. Lưu trữ local trên ổ E:, chưa đo loại ổ/throughput.

Python 3.12.10; pandas 2.2.3; PyArrow 21.0.0; Spark 4.0.1; Java 17.0.12. Spark `local[2]`, 4 shuffle partitions, timezone UTC, AQE bật, Arrow tắt, ANSI bật. Driver/executor memory không override mặc định. Khởi động Spark/JVM: **6,1368 giây**, tách khỏi bảng dưới.

| Truy vấn mart | Nhóm kết quả | pandas median (s) | Spark median (s) | Spark / pandas | Độ khớp |
|---|---:|---:|---:|---:|---|
| Tháng/kênh | 71 | 0,1093 | 0,6398 | 5,86× | 100% nhóm và chỉ số |
| Vùng/kênh | 20 | 0,1167 | 0,5198 | 4,46× | 100% nhóm và chỉ số |
| Danh mục/kênh | 7 | 0,1173 | 0,5045 | 4,30× | 100% nhóm và chỉ số |

Mỗi ô median lấy từ 5 lượt, tổng **30 mẫu đo**, tất cả khớp. Spark lượt đầu của truy vấn tháng mất 5,6347 giây; lượt này vẫn nằm trong CSV và min/max, không bị bỏ. Các số liệu chỉ cho thấy pandas nhanh hơn trên workload/local dataset này; không chứng minh tốc độ JOIN/window của Q1–Q8 hoặc hiệu quả trên cụm phân tán. Phép đo không kiểm soát hoàn toàn tải nền Windows, cache OS, disk I/O hoặc peak memory.

Minh chứng [lượt mart hiện hành](../output/evidence/) gồm từng lượt đo, trung vị, cấu hình, kế hoạch SQL và đầu ra của từng công cụ. [Số đo trong báo cáo CO4033](reports/benchmark-20261118/) được lưu riêng theo ngày.

### Lệnh tái lập trên Windows

Chạy từ thư mục gốc, sau khi cài requirements và tạo mart. Dùng JDK 17 hiện có trên máy:

```powershell
$env:JAVA_HOME = 'C:\Program Files\Java\jdk-17'
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m pytest tests/benchmark/test_mart.py -q
.\.venv\Scripts\python.exe -m src.benchmark.mart --repeats 5
.\.venv\Scripts\python.exe -m src.utils.delivery --verify
```

Lệnh cuối lưu log kiểm thử và xuất evidence từ run hiện hành. Không chạy benchmark và test đồng thời. Không cần chạy `instawdbdw.sql` trong SQL Server; chỉ đọc schema của nó.
