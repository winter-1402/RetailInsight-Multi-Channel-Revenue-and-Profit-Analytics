"""Tạo báo cáo PDF từ dữ liệu và kết quả đo hiện hành; không điền số liệu giả."""
from html import escape
import json
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, String, Line, PolyLine
from reportlab.graphics import renderPDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

from src.ingestion.source import BASE
from src.pipeline.retail import current_run
from src.pipeline.analytics import kpis, monthly_sales, monthly_view, growth_metric, number_vn
from .config import ROOT, SCALE

NAVY = colors.HexColor('#143957')
TEAL = colors.HexColor('#008577')
PALE = colors.HexColor('#edf3f8')
PROJECT_REPO = 'https://github.com/winter-1402/RetailInsight-Multi-Channel-Revenue-and-Profit-Analytics'


def register_fonts():
    candidates = [
        (Path('C:/Windows/Fonts/arial.ttf'), Path('C:/Windows/Fonts/arialbd.ttf')),
        (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')),
        (ROOT / 'assets/fonts/arial.ttf', ROOT / 'assets/fonts/arialbd.ttf')]
    for normal, bold in candidates:
        if normal.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont('Report', str(normal)))
            pdfmetrics.registerFont(TTFont('ReportBold', str(bold)))
            pdfmetrics.registerFontFamily('Report', normal='Report', bold='ReportBold', italic='Report', boldItalic='ReportBold')
            return
    raise FileNotFoundError('Cần Arial trên Windows hoặc fonts-dejavu-core trên Linux để xuất PDF tiếng Việt.')


def results_drawing(fact, width=480, height=285):
    drawing = Drawing(width, height)
    drawing.add(Rect(0, 0, width, height, fillColor=colors.white, strokeColor=colors.HexColor('#dce6ee'), rx=8, ry=8))
    drawing.add(String(18, height-27, 'DOANH THU VÀ LỢI NHUẬN THEO KÊNH', fontName='ReportBold', fontSize=11, fillColor=NAVY))
    channel = fact.groupby('channel')[['revenue_units', 'profit_units']].sum() / SCALE
    maximum = channel.revenue_units.max()
    for i, (name, row) in enumerate(channel.iterrows()):
        y = height - 67 - i * 95
        drawing.add(String(18, y, name, fontName='ReportBold', fontSize=11, fillColor=NAVY))
        bar = 280 * row.revenue_units / maximum
        profit_bar = 280 * row.profit_units / maximum
        drawing.add(Rect(18, y-25, bar, 12, fillColor=NAVY, strokeColor=None))
        drawing.add(Rect(18, y-43, profit_bar, 12, fillColor=TEAL, strokeColor=None))
        drawing.add(String(318, y-23, number_vn(row.revenue_units) + ' USD', fontName='Report', fontSize=9, fillColor=NAVY))
        drawing.add(String(318, y-41, number_vn(row.profit_units) + ' USD', fontName='Report', fontSize=9, fillColor=TEAL))
    drawing.add(Rect(18, 20, 9, 9, fillColor=NAVY, strokeColor=None))
    drawing.add(String(32, 20, 'Doanh thu thuần', fontName='Report', fontSize=8, fillColor=NAVY))
    drawing.add(Rect(148, 20, 9, 9, fillColor=TEAL, strokeColor=None))
    drawing.add(String(162, 20, 'Lợi nhuận gộp', fontName='Report', fontSize=8, fillColor=NAVY))
    return drawing


def render_figures():
    import fitz
    register_fonts()
    fact = pd.read_parquet(current_run() / 'gold/fact_sales.parquet')
    destination = ROOT / 'docs/figures'
    destination.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / '.cache/figures'
    scratch.mkdir(parents=True, exist_ok=True)
    pdf = scratch / 'channel_results.pdf'
    renderPDF.drawToFile(results_drawing(fact), str(pdf))
    with fitz.open(pdf) as document:
        document[0].get_pixmap(matrix=fitz.Matrix(2, 2)).save(destination / 'channel_results.png')
    return destination


def benchmark_table(summary):
    labels = {'pandas': 'pandas', 'duckdb': 'DuckDB', 'spark_sql': 'Spark SQL'}
    medians = summary.pivot(index='query', columns='engine', values='median_seconds')
    matched = summary.groupby('query')['exact_match'].all()
    engines = [engine for engine in labels if engine in medians]
    return [['Truy vấn', *(f'{labels[engine]} (s)' for engine in engines), 'Khớp']] + [
        [query, *(f'{medians.loc[query, engine]:.4f}' for engine in engines),
         'Chính xác' if matched[query] else 'Sai lệch']
        for query in ['monthly', 'region', 'category', 'customer_segments'] if query in medians.index]


def completed_loads(run):
    for path in sorted(run.glob('load_scale_*/benchmark_summary.csv')):
        summary = pd.read_csv(path)
        if not summary.empty and ('complete' not in summary or summary['complete'].all()):
            yield path, summary


def build_markdown_report(output=ROOT / 'docs/BAO_CAO.md'):
    run = current_run()
    fact = pd.read_parquet(run / 'gold/fact_sales.parquet')
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    environment = json.loads((run / 'benchmark_environment.json').read_text(encoding='utf-8'))
    if environment.get('status', 'passed') != 'passed':
        raise ValueError('Benchmark chưa hoàn tất hoặc không khớp; không xuất báo cáo thành công.')
    quality = pd.read_csv(run / 'quality/summary.csv')
    summary = pd.read_csv(run / 'benchmark_summary.csv')
    total = kpis(fact)
    growth = growth_metric(monthly_view(fact, fact.order_date.min(), fact.order_date.max(), fact))
    channel = fact.groupby('channel')[['revenue_units', 'cost_units', 'profit_units']].sum()
    category = fact.groupby('category')[['revenue_units', 'profit_units']].sum()
    lines = [
        '# Phân tích doanh thu và lợi nhuận bán lẻ đa kênh', '',
        'Báo cáo kỹ thuật RetailInsight. Nguồn Microsoft AdventureWorksDW, dữ liệu doanh nghiệp **giả lập**, giấy phép MIT.', '',
        '## 1 Bài toán và phạm vi', '',
        'Người dùng cuối là quản lý bán hàng và tài chính. Hai câu hỏi: kênh doanh thu cao có đồng thời tạo hiệu quả giá vốn cao không; danh mục/vùng nào đóng góp lợi nhuận gộp đáng ưu tiên kiểm tra?', '',
        f'Phạm vi: {len(fact):,} dòng bán hàng, {total["orders"]:,} đơn, {manifest["date_min"][:10]} đến {manifest["date_max"][:10]}. '
        'Internet kết thúc ngày 28/01/2014; Reseller kết thúc ngày 29/11/2013. Không coi khác biệt thời gian ghi nhận là biến động nhu cầu.', '',
        '## 2 Dữ liệu và quản lý chất lượng', '',
        f'Commit nguồn: `{manifest["commit"]}`. [Nguồn và link tải](DATA_SOURCES.md). CSV UTF-8, phân cách `|`, không có header; đọc tên cột từ DDL chính thức, không thực thi DDL.', '',
        '| Bảng | Đầu vào | Hợp lệ | Trùng đã loại | Cách ly |', '|---|---:|---:|---:|---:|']
    for row in quality.itertuples():
        lines.append(f'| {row.table} | {row.rows_before:,} | {row.rows_after:,} | {row.duplicates_removed} | {row.rows_rejected} |')
    lines += ['', 'Giữ nguyên nguồn; loại trùng hoàn toàn; chuẩn hóa trường dùng trong phân tích; cách ly dòng sai ngày/tiền/số lượng. '
        'Dừng khi khóa chính xung đột hoặc khóa ngoại thiếu. Không loại các giao dịch có giá vốn lớn hơn doanh thu. '
        'Các ô thiếu ở trường mô tả/ảnh tùy chọn được giữ, không tự điền thành số tiền.', '',
        'Mỗi file có URL, SHA-256, số byte và schema trong manifest; quality JSON lưu số ô thiếu trước–sau theo cột. '
        'DiscountAmount là FLOAT, cho phép sai số đối soát 0,0001 USD/dòng; SalesAmount và TotalProductCost được giữ chính xác với 4 chữ số thập phân.', '',
        '## 3 Pipeline và mô hình dữ liệu', '',
        'Nguồn Microsoft → Python kiểm tra/làm sạch → Parquet Silver → mart một dòng mặt hàng → đối chiếu công cụ → dashboard và quyết định. '
        'Dashboard tính lại từ cùng mart khi lọc, trang kiểm chứng đọc đầu ra Spark và benchmark toàn run.', '',
        'Khóa dòng: kênh + SalesOrderNumber + SalesOrderLineNumber. Khóa đơn thêm tiền tố kênh. '
        'Chiều sản phẩm → nhóm → danh mục, vùng, đại lý DimReseller và tiền tệ được ghép nhiều-một; có kiểm tra không nhân đôi doanh thu. '
        'DimReseller có 701 đại lý, 635 có giao dịch; Internet không có mã cửa hàng vật lý. '
        'Mỗi run có thư mục riêng; chỉ chuyển current.txt khi nạp thành công.', '',
        '## 4 KPI và kết quả đo', '',
        '| KPI | Công thức | Kết quả toàn kỳ |', '|---|---|---:|',
        f'| Doanh thu thuần | SUM(SalesAmount) | {number_vn(total["revenue_units"]/SCALE)} USD |',
        f'| Lợi nhuận gộp | SUM(SalesAmount − TotalProductCost) | {number_vn(total["profit_units"]/SCALE)} USD |',
        f'| Biên gộp | Tổng lợi nhuận / tổng doanh thu × 100 | {number_vn(total["margin_pct"],4)}% |',
        f'| Tăng trưởng {growth["period"]} | (Doanh thu tháng / tháng lịch trước − 1) × 100 | +{number_vn(growth["growth_pct"],4)}% |', '',
        'SalesAmount đã trừ chiết khấu nên không trừ thêm DiscountAmount. Không cộng TaxAmt/Freight vào doanh thu. '
        'Biên dùng tỷ lệ của các tổng, không lấy trung bình tỷ lệ từng dòng. Mẫu số bằng 0 hoặc thiếu kỳ trước: không xác định.', '',
        'KPI tăng trưởng chọn tháng đủ phạm vi nguồn gần nhất và yêu cầu tháng trước cũng đủ phạm vi. '
        'Cờ này chỉ xét biên thời gian; không bảo đảm nguồn không thiếu giao dịch. Lợi nhuận gộp chưa trừ vận hành, marketing, thuế thu nhập và hoàn trả chưa có trong nguồn.', '',
        '| Kênh | Doanh thu USD | Giá vốn USD | Lợi nhuận gộp USD | Biên % |', '|---|---:|---:|---:|---:|']
    for name, row in channel.iterrows():
        lines.append(f'| {name} | {number_vn(row.revenue_units/SCALE)} | {number_vn(row.cost_units/SCALE)} | '
            f'{number_vn(row.profit_units/SCALE)} | {number_vn(row.profit_units/row.revenue_units*100)} |')
    lines += ['', '![Doanh thu và lợi nhuận theo kênh](figures/channel_results.png)', '',
        '*Biểu đồ tổng hợp sinh từ mart, không phải ảnh chụp giao diện.*', '',
        '## 5 Baseline và thực nghiệm', '',
        'Các truy vấn tổng hợp theo tháng/kênh, vùng/kênh, danh mục/kênh và phân khúc người mua. '
        'Các công cụ đọc cùng Parquet và dùng cùng phép tính. Kết quả được đối chiếu từng nhóm với pandas.', '',
        f'Mỗi công cụ chạy {environment["repeats"]} lần/truy vấn, thứ tự luân phiên; không loại lượt đầu; không dùng persist/cache Spark; không xóa cache OS. '
        f'JVM khởi động riêng {environment["spark_startup_seconds"]:.2f} giây. Mốc đo gồm đọc, groupby/distinct, sort và collect, không bao gồm tải nguồn hoặc tạo mart.', '',
        f'Cấu hình: {environment["os"]}; Python {environment["python"]}; Spark {environment["spark"]}; '
        f'{environment["logical_cpus"]} CPU logic; local[2], 4 shuffle partitions; JDK trong metadata.', '']
    rows = benchmark_table(summary)
    rows.insert(1, ['---', *(['---:'] * (len(rows[0]) - 2)), '---'])
    lines.extend('| ' + ' | '.join(row) + ' |' for row in rows)
    for path, _ in completed_loads(run):
        provenance = json.loads((path.parent / 'synthetic_provenance.json').read_text())
        lines += ['', f'Thử tải {provenance["replication_factor"]}×: {provenance["synthetic_rows"]:,} dòng nhân bản, mã đơn/người mua có hậu tố. '
            'Đây là bản sao đo tải, không phải giao dịch kinh doanh mới. Bảng từng lần đo nằm trong evidence.']
    lines += ['', 'Thời gian trung vị phụ thuộc truy vấn và cấu hình. Chi phí lập kế hoạch, shuffle và trả kết quả về Python '
        'ảnh hưởng các số đo Spark trên máy local. Giới hạn và năng lực cụm phân tán cần phép đo riêng.', '',
        '## 6 Nhận xét và quyết định có điều kiện', '',
        f'1. Reseller chiếm {number_vn(channel.loc["Reseller","revenue_units"]/total["revenue_units"]*100)}% doanh thu nhưng biên gộp '
        f'{number_vn(channel.loc["Reseller","profit_units"]/channel.loc["Reseller","revenue_units"]*100)}%. '
        'Rà soát giá vốn và chiết khấu trước khi tăng doanh số bằng giảm giá.',
        f'2. Bikes tạo {number_vn(category.loc["Bikes","profit_units"]/SCALE)} USD lợi nhuận gộp, '
        f'{number_vn(category.loc["Bikes","profit_units"]/total["profit_units"]*100)}% toàn kỳ. '
        'Kiểm tra năng lực cung ứng trước khi ưu tiên danh mục.',
        '3. Southwest có doanh thu cao nhất, 24.184.609,60 USD, biên gộp khoảng 9,74%. '
        'Đánh giá chi phí phục vụ và biên gộp cùng với doanh thu trước khi mở rộng.', '',
        '| Hành động | Chi phí/rủi ro | Điều kiện áp dụng |', '|---|---|---|',
        '| Thử ngân sách nhỏ ở Internet | Chi phí thu hút khách có thể ăn hết biên gộp | Bổ sung marketing/vận hành, đo nhóm thử nghiệm |',
        '| Rà soát discount Reseller | Mất đại lý hoặc doanh số nếu cắt ưu đãi mạnh | Kiểm tra hợp đồng và nhóm sản phẩm lỗ trước |',
        '| Ưu tiên kiểm tra Bikes | Phụ thuộc danh mục và nguy cơ thiếu hàng | Bổ sung tồn kho, lead time và chi phí cung ứng |', '',
        '## 7 Dashboard kiểm thử và tái lập', '',
        'Bốn trang: Tổng quan; Kênh và thị trường; Sản phẩm; Dữ liệu và kiểm chứng. Bộ lọc gọn có Tất cả, '
        'ngày/kỳ chung, kênh/vùng/danh mục/đại lý, tìm sản phẩm liên kết và nút đặt lại. KPI, biểu đồ, bảng và CSV dùng chung scope. '
        'Sản phẩm lỗ vẫn hiển thị; ngày đảo/rỗng có thông báo; bảng xuất dùng USD thay vì đơn vị lưu trữ.', '',
        'Các ca kiểm thử, phương pháp đối chiếu và giới hạn kiểm tra UI: [VALIDATION.md](VALIDATION.md). '
        'Hướng dẫn chạy: [README](../README.md). Demo: [DEMO.md](DEMO.md). Log và dữ liệu mẫu: [output/evidence](../output/evidence).', '',
        f'[Repository dự án]({PROJECT_REPO}). '
        'Trạng thái CI cần kiểm tra trên đúng commit ở GitHub Actions. '
        'Ảnh giao diện thật và xác nhận từng bước: [SCREENSHOT_REVIEW.md](SCREENSHOT_REVIEW.md).', '',
        '## 8 Nguồn và công cụ AI', '',
        '[Microsoft AdventureWorksDW](DATA_SOURCES.md); MIT license được giữ nguyên trong evidence. '
        '[Sử dụng công cụ AI](AI_USAGE.md). Dữ liệu, số đo và hình minh họa có nguồn truy vết. '
        'Kết quả cần được kiểm chứng lại trên môi trường triển khai trước khi sử dụng để ra quyết định.', '']
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines), encoding='utf-8')
    return output


def build_report(output=ROOT / 'output' / 'Bao_cao_pipeline_dashboard.pdf'):
    run = current_run()
    fact = pd.read_parquet(run / 'gold' / 'fact_sales.parquet')
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    environment = json.loads((run / 'benchmark_environment.json').read_text(encoding='utf-8'))
    if environment.get('status', 'passed') != 'passed':
        raise ValueError('Benchmark chưa hoàn tất hoặc không khớp; không xuất báo cáo thành công.')
    quality = pd.read_csv(run / 'quality' / 'summary.csv')
    benchmark = pd.read_csv(run / 'benchmark_summary.csv')
    register_fonts()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('BodyVN', fontName='Report', fontSize=10, leading=15, spaceAfter=8))
    styles.add(ParagraphStyle('TitleVN', fontName='ReportBold', fontSize=23, leading=30, textColor=NAVY, spaceAfter=16))
    styles.add(ParagraphStyle('HeadingVN', fontName='ReportBold', fontSize=15, leading=20, textColor=NAVY, spaceAfter=12))
    styles.add(ParagraphStyle('SmallVN', fontName='Report', fontSize=8, leading=12, spaceAfter=6))
    styles.add(ParagraphStyle('CellVN', fontName='Report', fontSize=8, leading=11))
    story = []

    def p(text, style='BodyVN'):
        story.append(Paragraph(text, styles[style]))

    def heading(text):
        p(text, 'HeadingVN')

    def table(rows, widths=None):
        content = [[Paragraph(escape(str(c)), styles['CellVN']) for c in row] for row in rows]
        result = Table(content, colWidths=widths, repeatRows=1, hAlign='LEFT')
        result.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), PALE), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LINEBELOW', (0, 0), (-1, 0), .8, NAVY),
            ('LINEBELOW', (0, 1), (-1, -1), .3, colors.HexColor('#dce4eb')),
            ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
        story.extend([result, Spacer(1, 12)])

    total = kpis(fact)
    coverage = fact.groupby('channel').order_date.agg(['min', 'max'])
    growth = growth_metric(monthly_view(fact, fact.order_date.min(), fact.order_date.max(), fact))
    comparison_month, month_kpi = growth['period'], growth['growth_pct']
    p('Phân tích doanh thu và lợi nhuận bán lẻ đa kênh', 'TitleVN')
    p('Báo cáo triển khai pipeline và dashboard', 'HeadingVN')
    p('RetailInsight · Microsoft AdventureWorksDW · Báo cáo kỹ thuật tháng 11/2026', 'SmallVN')
    p('Pipeline đã nạp hai kênh Internet và Reseller từ nguồn Microsoft, tạo data mart, '
      'tổng hợp bằng Spark SQL và dashboard có bộ lọc. Báo cáo dùng kết quả đo thực trên máy triển khai. '
      'AdventureWorks là dữ liệu doanh nghiệp <b>giả lập</b> do Microsoft cung cấp; các con số không mô tả thị trường thực tế.')
    table([['Chỉ tiêu toàn kỳ', 'Giá trị đo'],
        ['Doanh thu sau chiết khấu', f'{total["revenue_units"]/SCALE:,.2f} USD'],
        ['Lợi nhuận gộp', f'{total["profit_units"]/SCALE:,.2f} USD'],
        ['Biên lợi nhuận gộp', f'{total["margin_pct"]:.4f}%'],
        [f'Tăng trưởng tháng {comparison_month} so với tháng trước', f'{month_kpi:+.4f}%'],
        ['Dòng bán hàng / đơn hàng', f'{len(fact):,} / {total["orders"]:,}']], [8.7*cm, 8.3*cm])
    heading('Bài toán và người dùng')
    p('Người dùng cuối là quản lý bán hàng và quản lý tài chính. Hai câu hỏi kiểm chứng: '
      '(1) Kênh nào có doanh thu lớn nhưng hiệu quả giá vốn thấp? '
      '(2) Danh mục và vùng nào đóng góp lợi nhuận gộp cao nhất để ưu tiên kiểm tra năng lực phục vụ?')
    p('Ba KPI bắt buộc: doanh thu thuần, biên lợi nhuận và tăng trưởng theo tháng. '
      'Trong phạm vi này, doanh thu thuần là SalesAmount sau chiết khấu, chưa điều chỉnh cho hoàn trả không có trong nguồn. '
      'Lợi nhuận được xác định là lợi nhuận gộp, chưa phải lợi nhuận ròng.')
    p('Phạm vi thời gian: ' + manifest['date_min'][:10] + ' đến ' + manifest['date_max'][:10] +
      '. Tháng đầu và cuối không đủ kỳ; các so sánh tăng trưởng ở biên phải được đọc thận trọng.')
    p('KPI tăng trưởng dùng cặp tháng lịch nằm trọn trong phạm vi nguồn và khoảng ngày đã chọn. '
      'Đây là kiểm tra biên thời gian, chưa chứng minh nguồn không thiếu giao dịch. Reseller kết thúc ghi nhận sớm hơn Internet; '
      'không diễn giải mức giảm cuối kỳ là thị trường suy giảm.', 'SmallVN')
    story.append(PageBreak())

    heading('Nguồn dữ liệu và chất lượng')
    p('Nguồn chính thức: Microsoft SQL Server Samples / AdventureWorksDW. Giấy phép MIT được lưu cùng dữ liệu tải xuống. '
      'Bộ dữ liệu được ghim commit để chạy lại đúng cùng phiên bản.', 'BodyVN')
    p('Commit: ' + manifest['commit'], 'SmallVN')
    table([['Bảng', 'Trước', 'Sau', 'Trùng', 'Cách ly', 'Thiếu ô %']] + [
        [r.table, f'{r.rows_before:,}', f'{r.rows_after:,}', r.duplicates_removed, r.rows_rejected,
         f'{r.missing_pct_before:.2f}'] for r in quality.itertuples()],
        [6.4*cm, 2*cm, 2*cm, 1.5*cm, 1.6*cm, 1.5*cm])
    p('Không có dòng bị cách ly trong bộ nguồn đã tải. Đây là kết quả kiểm tra, không phải bỏ qua làm sạch. '
      'Các trường ảnh, mô tả sản phẩm, mã theo dõi có thể thiếu; không điền giá vốn hoặc doanh thu từ các trường mô tả.')
    p('Phạm vi giao dịch theo kênh: ' + '; '.join(f'{name}: {row["min"].date()} đến {row["max"].date()}'
        for name,row in coverage.iterrows()) + '. Khác biệt thời gian ghi nhận hạn chế so sánh tổng toàn kỳ giữa hai kênh.', 'SmallVN')
    table([['Nhóm trường', 'Ví dụ', 'Vai trò'],
        ['Khóa giao dịch', 'SalesOrderNumber, SalesOrderLineNumber', 'Một dòng đơn hàng; thêm tiền tố kênh để tránh trùng'],
        ['Thời gian', 'OrderDate, OrderDateKey', 'Phân tích tháng; lưu timestamp microsecond'],
        ['Tiền', 'SalesAmount, TotalProductCost, ExtendedAmount', 'MONEY trong nguồn; lưu số nguyên nhân 10.000'],
        ['Chiết khấu', 'DiscountAmount', 'FLOAT trong nguồn; làm tròn để đối soát, sai số tối đa cho phép 0,0001 USD/dòng'],
        ['Chiều', 'ProductKey, SalesTerritoryKey, CurrencyKey', 'Ghép nhiều-một với chiều sản phẩm, vùng, tiền tệ']],
        [3.4*cm, 6.2*cm, 7.4*cm])
    p('Chất lượng chi tiết theo từng cột, kiểu dữ liệu và số ô thiếu trước–sau nằm trong quality/data_quality.json. '
      'manifest.json lưu URL nguồn, tên file, số byte và SHA-256 cho từng bảng. Dữ liệu nguồn nguyên bản được giữ tại data/raw.')
    p('Giá trị SalesAmount và TotalProductCost sử dụng số tiền cơ sở USD của mô hình AdventureWorks. '
      'CurrencyAlternateKey được giữ để truy vết; pipeline không tự nhân thêm tỷ giá lần nữa.', 'SmallVN')
    story.append(PageBreak())

    heading('Kiến trúc và quy trình xử lý')
    diagram = Drawing(480, 105)
    names = [('Microsoft', 'CSV nguồn'), ('Python', 'Kiểm tra'), ('Parquet', 'Silver và mart'), ('Spark SQL', 'Tổng hợp'), ('Streamlit', 'Bộ lọc và KPI')]
    for i, (top, bottom) in enumerate(names):
        x = i * 97
        diagram.add(Rect(x, 30, 88, 62, fillColor=PALE, strokeColor=NAVY, rx=6, ry=6))
        diagram.add(String(x+44, 67, top, fontName='ReportBold', fontSize=10, textAnchor='middle', fillColor=NAVY))
        diagram.add(String(x+44, 48, bottom, fontName='Report', fontSize=8, textAnchor='middle'))
        if i < 4:
            diagram.add(Line(x+88, 61, x+97, 61, strokeColor=TEAL))
    story.append(diagram)
    p('CSV dùng dấu phân cách |, không có header. Pipeline lấy tên cột từ DDL chính thức đi kèm. '
      'Script chỉ đọc DDL để nhận diện schema; không thực thi lệnh tạo hoặc xóa database trong file SQL.')
    p('Mỗi bảng được chuẩn hóa khoảng trắng, loại trùng hoàn toàn, kiểm tra khóa và chuyển kiểu cần dùng. '
      'Dòng sai ngày, tiền âm/không hợp lệ, số lượng không nguyên dương hoặc đối soát doanh thu lệch quá ngưỡng '
      'được cách ly kèm lý do. Khóa chính xung đột và khóa ngoại không tồn tại làm pipeline dừng.')
    heading('Mô hình phân tích')
    table([['Thành phần', 'Quan hệ'],
        ['FactInternetSales / FactResellerSales', 'UNION ALL sau khi chuẩn hóa cùng schema; kênh xác định từ bảng nguồn'],
        ['DimProduct → Subcategory → Category', 'Ghép nhiều-một theo các khóa kỹ thuật; giữ phiên bản sản phẩm trong nguồn'],
        ['DimSalesTerritory', 'Vùng và quốc gia bán hàng'],
        ['DimReseller', '701 đại lý trong chiều; 635 có giao dịch. Internet không có mã cửa hàng vật lý'],
        ['DimCurrency', 'Mã tiền tệ nguồn để truy vết'],
        ['gold/fact_sales.parquet', 'Grain một dòng đơn hàng; line_id duy nhất gồm kênh + số đơn + số dòng']],
        [7*cm, 10*cm])
    p('Mỗi lượt chạy có thư mục run riêng. Chỉ sau khi nạp và kiểm tra hoàn tất, current.txt mới chuyển sang lượt chạy mới. '
      'Nếu lỗi xảy ra trước khi công bố, dashboard tiếp tục dùng dữ liệu của lượt thành công trước đó. '
      'Không có phép cộng tiền từ bảng thanh toán hoặc bảng có quan hệ một-nhiều.')
    p('Spark SQL đọc mart Parquet để tạo tổng hợp theo tháng, vùng, danh mục và phân khúc người mua. '
      'Dashboard tính lại trên cùng mart khi người dùng lọc, đồng thời hiển thị đầu ra Spark và phép đối chiếu chính xác với baseline pandas.')
    story.append(PageBreak())

    heading('Kết quả phân tích và quyết định')
    channel = fact.groupby('channel')[['revenue_units','profit_units']].sum()
    table([['Kênh', 'Doanh thu USD', 'Lợi nhuận gộp USD', 'Biên %']] + [
        [name, f'{r.revenue_units/SCALE:,.2f}', f'{r.profit_units/SCALE:,.2f}',
         f'{r.profit_units/r.revenue_units*100:.2f}'] for name,r in channel.iterrows()],
        [3*cm, 5*cm, 5.5*cm, 3.5*cm])
    cat = fact.groupby('category')[['revenue_units','profit_units']].sum().sort_values('profit_units', ascending=False)
    table([['Danh mục', 'Doanh thu USD', 'Lợi nhuận gộp USD', 'Biên %']] + [
        [name, f'{r.revenue_units/SCALE:,.2f}', f'{r.profit_units/SCALE:,.2f}',
         f'{r.profit_units/r.revenue_units*100:.2f}'] for name,r in cat.iterrows()],
        [3*cm, 5*cm, 5.5*cm, 3.5*cm])
    internet, reseller = channel.loc['Internet'], channel.loc['Reseller']
    p(f'<b>Nhận xét 1.</b> Reseller chiếm {reseller.revenue_units/total["revenue_units"]:.2%} doanh thu '
      f'nhưng biên gộp chỉ {reseller.profit_units/reseller.revenue_units*100:.2f}%. '
      f'Internet có biên gộp {internet.profit_units/internet.revenue_units*100:.2f}%. '
      'Ưu tiên kiểm tra giá bán, chiết khấu và giá vốn ở Reseller trước khi tăng doanh số bằng giảm giá.')
    p(f'<b>Nhận xét 2.</b> Bikes tạo {cat.loc["Bikes","profit_units"]/SCALE:,.2f} USD lợi nhuận gộp, '
      f'tương đương {cat.loc["Bikes","profit_units"]/total["profit_units"]:.2%} toàn kỳ. '
      'Có thể ưu tiên kiểm tra năng lực đáp ứng danh mục này; không kết luận tồn kho tối ưu khi không có dữ liệu tồn kho.')
    regional = fact.groupby('region')[['revenue_units','profit_units']].sum()
    region_name = regional.revenue_units.idxmax()
    p(f'<b>Nhận xét 3.</b> {escape(region_name)} có doanh thu cao nhất: '
      f'{regional.loc[region_name,"revenue_units"]/SCALE:,.2f} USD, nhưng biên gộp '
      f'{regional.loc[region_name,"profit_units"]/regional.loc[region_name,"revenue_units"]*100:.2f}%. '
      'Quyết định mở rộng cần xem đồng thời doanh thu và chi phí phục vụ vùng.')
    table([['Hành động đề xuất', 'Chi phí và rủi ro', 'Điều kiện kiểm chứng'],
        ['Thử nghiệm ngân sách nhỏ cho Internet', 'Chi phí thu hút khách có thể làm giảm biên gộp cao hiện tại', 'Bổ sung chi phí marketing; đo lợi nhuận sau chi phí trên nhóm thử nghiệm'],
        ['Rà soát chiết khấu Reseller', 'Tăng giá hoặc giảm ưu đãi có thể làm mất đại lý', 'Kiểm tra hợp đồng và nhóm sản phẩm bị lỗ; thử theo nhóm trước'],
        ['Ưu tiên kiểm tra danh mục Bikes', 'Tập trung danh mục làm tăng rủi ro thiếu hàng và phụ thuộc', 'Bổ sung tồn kho và thời gian cung ứng trước khi tăng cam kết']],
        [5*cm, 6*cm, 6*cm])
    story.append(PageBreak())

    heading('Minh họa kết quả và cách đọc dashboard')
    story.append(results_drawing(fact))
    story.append(Spacer(1, 14))
    p('Hình tổng hợp được sinh trực tiếp từ data mart của run hiện hành. Màu xanh đậm là doanh thu '
      'thuần; màu xanh ngọc là lợi nhuận gộp. Đây là biểu đồ dữ liệu, không phải ảnh chụp giao diện.')
    p('Internet có doanh thu nhỏ hơn Reseller nhưng đóng góp lợi nhuận gộp lớn hơn đáng kể. '
      'Đọc đồng thời độ lớn doanh thu, lợi nhuận và biên gộp giúp tránh ưu tiên một kênh chỉ vì doanh số cao.')
    heading('Phạm vi và khả năng tương tác')
    table([['Trang', 'Mục đích và thao tác'],
        ['Tổng quan', 'KPI, xu hướng tháng, cơ cấu kênh, đóng góp danh mục và ba nhận xét theo bộ lọc'],
        ['Kênh và thị trường', 'So sánh kênh, vùng; bảng USD và tải CSV theo phạm vi đang chọn'],
        ['Sản phẩm', 'Xếp hạng lợi nhuận cao/thấp; giữ sản phẩm lỗ; bảng và CSV theo bộ lọc'],
        ['Dữ liệu và kiểm chứng', 'Chất lượng, benchmark và nguồn/công thức; số liệu kiểm chứng luôn được gắn nhãn toàn run']],
        [4.3*cm, 12.7*cm])
    p('Thanh bên dùng lựa chọn “Tất cả” để tránh danh sách thẻ dài; có ngày bắt đầu/kết thúc, '
      'kỳ chung hai kênh, kênh, vùng, danh mục và tìm sản phẩm. Danh sách sản phẩm tuân theo các bộ lọc trước; '
      'sản phẩm không còn phù hợp được đặt lại. Nút đặt lại khôi phục toàn bộ dữ liệu.')
    p('Thay đổi bộ lọc cập nhật đồng thời KPI, biểu đồ, bảng và CSV. Ngày đảo chiều được báo lỗi; '
      'phạm vi không có giao dịch hiển thị hướng dẫn thay vì tính KPI từ một tập dữ liệu khác. '
      'Mọi số tiền hiển thị bằng USD; giá trị lưu bằng đơn vị nguyên chỉ xuất hiện trong minh chứng kỹ thuật.')
    story.append(PageBreak())

    heading('So sánh công cụ trên data mart')
    p('Tổng hợp theo tháng/kênh, vùng/kênh, danh mục/kênh và phân khúc người mua. '
      'Các công cụ dùng cùng tệp Parquet. So sánh giá trị từng nhóm với baseline pandas.')
    rows = benchmark_table(benchmark)
    widths = [4.4*cm, *([9.4*cm / (len(rows[0]) - 2)] * (len(rows[0]) - 2)), 3.2*cm]
    table(rows, widths)
    p(f'Đầu vào gốc: {manifest["fact_rows"]:,} dòng. Mỗi engine chạy {environment["repeats"]} lần/truy vấn, '
      'thứ tự luân phiên; không loại lượt chạy đầu, không dùng persist/cache của Spark, không xóa cache hệ điều hành. '
      f'Khởi động JVM/Spark đo riêng: {environment["spark_startup_seconds"]:.2f} giây. '
      'Mốc đo gồm đọc Parquet, groupby/distinct, sắp xếp và trả kết quả về pandas; không bao gồm tải nguồn hay tạo mart.')
    p(f'Cấu hình: {escape(environment["os"])}; Python {environment["python"]}; Spark {environment["spark"]}; '
      f'{environment["logical_cpus"]} CPU logic; master local[2]; 4 shuffle partitions. '
      'Máy dùng JDK theo JAVA_HOME; thông tin phiên bản chính xác nằm trong benchmark_environment.json.', 'SmallVN')
    loads = list(completed_loads(run))
    if loads:
        load, summary = loads[-1]
        prov = json.loads((load.parent / 'synthetic_provenance.json').read_text())
        p(f'<b>Thử tăng tải.</b> Nhân bản {prov["replication_factor"]} lần tạo {prov["synthetic_rows"]:,} dòng. '
          'Mã đơn và người mua được thêm hậu tố cho từng bản sao. Đây là dữ liệu tải mô phỏng, không phải quan sát mới.')
        loaded = benchmark_table(summary)
        table(loaded, [4.4*cm, *([9.4*cm / (len(loaded[0]) - 2)] * (len(loaded[0]) - 2)), 3.2*cm])
    p('Thời gian trung vị mô tả cấu hình local của từng lượt. Chi phí lập kế hoạch, shuffle và trả kết quả về Python '
      'ảnh hưởng các số đo Spark. Hiệu năng trên cụm phân tán cần phép đo riêng.')
    p(f'Dung lượng nguồn {manifest["raw_bytes"]/1024**2:.2f} MiB; silver {manifest["silver_bytes"]/1024**2:.2f} MiB; '
      f'mart {manifest["fact_bytes"]/1024**2:.2f} MiB. Chênh lệch gồm cả nén và việc mart chỉ chọn các trường phân tích.', 'SmallVN')
    story.append(PageBreak())

    heading('Công thức kiểm thử và bàn giao')
    table([['KPI', 'Công thức và quy tắc'],
        ['Doanh thu thuần', 'SUM(SalesAmount), USD; đã trừ chiết khấu trong nguồn, không cộng TaxAmt/Freight'],
        ['Lợi nhuận gộp', 'SUM(SalesAmount − TotalProductCost), USD; giữ cả giao dịch lỗ'],
        ['Biên lợi nhuận gộp', 'SUM(lợi nhuận gộp) / SUM(doanh thu) × 100; không lấy trung bình tỷ lệ từng dòng'],
        ['Tăng trưởng tháng', '(doanh thu tháng / doanh thu tháng lịch trước − 1) × 100; mẫu số 0 hoặc chưa có kỳ trước: N/A']],
        [4*cm, 13*cm])
    p('Các kiểm thử bao gồm: giữ 4 chữ số thập phân và không trừ chiết khấu hai lần; '
      'cách ly tiền âm và ngày sai; loại trùng hoàn toàn; dừng khi khóa xung đột; '
      'kiểm tra margin có trọng số và giao dịch lỗ; tháng thiếu và mẫu số bằng 0; '
      'khóa đơn trùng giữa hai kênh; khóa ngoại thiếu và chiều trùng; '
      'đối chiếu SQL/pandas trên fixture tính tay; dashboard có bộ lọc rỗng không lỗi.')
    p('Bộ kiểm thử giao diện bổ sung việc đổi danh mục đặt lại sản phẩm, chọn kỳ chung hai kênh, '
      'ngày đảo chiều, tổ hợp không có giao dịch, sản phẩm lỗ, phạm vi hẹp và nút đặt lại. '
      'CSV được kiểm tra công thức USD, tiêu đề công khai và phạm vi lọc. '
      'Đã chụp 9 ảnh giao diện thật trên Chrome và xác nhận KPI, các trang phân tích, lọc Internet và reset. '
      'Chi tiết và giới hạn kiểm tra nằm trong docs/SCREENSHOT_REVIEW.md; ảnh tại docs/screenshots.')
    p('Chạy lại bằng setup.cmd và run.cmd theo README. Mã nguồn, SQL, dữ liệu mẫu đầu ra, log, '
      'manifest, bảng benchmark và kịch bản demo được bàn giao cùng thư mục. '
      'Gói phân phối ZIP loại dữ liệu thô, môi trường ảo, cache và tài liệu ngoài phạm vi dự án. '
      'Mã nguồn và hướng dẫn chạy được lưu trong repository dự án. '
      'Trạng thái CI phải đối chiếu trên đúng commit tại GitHub Actions.')
    heading('Khả năng tái lập và sử dụng công cụ AI')
    p('ChatGPT/Codex hỗ trợ phân tích yêu cầu, thiết kế và rà soát mã, tạo kiểm thử và soạn tài liệu. '
      'Số liệu kinh doanh được tính từ nguồn Microsoft; thời gian thực thi được đo bằng chương trình. '
      'Cần kiểm chứng đầu ra, giả định và giới hạn trên môi trường đích trước khi sử dụng kết quả.')
    heading('Nguồn tham khảo')
    for text, url in [
        ('RetailInsight — repository dự án', PROJECT_REPO),
        ('Microsoft AdventureWorks source', 'https://github.com/microsoft/sql-server-samples/tree/'+manifest['commit']+'/samples/databases/adventure-works'),
        ('Schema và dữ liệu', BASE+'instawdbdw.sql'),
        ('MIT license', f'https://raw.githubusercontent.com/microsoft/sql-server-samples/{manifest["commit"]}/license.txt'),
        ('Microsoft Analysis Services AdventureWorks model', 'https://github.com/microsoft/Analysis-Services/blob/master/AsPartitionProcessing/AsPartitionProcessing.AdventureWorks/Model.bim'),
        ('PySpark 4.0.1 installation', 'https://spark.apache.org/docs/4.0.1/api/python/getting_started/install.html')]:
        p(f'<link href="{escape(url)}" color="#143957">{escape(text)}</link>', 'SmallVN')
    p('Phạm vi chức năng và minh chứng: docs/REQUIREMENTS.md. '
      'Trạng thái kiểm chứng và giới hạn: docs/COMPLIANCE_REVIEW.md.', 'SmallVN')

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    def footer(canvas, doc):
        canvas.setFont('Report', 8)
        canvas.setFillColor(NAVY)
        canvas.drawString(2*cm, 1.1*cm, 'RetailInsight · Pipeline và dashboard · AdventureWorksDW')
        canvas.drawRightString(A4[0]-2*cm, 1.1*cm, str(doc.page))
    SimpleDocTemplate(str(output), pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
        topMargin=1.8*cm, bottomMargin=1.8*cm, title='Pipeline và dashboard doanh thu lợi nhuận đa kênh',
        author='RetailInsight Contributors').build(story, onFirstPage=footer, onLaterPages=footer)
    print(f'Created {output}', flush=True)
    return output


if __name__ == '__main__':
    build_report()
    render_figures()
    build_markdown_report()
