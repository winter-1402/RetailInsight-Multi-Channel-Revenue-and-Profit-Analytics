import json
import os
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from src.benchmark import mart as benchmark


@pytest.fixture
def spark():
    session = benchmark.spark_session()
    yield session
    session.stop()


def test_spark_uses_supported_path_when_java_home_is_stale(tmp_path, monkeypatch):
    monkeypatch.setenv('JAVA_HOME', os.environ.get('JAVA_HOME', ''))
    benchmark.configure_java()
    java_home = Path(os.environ['JAVA_HOME'])
    monkeypatch.setenv('PATH', str(java_home / 'bin'), prepend=os.pathsep)
    monkeypatch.setenv('JAVA_HOME', str(tmp_path / 'removed-jdk'))
    session = benchmark.spark_session()
    try:
        assert session.sql('SELECT 42 AS result').first().result == 42
        assert Path(os.environ['JAVA_HOME']).resolve() == java_home.resolve()
    finally:
        session.stop()


@pytest.mark.parametrize('case', ['empty', 'null_keys', 'large_money', 'loss_and_zero'])
def test_sql_matches_pandas_on_edge_cases(tmp_path, spark, case):
    frame = pd.DataFrame({
        'order_id': ['a', 'a', 'b'], 'party_id': ['u', 'u', 'v'],
        'purchase_month': ['2018-01'] * 3, 'region': ['North'] * 3,
        'category': ['Bike'] * 3, 'channel': ['Internet'] * 3,
        'revenue_units': [1000, 2000, 0], 'cost_units': [600, 2500, 500],
        'profit_units': [400, -500, -500],
    })
    if case == 'empty':
        frame = frame.iloc[:0]
    elif case == 'null_keys':
        frame.loc[2, ['purchase_month', 'region', 'category', 'order_id']] = None
    elif case == 'large_money':
        frame.loc[0, 'revenue_units'] = 2**53 + 1
        frame.loc[0, 'profit_units'] = 2**53 + 1 - 600
    path = tmp_path / 'edge.parquet'
    frame.to_parquet(path, index=False)
    spark.read.parquet(path.as_posix()).createOrReplaceTempView('sales')
    for name, (filename, keys) in benchmark.QUERIES.items():
        if name == 'customer_segments':
            continue
        actual = spark.sql((benchmark.SQL_DIR / filename).read_text(encoding='utf-8')).toPandas()
        actual = actual.sort_values(keys).reset_index(drop=True)
        baseline = benchmark.pandas_query(path, keys)
        assert_frame_equal(actual, baseline, check_dtype=False, check_exact=True)
        assert int(actual.revenue_units.sum()) == int(frame.revenue_units.sum())
        if case == 'null_keys':
            assert len(actual) == 2
            assert actual.loc[actual[keys[0]].isna(), 'orders'].item() == 0
        elif case != 'empty':
            assert actual.orders.item() == 2


def test_customer_segments_use_customer_totals_and_exact_boundaries(tmp_path, spark):
    frame = pd.DataFrame({
        'party_id': ['a', 'b', 'b', 'c', 'd', 'e', 'a'],
        'channel': ['Internet'] * 6 + ['Reseller'],
        'revenue_units': [1999999, 1000000, 1000000, 9999999, 10000000, 10000001, 0],
    })
    path = tmp_path / 'segments.parquet'
    frame.to_parquet(path, index=False)
    spark.read.parquet(path.as_posix()).createOrReplaceTempView('sales')
    actual = spark.sql((benchmark.SQL_DIR / '04_customer_segments.sql').read_text()).toPandas()
    expected = pd.DataFrame([
        ['Internet', '1000_USD_plus', 2, 20000001],
        ['Internet', '200_to_1000_USD', 2, 11999999],
        ['Internet', 'under_200_USD', 1, 1999999],
        ['Reseller', 'under_200_USD', 1, 0],
    ], columns=['channel', 'segment', 'buyers', 'revenue_units'])
    assert_frame_equal(actual, expected, check_dtype=False, check_exact=True)


def test_invalid_repeats_are_rejected_before_spark(tmp_path, monkeypatch):
    def forbidden():
        pytest.fail('Spark must not start for invalid repeats')
    monkeypatch.setattr(benchmark, 'spark_session', forbidden)
    with pytest.raises(ValueError, match='repeats'):
        benchmark.compare(tmp_path / 'missing.parquet', tmp_path, repeats=0)


def test_pandas_and_spark_queries_match_hand_calculated_totals(tmp_path):
    try:
        from src.benchmark.mart import compare
    except ImportError:
        pytest.fail('Chưa có phép so sánh pandas với Spark SQL')
    frame = pd.DataFrame({'order_id': ['a', 'a', 'b'],
        'party_id': ['u', 'u', 'v'],
        'purchase_month': ['2018-01', '2018-01', '2018-02'],
        'region': ['SP', None, 'RJ'], 'category': ['x', 'y', 'x'],
        'channel': ['Internet', 'Internet', 'Reseller'],
        'revenue_units': [1000, 2000, 5000],
        'cost_units': [600, 1000, 5500], 'profit_units': [400, 1000, -500]})
    path = tmp_path / 'fact.parquet'
    frame.to_parquet(path, index=False)
    measurements = compare(path, tmp_path, repeats=1)
    assert len(measurements) == 12
    assert set(measurements.engine) == {'pandas', 'duckdb', 'spark_sql'}
    assert set(measurements['query']) == {'monthly', 'region', 'category', 'customer_segments'}
    assert measurements['matches_baseline'].all()
    actual = pd.read_csv(tmp_path / 'spark_monthly.csv')
    assert actual.revenue_units.tolist() == [3000, 5000]
    assert actual.profit_units.tolist() == [1400, -500]
    assert actual.orders.tolist() == [1, 1]
    baseline = pd.read_csv(tmp_path / 'pandas_monthly.csv')
    assert_frame_equal(actual, baseline)
    metadata = json.loads((tmp_path / 'benchmark_environment.json').read_text())
    assert metadata['status'] == 'passed'
    assert metadata['input_sha256'] == benchmark.file_sha256(path)
    assert metadata['input_sha256_after'] == metadata['input_sha256']
    assert metadata['input_rows'] == len(frame)
    assert metadata['cpu_model']
    assert metadata['logical_cpus'] > 0
    assert 'ram_bytes' in metadata
    assert set(metadata['sql_sha256']) == {file.name for file in benchmark.SQL_DIR.glob('*.sql')}
    assert measurements.groupby(['query', 'iteration']).execution_order.apply(list).tolist() == [[1, 2, 3]] * 4


def test_group_mismatch_is_detected_even_when_grand_total_matches(tmp_path, monkeypatch):
    frame = pd.DataFrame({'order_id': ['a', 'b'], 'party_id': ['u', 'v'],
        'purchase_month': ['2018-01', '2018-02'], 'channel': ['Internet'] * 2,
        'region': ['North'] * 2, 'category': ['Bike'] * 2,
        'revenue_units': [1000, 2000], 'cost_units': [600, 1500], 'profit_units': [400, 500]})
    path = tmp_path / 'fact.parquet'
    frame.to_parquet(path, index=False)
    original = benchmark.pandas_query

    def incorrect_baseline(path, keys):
        result = original(path, keys)
        result.loc[0, 'revenue_units'] += 1
        result.loc[1, 'revenue_units'] -= 1
        return result

    monkeypatch.setattr(benchmark, 'pandas_query', incorrect_baseline)
    with pytest.raises(AssertionError):
        benchmark.compare(path, tmp_path, repeats=1)
    measurements = pd.read_csv(tmp_path / 'benchmark.csv')
    assert measurements.sum_revenue_units.nunique() == 1
    assert measurements.matches_baseline.tolist() == [True, False]
    assert not pd.read_csv(tmp_path / 'benchmark_summary.csv').complete.any()
    metadata = json.loads((tmp_path / 'benchmark_environment.json').read_text())
    assert metadata['status'] == 'failed'
    assert 'AssertionError' in metadata['error']


def test_spark_startup_failure_is_recorded(tmp_path, monkeypatch):
    path = tmp_path / 'fact.parquet'
    pd.DataFrame({'order_id': ['a']}).to_parquet(path, index=False)

    def unavailable():
        raise RuntimeError('fixture: Spark unavailable')

    monkeypatch.setattr(benchmark, 'spark_session', unavailable)
    with pytest.raises(RuntimeError, match='Spark unavailable'):
        benchmark.compare(path, tmp_path)
    metadata = json.loads((tmp_path / 'benchmark_environment.json').read_text())
    assert metadata['status'] == 'failed'
    assert pd.read_csv(tmp_path / 'benchmark.csv').empty
