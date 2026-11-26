import importlib
import shutil
import subprocess
import sys
from zipfile import ZipFile
import pytest


def test_github_package_contains_entrypoints_but_no_raw_data_or_machine_state(tmp_path):
    try:
        delivery = importlib.import_module('src.utils.delivery')
    except ImportError:
        pytest.fail('Chưa có lệnh tạo bộ bàn giao GitHub')
    package = delivery.build_package(tmp_path / 'delivery.zip')
    with ZipFile(package) as zipped:
        assert zipped.testzip() is None
        names = zipped.namelist()
        assert 'dashboard/dashboard.py' in names
        assert 'src/pipeline/analytics.py' in names
        assert 'src/ingestion/source.py' in names
        assert 'src/cleaning/source.py' in names
        assert 'src/utils/config.py' in names
        assert 'src/utils/report.py' in names
        assert 'src/benchmark/runner.py' in names
        assert all(f'sql/benchmarks/Q{i}.sql' in names for i in range(1, 9))
        assert 'src/benchmark/prepare.py' in names
        assert 'src/benchmark/mart.py' in names
        assert 'tests/benchmark/test_sql_benchmark.py' in names
        assert 'dashboard/assets/dashboard.css' in names
        assert not any(n.startswith('retail_bi/') for n in names)
        assert '.streamlit/config.toml' in names
        assert '.github/workflows/ci.yml' in names
        assert 'output/Bao_cao_pipeline_dashboard.pdf' in names
        assert not any(n.startswith(('data/', '.venv/', '.cache/', '.git/')) for n in names)
        assert not any('olist' in n.lower() for n in names)
        public_report = 'docs/reports/Bao_cao_CO4033_RetailInsight'
        assert public_report + '.pdf' in names
        assert [name for name in names if name.endswith('.docx')] == [public_report + '.docx']
        assert not any(n.endswith('.pyc') for n in names)
        extracted = tmp_path / 'extracted'
        zipped.extractall(extracted)
    check = subprocess.run([sys.executable, '-c',
        'from pathlib import Path; from src.utils.config import ROOT; '
        'from src.utils import report; assert ROOT == Path.cwd(); '
        'assert (ROOT / "dashboard/assets/dashboard.css").is_file()'],
        cwd=extracted, capture_output=True, text=True, timeout=30)
    assert check.returncode == 0, check.stderr
    for module in ['src.pipeline.retail', 'src.benchmark.mart', 'src.benchmark.runner', 'src.utils.delivery']:
        check = subprocess.run([sys.executable, '-m', module, '--help'],
            cwd=extracted, capture_output=True, text=True, timeout=30)
        assert check.returncode == 0, check.stderr


def test_package_excludes_streamlit_secrets_and_environment_files(tmp_path, monkeypatch):
    from src.utils import delivery
    source = tmp_path / 'project'
    (source / '.streamlit').mkdir(parents=True)
    (source / 'docs').mkdir()
    (source / 'dashboard').mkdir()
    (source / 'dashboard/dashboard.py').write_text('print("demo")', encoding='utf-8')
    (source / '.streamlit/config.toml').write_text('[theme]\nbase="light"', encoding='utf-8')
    (source / '.streamlit/secrets.toml').write_text('token="fixture-only"', encoding='utf-8')
    (source / 'docs/private.env').write_text('TOKEN=fixture-only', encoding='utf-8')
    monkeypatch.setattr(delivery, 'ROOT', source)
    package = delivery.build_package(tmp_path / 'safe.zip')
    with ZipFile(package) as zipped:
        assert '.streamlit/config.toml' in zipped.namelist()
        assert '.streamlit/secrets.toml' not in zipped.namelist()
        assert 'docs/private.env' not in zipped.namelist()


def test_evidence_export_removes_old_optional_run_outputs_but_keeps_logs(tmp_path, monkeypatch):
    from src.utils import delivery
    actual = delivery.current_run()
    fresh = tmp_path / 'fresh-run'
    for name in ['manifest.json', 'gold/fact_sales.parquet', 'gold/sample_sales.csv',
            'quality/data_quality.json', 'quality/summary.csv',
            'silver/FactInternetSales.parquet', 'silver/FactResellerSales.parquet']:
        target = fresh / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(actual / name, target)
    destination = tmp_path / 'evidence'
    destination.mkdir()
    stale = ['benchmark.csv', 'spark_monthly.csv', 'pandas_monthly.csv', 'load_scale_5_benchmark.csv',
        'load_scale_5_duckdb_customer_segments.csv', 'scale5_synthetic_provenance.json']
    for name in stale:
        (destination / name).write_text('old-run', encoding='utf-8')
    (destination / 'tests.log').write_text('preserved-test-log', encoding='utf-8')
    (destination / 'notes.txt').write_text('reader-notes', encoding='utf-8')
    monkeypatch.setattr(delivery, 'current_run', lambda: fresh)
    delivery.export_evidence(destination)
    assert not any((destination / name).exists() for name in stale)
    assert (destination / 'manifest.json').exists()
    assert (destination / 'tests.log').read_text() == 'preserved-test-log'
    assert (destination / 'notes.txt').read_text() == 'reader-notes'
