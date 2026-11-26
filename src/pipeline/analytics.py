"""Các phép phân tích dùng chung cho dashboard, xuất CSV và báo cáo."""
import pandas as pd

from src.utils.config import SCALE

ALL = 'Tất cả'
CATEGORY_LABELS = {'Bikes': 'Xe đạp', 'Components': 'Linh kiện',
    'Clothing': 'Trang phục', 'Accessories': 'Phụ kiện', 'Unknown': 'Chưa phân loại'}
CHANNEL_LABELS = {'Internet': 'Internet · Trực tuyến', 'Reseller': 'Reseller · Đại lý'}


def number_vn(value, decimals=2):
    if value is None or pd.isna(value):
        return '—'
    return f'{value:,.{decimals}f}'.translate(str.maketrans({',': '.', '.': ','}))


def compact_money(value):
    for divisor, suffix in [(1e9, 'tỷ'), (1e6, 'triệu'), (1e3, 'nghìn')]:
        if abs(value) >= divisor:
            return f'{number_vn(value / divisor)} {suffix}'
    return number_vn(value)


def filter_sales(frame, start, end, channel=ALL, region=ALL, category=ALL, product=ALL, store=ALL):
    mask = frame.order_date.ge(pd.Timestamp(start)) & frame.order_date.lt(pd.Timestamp(end) + pd.Timedelta(1, unit='D'))
    for column, value in [('channel', channel), ('region', region), ('category', category), ('product', product), ('store', store)]:
        if value != ALL:
            mask &= frame[column].eq(value)
    return frame.loc[mask].copy()


def group_metrics(frame, keys):
    result = frame.groupby(keys, as_index=False, dropna=False).agg(
        revenue_units=('revenue_units', 'sum'), cost_units=('cost_units', 'sum'),
        profit_units=('profit_units', 'sum'), orders=('order_id', 'nunique'), quantity=('quantity', 'sum'))
    result['revenue_usd'] = result.revenue_units / SCALE
    result['cost_usd'] = result.cost_units / SCALE
    result['gross_profit_usd'] = result.profit_units / SCALE
    result['margin_pct'] = result.profit_units / result.revenue_units.where(result.revenue_units.ne(0)) * 100
    return result


def public_table(data, dimensions):
    columns = dimensions + ['revenue_usd', 'gross_profit_usd', 'margin_pct', 'orders', 'quantity']
    names = {'channel': 'Kênh bán', 'region': 'Vùng', 'country': 'Quốc gia', 'category': 'Danh mục',
        'product': 'Sản phẩm', 'revenue_usd': 'Doanh thu (USD)', 'gross_profit_usd': 'Lợi nhuận gộp (USD)',
        'margin_pct': 'Biên gộp (%)', 'orders': 'Số đơn', 'quantity': 'Số lượng'}
    result = data[columns].copy()
    if 'category' in result:
        result['category'] = result.category.map(lambda v: CATEGORY_LABELS.get(v, v))
    return result.rename(columns=names)


def csv_bytes(table):
    return table.to_csv(index=False).encode('utf-8-sig')


def monthly_view(scope, start, end, source):
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    months = pd.period_range(start, end, freq='M')
    data = scope.assign(month=scope.order_date.dt.to_period('M'))
    grouped = data.groupby('month')[['revenue_units', 'profit_units']].sum()
    result = grouped.reindex(months, fill_value=0).rename_axis('month').reset_index()
    result['purchase_month'] = result.month.astype(str)
    result['month_start'] = result.month.dt.start_time
    result['month_end'] = result.month.dt.end_time.dt.normalize()
    coverage = source.groupby('channel').order_date.agg(['min', 'max'])
    earliest = max(start, coverage['min'].max().normalize())
    latest = min(end, coverage['max'].min().normalize())
    result['complete'] = result.month_start.ge(earliest) & result.month_end.le(latest)
    previous = result.revenue_units.shift(1)
    result['growth_pct'] = (result.revenue_units / previous.where(previous.ne(0)) - 1) * 100
    result['comparable'] = result.complete & result.complete.shift(1, fill_value=False)
    result['revenue_usd'] = result.revenue_units / SCALE
    result['gross_profit_usd'] = result.profit_units / SCALE
    result['month_label'] = result.month_start.dt.strftime('%m/%Y')
    return result


def growth_metric(monthly):
    full = monthly.loc[monthly.complete]
    if full.empty:
        return {'period': None, 'previous_period': None, 'growth_pct': None}
    last = full.iloc[-1]
    return {'period': last.purchase_month,
        'previous_period': str(last.month - 1),
        'growth_pct': last.growth_pct if last.comparable else None}


def kpis(frame):
    revenue, cost, profit = (int(frame[c].sum()) for c in ['revenue_units', 'cost_units', 'profit_units'])
    return {'revenue_units': revenue, 'cost_units': cost, 'profit_units': profit,
        'margin_pct': profit / revenue * 100 if revenue else None,
        'orders': int(frame.order_id.nunique())}


def monthly_sales(frame):
    if frame.empty:
        return pd.DataFrame(columns=['purchase_month', 'revenue_units', 'profit_units', 'growth_pct'])
    months = pd.period_range(frame.purchase_month.min(), frame.purchase_month.max(), freq='M').astype(str)
    out = frame.groupby('purchase_month')[['revenue_units', 'profit_units']].sum().reindex(months, fill_value=0)
    out = out.rename_axis('purchase_month').reset_index()
    previous = out.revenue_units.shift(1)
    out['growth_pct'] = (out.revenue_units / previous.where(previous.ne(0)) - 1) * 100
    return out
