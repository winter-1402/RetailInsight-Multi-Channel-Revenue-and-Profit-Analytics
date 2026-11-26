"""Xuất minh chứng và gói mã nguồn để kiểm tra trước khi đưa lên GitHub."""
import argparse
import csv
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED

import pandas as pd

from src.pipeline.analytics import monthly_view
from src.pipeline.retail import current_run
from src.ingestion.source import source_columns
from .config import RAW, ROOT

BENCHMARK_EVIDENCE = ('benchmark.csv', 'benchmark_summary.csv', 'benchmark_environment.json', 'sql_plans.txt')
QUERY_OUTPUT = re.compile(r'^(?:pandas|duckdb|spark)_(?:monthly|region|category|customer_segments)\.csv$')
LOAD_NAME = re.compile(r'^(?:load_scale_|scale)\d+_(.+)$')


def is_benchmark_evidence(name):
    return name in BENCHMARK_EVIDENCE or QUERY_OUTPUT.fullmatch(name) is not None


def verify_tests(destination=ROOT / 'output' / 'evidence'):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-X', 'utf8', '-m', 'pytest', '-q']
    with (destination / 'tests.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    output = '\n'.join(line.rstrip() for line in (destination / 'tests.log').read_text(encoding='utf-8').splitlines()) + '\n'
    (destination / 'tests.log').write_text(output, encoding='utf-8')
    (destination / 'test_status.json').write_text(json.dumps({
        'command': 'python -X utf8 -m pytest -q', 'exit_code': result.returncode}, indent=2), encoding='utf-8')
    print(output, flush=True)
    if result.returncode:
        raise RuntimeError('Kiểm thử thất bại; xem output/evidence/tests.log')
    return destination / 'tests.log'


def export_evidence(destination=ROOT / 'output' / 'evidence'):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    run = current_run()
    # Reconcile only owned optional outputs; keep verification logs and reader files.
    for previous in destination.iterdir():
        load = LOAD_NAME.fullmatch(previous.name)
        if previous.is_file() and (is_benchmark_evidence(previous.name)
                or load and (load[1] == 'synthetic_provenance.json' or is_benchmark_evidence(load[1]))):
            previous.unlink()
    for source in run.iterdir():
        if source.is_file() and (source.name == 'manifest.json' or is_benchmark_evidence(source.name)):
            shutil.copyfile(source, destination / source.name)
    for src, name in [('gold/sample_sales.csv', 'sample_sales.csv'),
            ('quality/data_quality.json', 'data_quality.json'), ('quality/summary.csv', 'quality_summary.csv')]:
        shutil.copyfile(run / src, destination / name)
    if (run / 'pipeline.log').exists():
        shutil.copyfile(run / 'pipeline.log', destination / 'pipeline.log')
    fact = pd.read_parquet(run / 'gold/fact_sales.parquet')
    month = monthly_view(fact, fact.order_date.min(), fact.order_date.max(), fact)
    month[['purchase_month', 'revenue_usd', 'gross_profit_usd', 'growth_pct', 'complete', 'comparable']].to_csv(
        destination / 'monthly_sales.csv', index=False)
    for load in run.glob('load_scale_*/'):
        for source in load.iterdir():
            if source.is_file() and (source.name == 'synthetic_provenance.json' or is_benchmark_evidence(source.name)):
                shutil.copyfile(source, destination / f'{load.name}_{source.name}')
    shutil.copyfile(RAW / 'license.txt', destination / 'MICROSOFT_LICENSE.txt')
    schema = (RAW / 'instawdbdw.sql').read_text(encoding='utf-8-sig')
    fields = ['SalesOrderNumber', 'SalesOrderLineNumber', 'OrderDate', 'OrderQuantity',
        'ExtendedAmount', 'DiscountAmount', 'SalesAmount', 'TotalProductCost']
    for table in ['FactInternetSales', 'FactResellerSales']:
        before = pd.read_csv(RAW / (table + '.csv'), sep='|', header=None,
            names=source_columns(schema, table), dtype='string', quoting=csv.QUOTE_NONE, nrows=8)
        before[fields].to_csv(destination / (table + '_before.csv'), index=False)
        after = pd.read_parquet(run / 'silver' / (table + '.parquet')).head(8)
        after[fields + ['revenue_units', 'cost_units', 'profit_units']].to_csv(
            destination / (table + '_after.csv'), index=False)
    print(f'Evidence exported to {destination}', flush=True)
    return destination


def build_package(output=ROOT / 'output/AdventureWorks_Retail_BI_GitHub.zip'):
    files = []
    allowed = {'.py', '.sql', '.md', '.css', '.png', '.svg', '.yml', '.yaml', '.json', '.csv', '.txt', '.log'}
    for folder in ['src', 'dashboard', 'tests', 'sql', 'docs', 'tasks', 'assets', '.github',
            'output/evidence', 'output/sql_benchmark']:
        for file in (ROOT / folder).rglob('*'):
            if (file.is_file() and file.suffix.lower() in allowed
                    and '__pycache__' not in file.parts and 'local' not in file.parts
                    and not file.name.startswith('.env') and file.name not in {'kaggle.json', 'secrets.toml'}):
                files.append(file)
    for name in ['README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'requirements.txt', 'pytest.ini',
            '.gitignore', '.gitattributes', 'setup.cmd', 'run.cmd', 'setup.ps1', 'run.ps1',
            '.streamlit/config.toml', '.vscode/settings.json', 'output/Bao_cao_pipeline_dashboard.pdf',
            'docs/reports/Bao_cao_CO4033_RetailInsight.docx', 'docs/reports/Bao_cao_CO4033_RetailInsight.pdf']:
        file = ROOT / name
        if file.exists():
            files.append(file)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, 'w', ZIP_DEFLATED) as zipped:
        for file in sorted(set(files)):
            zipped.write(file, file.relative_to(ROOT).as_posix())
    with ZipFile(output) as zipped:
        bad = zipped.testzip()
        if bad:
            raise ValueError(f'Gói ZIP lỗi ở {bad}')
    print(f'Package created: {output} ({output.stat().st_size:,} bytes)', flush=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', action='store_true')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.verify:
        verify_tests()
    export_evidence()
    if args.package:
        build_package()


if __name__ == '__main__':
    main()
