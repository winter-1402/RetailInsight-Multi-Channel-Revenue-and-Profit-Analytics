"""Matching table projections, ordering and pandas implementations for Q1-Q8."""
import pandas as pd
import pyarrow as pa

from src.utils.config import ROOT

SQL_DIR = ROOT / 'sql' / 'benchmarks'
MONEY = ['revenue_units', 'cost_units', 'profit_units']
QUERIES = {
    'Q1': {'title': 'Sản phẩm có giá niêm yết >= 100 USD',
        'tables': {'DimProduct': ['ProductKey', 'EnglishProductName', 'list_price_units']},
        'sort': ['ProductKey']},
    'Q2': {'title': 'Doanh thu theo đại lý',
        'tables': {'FactResellerSales': ['ResellerKey', 'order_id', 'revenue_units'],
            'DimReseller': ['ResellerKey', 'ResellerName']}, 'sort': ['ResellerKey']},
    'Q3': {'title': 'Doanh thu theo danh mục và kênh',
        'tables': {'FactInternetSales': ['ProductKey', 'channel', 'order_id', *MONEY],
            'FactResellerSales': ['ProductKey', 'channel', 'order_id', *MONEY],
            'DimProduct': ['ProductKey', 'ProductSubcategoryKey'],
            'DimProductSubcategory': ['ProductSubcategoryKey', 'ProductCategoryKey'],
            'DimProductCategory': ['ProductCategoryKey', 'EnglishProductCategoryName']},
        'sort': ['channel', 'ProductCategoryKey']},
    'Q4': {'title': 'Doanh thu theo quốc gia/bang của đại lý',
        'tables': {'FactResellerSales': ['ResellerKey', 'order_id', 'revenue_units'],
            'DimReseller': ['ResellerKey', 'GeographyKey'],
            'DimGeography': ['GeographyKey', 'CountryRegionCode', 'StateProvinceCode']},
        'sort': ['CountryRegionCode', 'StateProvinceCode']},
    'Q5': {'title': 'Doanh thu theo năm-tháng và kênh',
        'tables': {'FactInternetSales': ['OrderDateKey', 'channel', 'order_id', *MONEY],
            'FactResellerSales': ['OrderDateKey', 'channel', 'order_id', *MONEY],
            'DimDate': ['DateKey', 'FullDateAlternateKey']}, 'sort': ['purchase_month', 'channel']},
    'Q6': {'title': 'Top 3 đại lý trong mỗi quốc gia/bang',
        'tables': {'FactResellerSales': ['ResellerKey', 'revenue_units'],
            'DimReseller': ['ResellerKey', 'ResellerName', 'GeographyKey'],
            'DimGeography': ['GeographyKey', 'CountryRegionCode', 'StateProvinceCode']},
        'sort': ['CountryRegionCode', 'StateProvinceCode', 'rank']},
    'Q7': {'title': 'Doanh thu và số đơn theo loại hình đại lý',
        'tables': {'FactResellerSales': ['ResellerKey', 'order_id', *MONEY],
            'DimReseller': ['ResellerKey', 'BusinessType']}, 'sort': ['BusinessType']},
    'Q8': {'title': 'Top 10 khách hàng Internet theo chi tiêu',
        'tables': {'FactInternetSales': ['CustomerKey', 'order_id', 'revenue_units'],
            'DimCustomer': ['CustomerKey']}, 'sort': ['revenue_units', 'CustomerKey'],
        'ascending': [False, True]},
}


def normalize_result(query, frame):
    spec = QUERIES[query]
    return frame.convert_dtypes().sort_values(spec['sort'],
        ascending=spec.get('ascending', True), na_position='last', kind='stable').reset_index(drop=True)


def pandas_query(query, tables):
    if query == 'Q1':
        frame = tables['DimProduct']
        return frame.loc[frame.list_price_units.ge(1000000),
            ['ProductKey', 'EnglishProductName', 'list_price_units']].copy()
    money = ['revenue_units']
    if query in {'Q2', 'Q4', 'Q6', 'Q7'}:
        frame = tables['FactResellerSales'].merge(tables['DimReseller'],
            on='ResellerKey', how='inner', validate='many_to_one')
        if query in {'Q4', 'Q6'}:
            frame = frame.merge(tables['DimGeography'], on='GeographyKey',
                how='left', validate='many_to_one')
        if query == 'Q2':
            keys = ['ResellerKey', 'ResellerName']
        elif query == 'Q4':
            keys = ['CountryRegionCode', 'StateProvinceCode']
        elif query == 'Q7':
            keys, money = ['BusinessType'], MONEY
        else:
            keys = ['CountryRegionCode', 'StateProvinceCode', 'ResellerKey', 'ResellerName']
            totals = frame.groupby(keys, as_index=False, dropna=False).revenue_units.sum()
            totals = totals.sort_values(['revenue_units', 'ResellerKey'], ascending=[False, True], kind='stable')
            totals['rank'] = totals.groupby(keys[:2], dropna=False).cumcount() + 1
            return totals.loc[totals['rank'].le(3)]
    elif query in {'Q3', 'Q5'}:
        frame = pd.concat([tables['FactInternetSales'], tables['FactResellerSales']], ignore_index=True)
        money = MONEY
        if query == 'Q3':
            frame = frame.merge(tables['DimProduct'], on='ProductKey', how='inner', validate='many_to_one')
            frame = frame.merge(tables['DimProductSubcategory'], on='ProductSubcategoryKey',
                how='left', validate='many_to_one')
            frame = frame.merge(tables['DimProductCategory'], on='ProductCategoryKey',
                how='left', validate='many_to_one')
            keys = ['channel', 'ProductCategoryKey', 'EnglishProductCategoryName']
        else:
            frame = frame.merge(tables['DimDate'], left_on='OrderDateKey', right_on='DateKey',
                how='inner', validate='many_to_one')
            frame['purchase_month'] = frame.FullDateAlternateKey.dt.strftime('%Y-%m')
            keys = ['purchase_month', 'channel']
    elif query == 'Q8':
        frame = tables['FactInternetSales'].merge(tables['DimCustomer'], on='CustomerKey',
            how='inner', validate='many_to_one')
        result = frame.groupby('CustomerKey', as_index=False, dropna=False).agg(
            revenue_units=('revenue_units', 'sum'), orders=('order_id', 'nunique'))
        return result.sort_values(['revenue_units', 'CustomerKey'], ascending=[False, True], kind='stable').head(10)
    else:
        raise ValueError(f'Unknown query: {query}')
    return frame.groupby(keys, as_index=False, dropna=False).agg(
        **{column: (column, 'sum') for column in money}, orders=('order_id', 'nunique'))


def run_pandas_query(query, tables):
    tables = {name: tables[name][columns]
        for name, columns in QUERIES[query]['tables'].items()}
    return normalize_result(query, pandas_query(query, tables))


def register_spark_tables(spark, tables):
    for name, frame in tables.items():
        # Arrow preserves nullable int64 money and the schema of empty tables.
        schema = pa.Schema.from_pandas(frame, preserve_index=False)
        if name == 'DimDate':
            schema = schema.set(schema.get_field_index('FullDateAlternateKey'),
                pa.field('FullDateAlternateKey', pa.date32()))
        spark.createDataFrame(pa.Table.from_pandas(frame, schema=schema,
            preserve_index=False)).createOrReplaceTempView(name)


def spark_query(query, spark, statement=None):
    return spark.sql(statement if statement is not None else (SQL_DIR / f'{query}.sql').read_text(encoding='utf-8'))
