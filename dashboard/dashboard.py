"""Dashboard điều hành; mọi biểu đồ kinh doanh dùng chung phạm vi bộ lọc."""
from html import escape
import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.pipeline.analytics import (ALL, CATEGORY_LABELS, CHANNEL_LABELS, compact_money,
    filter_sales, group_metrics, growth_metric, monthly_view, number_vn, public_table, csv_bytes)
from src.pipeline.retail import current_run
from src.pipeline.analytics import kpis
from src.utils.config import ROOT, SCALE

NAVY, TEAL, AMBER, RED = '#183f63', '#0f8b80', '#d49b38', '#c15155'
CHANNEL_COLORS = {'Internet': TEAL, 'Reseller': NAVY}

st.set_page_config(page_title='RetailInsight · Retail BI', page_icon='📊', layout='wide')
st.markdown('<style>' + (ROOT / 'dashboard/assets/dashboard.css').read_text(encoding='utf-8') + '</style>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_fact(path):
    return pd.read_parquet(path)


try:
    run = current_run()
    fact = load_fact(str(run / 'gold' / 'fact_sales.parquet'))
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
except FileNotFoundError:
    st.title('AdventureWorks · Retail BI')
    st.info('Chưa có dữ liệu phân tích. Hãy chạy lệnh nạp dữ liệu trong README rồi mở lại trang.')
    st.code('python -m src.pipeline.retail --download')
    st.stop()

source_start, source_end = fact.order_date.min().date(), fact.order_date.max().date()
coverage = fact.groupby('channel').order_date.agg(['min', 'max'])
common_start = (coverage['min'].max().to_period('M') + 1).start_time.date()
common_end = (coverage['max'].min().to_period('M') - 1).end_time.date()


def reset_filters():
    st.session_state.update(period='Toàn bộ dữ liệu', date_start=source_start, date_end=source_end,
        channel=ALL, region=ALL, category=ALL, product=ALL, store=ALL)


def apply_period():
    if st.session_state.period == 'Kỳ chung hai kênh':
        st.session_state.update(date_start=common_start, date_end=common_end)
    elif st.session_state.period == 'Toàn bộ dữ liệu':
        st.session_state.update(date_start=source_start, date_end=source_end)


def custom_dates():
    st.session_state.period = 'Tùy chọn'


st.session_state.setdefault('date_start', source_start)
st.session_state.setdefault('date_end', source_end)

with st.sidebar:
    st.markdown('<div class="eyebrow">RETAILINSIGHT / BI</div>', unsafe_allow_html=True)
    st.header('Phạm vi phân tích')
    st.caption('Chọn một phạm vi. Tất cả biểu đồ và chỉ số kinh doanh sẽ cập nhật cùng nhau.')
    st.selectbox('Giai đoạn', ['Toàn bộ dữ liệu', 'Kỳ chung hai kênh', 'Tùy chọn'],
        key='period', on_change=apply_period,
        help='Kỳ chung chỉ dùng các tháng nằm trọn trong phạm vi ghi nhận của cả hai kênh.')
    start = st.date_input('Từ ngày', value=None, min_value=source_start, max_value=source_end,
        format='DD/MM/YYYY', key='date_start', on_change=custom_dates)
    end = st.date_input('Đến ngày', value=None, min_value=source_start, max_value=source_end,
        format='DD/MM/YYYY', key='date_end', on_change=custom_dates)
    if start is None or end is None:
        st.warning('Chọn đủ ngày bắt đầu và ngày kết thúc để tiếp tục phân tích.')
        st.stop()
    channel = st.selectbox('Kênh bán', [ALL] + sorted(fact.channel.unique()), key='channel',
        format_func=lambda v: 'Tất cả kênh bán' if v == ALL else CHANNEL_LABELS.get(v, v))
    region = st.selectbox('Vùng bán hàng', [ALL] + sorted(fact.region.unique()), key='region',
        format_func=lambda v: 'Tất cả vùng' if v == ALL else v)
    category = st.selectbox('Danh mục', [ALL] + sorted(fact.category.unique()), key='category',
        format_func=lambda v: 'Tất cả danh mục' if v == ALL else CATEGORY_LABELS.get(v, v))
    choices = filter_sales(fact, start, end, channel, region, category) if start <= end else fact.iloc[:0]
    store_options = [ALL] + sorted(choices['store'].dropna().unique())
    if st.session_state.get('store', ALL) not in store_options:
        st.session_state.store = ALL
    with st.expander('Đại lý / cửa hàng', expanded=st.session_state.get('store', ALL) != ALL):
        store = st.selectbox('Đại lý / cửa hàng', store_options, key='store',
            format_func=lambda v: 'Tất cả đại lý / cửa hàng' if v == ALL else v,
            help='Đại lý dùng tên và mã DimReseller. Nguồn Internet không có mã cửa hàng vật lý.')
    choices = choices if store == ALL else choices.loc[choices.store.eq(store)]
    product_options = [ALL] + sorted(choices['product'].dropna().unique())
    if st.session_state.get('product', ALL) not in product_options:
        st.session_state.product = ALL
    with st.expander('Lọc theo sản phẩm', expanded=st.session_state.get('product', ALL) != ALL):
        product = st.selectbox('Sản phẩm', product_options, key='product',
            disabled=len(product_options) == 1,
            format_func=lambda v: 'Tất cả sản phẩm' if v == ALL else v,
            help='Có thể gõ tên để tìm. Danh sách tuân theo ngày, kênh, vùng và danh mục đã chọn.')
    st.button('Đặt lại bộ lọc', key='reset_filters', on_click=reset_filters, width='stretch')
    st.divider()
    st.caption('Nguồn Microsoft · Dữ liệu doanh nghiệp giả lập · Đơn vị báo cáo USD')
    st.link_button('Xem nguồn dữ liệu',
        'https://github.com/microsoft/sql-server-samples/tree/b47eadc85277f72843647223cde53aa1b85ffcb8/samples/databases/adventure-works/data-warehouse-install-script',
        width='stretch')

st.markdown('<div class="eyebrow">RETAIL PERFORMANCE / ANALYTICS</div>', unsafe_allow_html=True)
st.title('RetailInsight · Hiệu quả bán hàng')
st.markdown('<div class="intro">Doanh thu, lợi nhuận gộp và cơ hội cải thiện hiệu quả theo kênh bán.</div>', unsafe_allow_html=True)
if start > end:
    st.error('Ngày bắt đầu phải trước hoặc bằng ngày kết thúc. Chọn lại khoảng ngày hoặc đặt lại bộ lọc.')
    st.stop()

scope = filter_sales(fact, start, end, channel, region, category, product, store)
tags = [f'{start:%d/%m/%Y} – {end:%d/%m/%Y}',
    'Hai kênh' if channel == ALL else CHANNEL_LABELS[channel],
    'Tất cả vùng' if region == ALL else region,
    'Tất cả danh mục' if category == ALL else CATEGORY_LABELS.get(category, category)]
if product != ALL:
    tags.append(product)
if store != ALL:
    tags.append(store)
st.markdown('<div class="scope-line">' + ''.join(f'<span class="scope-tag">{escape(v)}</span>' for v in tags) + '</div>', unsafe_allow_html=True)
if scope.empty:
    st.info('Không có giao dịch trong phạm vi này. Hãy đổi vùng, danh mục, khoảng ngày hoặc đặt lại bộ lọc.')
    st.stop()

selected_source = fact if channel == ALL else fact.loc[fact.channel.eq(channel)]
monthly = monthly_view(scope, start, end, selected_source)
growth = growth_metric(monthly)
metrics = kpis(scope)
growth_value = growth['growth_pct']
growth_label = pd.Period(growth['period']).strftime('%m/%Y') if growth['period'] else 'Chưa đủ kỳ'
cards = st.columns(4, gap='small')
cards[0].metric('Doanh thu thuần', compact_money(metrics['revenue_units'] / SCALE),
    help=f'{number_vn(metrics["revenue_units"] / SCALE)} USD · SalesAmount sau chiết khấu.')
cards[0].caption(f'{number_vn(metrics["revenue_units"] / SCALE)} USD')
cards[1].metric('Lợi nhuận gộp', compact_money(metrics['profit_units'] / SCALE),
    help='Doanh thu sau chiết khấu trừ giá vốn; chưa trừ chi phí vận hành và marketing.')
cards[1].caption(f'{number_vn(metrics["profit_units"] / SCALE)} USD')
cards[2].metric('Biên lợi nhuận gộp', number_vn(metrics['margin_pct']) + '%' if metrics['margin_pct'] is not None else '—')
cards[2].caption('Tổng lợi nhuận / Tổng doanh thu')
cards[3].metric('Tăng trưởng theo tháng',
    ('+' if growth_value >= 0 else '') + number_vn(growth_value) + '%' if pd.notna(growth_value) else '—',
    help='Tháng đầy đủ gần nhất và tháng trước đều phải nằm trong khoảng lọc và phạm vi nguồn của các kênh đang chọn. Mẫu số bằng 0: không xác định.')
cards[3].caption(f'{growth_label} · So với tháng lịch trước')
st.caption(f'{number_vn(metrics["orders"], 0)} đơn hàng · {number_vn(len(scope), 0)} dòng bán hàng · '
    'KPI tăng trưởng loại kỳ biên theo phạm vi nguồn. Biểu đồ vẫn giữ các kỳ biên để đối chiếu.')


def finish_chart(fig, height=350):
    fig.update_layout(template='plotly_white', height=height, paper_bgcolor='white', plot_bgcolor='white',
        font=dict(family='Arial, sans-serif', size=12, color='#405a72'),
        title=dict(font=dict(size=15, color=NAVY), x=.04),
        margin=dict(l=30, r=25, t=62, b=35), separators=',.',
        legend=dict(orientation='h', y=1.12, x=0, title_text=''),
        hoverlabel=dict(bgcolor='white', font_size=12))
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor='#edf1f5', zerolinecolor='#dce6ee')
    st.plotly_chart(fig, width='stretch', config={'displaylogo': False, 'modeBarButtonsToRemove': ['lasso2d', 'select2d']}, theme=None)


def show_table(data):
    formats = {c: (lambda v: number_vn(v)) for c in data.select_dtypes('number').columns}
    for column in ['Số đơn', 'Số lượng']:
        if column in data:
            formats[column] = lambda v: number_vn(v, 0)
    st.dataframe(data.style.format(formats), hide_index=True, width='stretch')


def download_table(data, filename, label='Tải bảng CSV'):
    st.download_button(label, csv_bytes(data), filename, 'text/csv', key=filename)


overview, markets, products_tab, evidence_tab = st.tabs(['Tổng quan', 'Kênh và thị trường', 'Sản phẩm', 'Dữ liệu và kiểm chứng'])
by_channel = group_metrics(scope, ['channel'])
by_category = group_metrics(scope, ['category'])
by_region = group_metrics(scope, ['region'])

with overview:
    left, right = st.columns([2.1, 1], gap='medium')
    with left:
        trend = go.Figure()
        for column, label, color in [('revenue_usd', 'Doanh thu thuần', NAVY), ('gross_profit_usd', 'Lợi nhuận gộp', TEAL)]:
            trend.add_trace(go.Scatter(x=monthly.month_start, y=monthly[column] / 1e6, name=label,
                mode='lines+markers', line=dict(color=color, width=2.5), marker=dict(size=5),
                customdata=monthly[['month_label', column]].to_numpy(),
                hovertemplate='%{customdata[0]}<br>%{customdata[1]:,.2f} USD<extra>%{fullData.name}</extra>'))
        trend.update_layout(title='Xu hướng doanh thu và lợi nhuận', yaxis_title='Triệu USD',
            xaxis=dict(title=None, tickformat='%m/%Y', dtick='M6'))
        for row in monthly.loc[~monthly.complete].itertuples():
            trend.add_vrect(x0=row.month_start, x1=row.month_end + pd.Timedelta(1, unit='D'),
                fillcolor=AMBER, opacity=.08, line_width=0)
        finish_chart(trend, 355)
    with right:
        donut = px.pie(by_channel, values='revenue_usd', names='channel', hole=.72,
            color='channel', color_discrete_map=CHANNEL_COLORS, title='Cơ cấu doanh thu theo kênh')
        donut.update_traces(textinfo='percent', textposition='outside',
            hovertemplate='%{label}<br>%{value:,.2f} USD<br>%{percent}<extra></extra>')
        donut.add_annotation(text='DOANH THU', x=.5, y=.5, showarrow=False, font=dict(size=11, color='#73869a'))
        finish_chart(donut, 355)
    st.caption('Vùng nền vàng nhạt: tháng chưa nằm trọn trong phạm vi nguồn hoặc khoảng ngày đã chọn. '
        'Reseller kết thúc ghi nhận sớm hơn Internet; mức giảm ở cuối nguồn chưa chứng minh nhu cầu giảm.')
    lower_left, lower_right = st.columns([1, 1.1])
    with lower_left:
        category_plot = by_category.assign(label=by_category.category.map(CATEGORY_LABELS)).sort_values('gross_profit_usd')
        fig = px.bar(category_plot, x='gross_profit_usd', y='label', orientation='h',
            title='Lợi nhuận gộp theo danh mục', color_discrete_sequence=[TEAL],
            labels={'gross_profit_usd': 'USD', 'label': ''})
        fig.update_traces(hovertemplate='%{y}<br>%{x:,.2f} USD<extra></extra>')
        finish_chart(fig, 300)
    with lower_right:
        fig = px.bar(by_channel, x='channel', y='margin_pct', color='channel',
            color_discrete_map=CHANNEL_COLORS, title='Biên lợi nhuận gộp theo kênh',
            text=by_channel.margin_pct.map(lambda v: number_vn(v) + '%'),
            labels={'channel': '', 'margin_pct': '% doanh thu'})
        fig.update_layout(showlegend=False)
        fig.update_traces(textposition='outside', cliponaxis=False, hovertemplate='%{x}<br>Biên gộp: %{y:.2f}%<extra></extra>')
        finish_chart(fig, 300)
    st.subheader('Nhận xét và hướng kiểm tra')
    best_channel = by_channel.sort_values('margin_pct', ascending=False).iloc[0]
    best_category = by_category.sort_values('gross_profit_usd', ascending=False).iloc[0]
    best_region = by_region.sort_values('revenue_usd', ascending=False).iloc[0]
    messages = [
        ('Hiệu quả kênh', f'{best_channel.channel} · {number_vn(best_channel.margin_pct)}% biên gộp',
            'So sánh thêm chi phí thu hút và phục vụ khách trước khi phân bổ ngân sách.'),
        ('Đóng góp danh mục', CATEGORY_LABELS.get(best_category.category, best_category.category),
            f'{number_vn(best_category.gross_profit_usd)} USD lợi nhuận gộp. Kiểm tra năng lực cung ứng trước khi ưu tiên.'),
        ('Thị trường dẫn đầu', best_region.region,
            f'{number_vn(best_region.revenue_usd)} USD doanh thu. Đánh giá đồng thời biên gộp và chi phí phục vụ vùng.')]
    for column, (label, title, description) in zip(st.columns(3), messages):
        column.markdown(f'<div class="insight"><div class="insight-label">{escape(label)}</div>'
            f'<div class="insight-title">{escape(title)}</div><p>{escape(description)}</p></div>', unsafe_allow_html=True)
    with st.expander('Xem và tải số liệu theo tháng'):
        table = monthly[['month_label', 'revenue_usd', 'gross_profit_usd', 'growth_pct', 'complete']].rename(columns={
            'month_label': 'Tháng', 'revenue_usd': 'Doanh thu (USD)', 'gross_profit_usd': 'Lợi nhuận gộp (USD)',
            'growth_pct': 'Tăng trưởng (%)', 'complete': 'Đủ kỳ theo phạm vi nguồn'})
        show_table(table)
        st.caption('Bảng giữ tăng trưởng số học ở mọi tháng; KPI chỉ dùng cặp tháng có đủ phạm vi nguồn. Cờ đủ kỳ phản ánh biên thời gian, không bảo đảm nguồn không bỏ sót giao dịch.')
        download_table(table, 'doanh_thu_theo_thang.csv')

with markets:
    st.subheader('So sánh hiệu quả kênh bán')
    show_table(public_table(by_channel, ['channel']))
    regions = group_metrics(scope, ['region', 'channel'])
    fig = px.bar(regions, y='region', x='gross_profit_usd', color='channel', orientation='h',
        color_discrete_map=CHANNEL_COLORS, barmode='group', title='Lợi nhuận gộp theo vùng và kênh',
        labels={'region': '', 'gross_profit_usd': 'USD', 'channel': 'Kênh'})
    finish_chart(fig, 460)
    table = public_table(regions, ['region', 'channel']).sort_values('Doanh thu (USD)', ascending=False)
    show_table(table)
    download_table(table, 'hieu_qua_vung_va_kenh.csv')
    st.caption('Số đơn là distinct trong mỗi nhóm. Một đơn nhiều danh mục có thể xuất hiện ở nhiều nhóm sản phẩm; không cộng số đơn các nhóm để suy ra tổng đơn.')

with products_tab:
    heading, control = st.columns([2, 1])
    heading.subheader('Sản phẩm đóng góp và sản phẩm cần kiểm tra')
    ranking = control.selectbox('Xếp hạng', ['Lợi nhuận cao nhất', 'Lợi nhuận thấp nhất'], key='ranking')
    product_summary = group_metrics(scope, ['product', 'category', 'channel'])
    ranked = product_summary.sort_values('gross_profit_usd', ascending=ranking == 'Lợi nhuận thấp nhất')
    top = ranked.head(10).sort_values('gross_profit_usd')
    top = top.assign(product_label=top['product'] + ' · ' + top.channel)
    fig = px.bar(top, x='gross_profit_usd', y='product_label', orientation='h', color='channel',
        color_discrete_map=CHANNEL_COLORS, title='10 sản phẩm theo lựa chọn xếp hạng',
        labels={'product_label': '', 'gross_profit_usd': 'Lợi nhuận gộp (USD)', 'channel': 'Kênh'})
    finish_chart(fig, 445)
    table = public_table(ranked, ['product', 'category', 'channel'])
    show_table(table)
    download_table(table, 'hieu_qua_san_pham.csv', 'Tải toàn bộ bảng sản phẩm đang lọc')
    st.caption('Giữ các giao dịch lỗ và tính biên theo tổng doanh thu. Lợi nhuận gộp chưa phản ánh chi phí vận hành, marketing hoặc hoàn trả chưa có trong nguồn.')

with evidence_tab:
    st.caption('Các kết quả kiểm chứng bên dưới dùng toàn bộ run dữ liệu, không chịu ảnh hưởng bộ lọc kinh doanh ở thanh bên.')
    quality_tab, benchmark_tab, source_tab = st.tabs(['Chất lượng', 'Hiệu năng', 'Nguồn và công thức'])
    with quality_tab:
        quality = pd.read_csv(run / 'quality/summary.csv')
        st.subheader('Kiểm tra trước và sau nạp dữ liệu')
        st.dataframe(quality.rename(columns={'table': 'Bảng', 'rows_before': 'Dòng đầu vào',
            'rows_after': 'Dòng hợp lệ', 'duplicates_removed': 'Trùng đã loại', 'rows_rejected': 'Dòng cách ly',
            'missing_pct_before': 'Ô thiếu trước xử lý (%)'}), hide_index=True, width='stretch')
        st.caption('Ô thiếu ở ảnh/mô tả hoặc trường tùy chọn không được tự điền thành tiền. Không có dòng bị cách ly trong nguồn đã tải; các ca dữ liệu lỗi được kiểm tra bằng fixture riêng.')
        with st.expander('Chi tiết truy vết và schema'):
            st.json(manifest)
    with benchmark_tab:
        path = run / 'benchmark_summary.csv'
        if path.exists():
            benchmark = pd.read_csv(path)
            environment = json.loads((run / 'benchmark_environment.json').read_text(encoding='utf-8'))
            if environment.get('status', 'passed') != 'passed':
                st.error('Benchmark chưa hoàn tất hoặc không khớp. Bảng dưới chỉ là kết quả chẩn đoán từng lượt đã chạy.')
            benchmark['workload'] = benchmark['query'].replace({'monthly': 'Tháng và kênh',
                'region': 'Vùng và kênh', 'category': 'Danh mục và kênh', 'customer_segments': 'Phân khúc người mua'})
            fig = px.bar(benchmark, x='workload', y='median_seconds', color='engine', barmode='group',
                color_discrete_map={'pandas': TEAL, 'duckdb': '#99692c', 'spark_sql': NAVY},
                title='Thời gian truy vấn trung vị · dữ liệu gốc',
                labels={'workload': '', 'median_seconds': 'Giây', 'engine': 'Công cụ'})
            finish_chart(fig, 340)
            st.dataframe(benchmark[['workload', 'engine', 'median_seconds', 'exact_match']].rename(columns={
                'workload': 'Truy vấn', 'engine': 'Công cụ', 'median_seconds': 'Trung vị (giây)', 'exact_match': 'Khớp chính xác'}), hide_index=True, width='stretch')
            st.caption(f'Cùng Parquet và cùng phép tính; {environment["repeats"]} lần/công cụ/truy vấn trong lượt đo này. JVM đo riêng; cache hệ điều hành không xóa. Xem bảng số đo để so sánh trên cấu hình hiện tại.')
            with st.expander('Cấu hình máy và thử tăng tải 5×'):
                st.json(environment)
                for path in sorted(run.glob('load_scale_*/benchmark_summary.csv')):
                    st.dataframe(pd.read_csv(path), hide_index=True)
                    st.caption('Dữ liệu nhân bản chỉ để đo tải; không dùng để rút ra insight kinh doanh.')
        else:
            st.info('Chưa có kết quả benchmark cho lượt nạp này. Xem lệnh benchmark trong README.')
    with source_tab:
        st.subheader('Cách đọc các chỉ số')
        st.markdown('''
        | Chỉ số | Công thức và phạm vi |
        |---|---|
        | Doanh thu thuần | Tổng SalesAmount, đã trừ chiết khấu. Không cộng thuế và cước. |
        | Lợi nhuận gộp | Tổng SalesAmount − TotalProductCost. Chưa trừ chi phí vận hành. |
        | Biên lợi nhuận gộp | Tổng lợi nhuận gộp / Tổng doanh thu × 100. Mẫu số 0: không xác định. |
        | Tăng trưởng theo tháng | (Doanh thu tháng / tháng lịch trước − 1) × 100; KPI chọn cặp tháng nằm trọn trong khoảng lọc và phạm vi nguồn của các kênh đang chọn. |
        ''')
        st.write('AdventureWorksDW là dữ liệu mẫu doanh nghiệp giả lập của Microsoft, giấy phép MIT. '
            'Internet ghi nhận đến 28/01/2014; Reseller đến 29/11/2013. '
            'Cờ đủ kỳ chỉ xét biên thời gian của nguồn. Không diễn giải khoảng kết thúc ghi nhận thành biến động nhu cầu.')
        st.caption('Một dòng đơn hàng · tiền giữ chính xác theo 1/10.000 USD · mã đơn có tiền tố kênh · dữ liệu tăng tải được tách riêng.')
        st.link_button('Mở thư mục dataset Microsoft',
            'https://github.com/microsoft/sql-server-samples/tree/b47eadc85277f72843647223cde53aa1b85ffcb8/samples/databases/adventure-works/data-warehouse-install-script')
        st.caption('Phiên bản nguồn: ' + manifest['commit'])

st.markdown('<div class="footer-note">Microsoft AdventureWorksDW · Dữ liệu doanh nghiệp giả lập · '
    'Tiền tệ báo cáo USD · Lợi nhuận gộp chưa phải lợi nhuận ròng · RetailInsight</div>', unsafe_allow_html=True)
