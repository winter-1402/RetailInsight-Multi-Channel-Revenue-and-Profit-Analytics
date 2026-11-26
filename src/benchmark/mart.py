"""Đối chiếu pandas, DuckDB và Spark SQL trên cùng dữ liệu Parquet."""
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time

import duckdb
import pandas as pd
import pyarrow
import pyarrow.compute as pc
import pyarrow.parquet as pq
from pandas.testing import assert_frame_equal

from src.utils.config import ROOT
from src.utils.files import file_sha256
from src.pipeline.retail import current_run
from src.utils.config import SCALE

QUERIES = {
    'monthly': ('01_monthly.sql', ['purchase_month', 'channel']),
    'region': ('02_region.sql', ['region', 'channel']),
    'category': ('03_category.sql', ['category', 'channel']),
    'customer_segments': ('04_customer_segments.sql', ['channel', 'segment']),
}
SQL_DIR = ROOT / 'sql' / 'retail'
JAVA_EXE = 'java.exe' if os.name == 'nt' else 'java'
ENGINES = ('pandas', 'duckdb', 'spark_sql')


def hardware_info():
    info = {'cpu_model': platform.processor(), 'logical_cpus': os.cpu_count(),
        'physical_cores': None, 'ram_bytes': None, 'architecture': platform.machine()}
    try:
        if platform.system() == 'Windows':
            command = ("$ErrorActionPreference='Stop'; $cpu=@(Get-CimInstance Win32_Processor); "
                "@{cpu_model=($cpu.Name -join '; '); "
                "physical_cores=($cpu | Measure-Object NumberOfCores -Sum).Sum; "
                "ram_bytes=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory} | ConvertTo-Json -Compress")
            result = subprocess.run(['powershell', '-NoProfile', '-Command', command],
                capture_output=True, text=True, check=True, timeout=30)
            info.update(json.loads(result.stdout))
        elif platform.system() == 'Linux':
            cpu = Path('/proc/cpuinfo').read_text()
            info['cpu_model'] = next(line.split(':', 1)[1].strip()
                for line in cpu.splitlines() if line.startswith('model name'))
            memory = Path('/proc/meminfo').read_text()
            info['ram_bytes'] = int(next(line.split()[1]
                for line in memory.splitlines() if line.startswith('MemTotal:'))) * 1024
        elif platform.system() == 'Darwin':
            for key, name in [('cpu_model', 'machdep.cpu.brand_string'),
                    ('physical_cores', 'hw.physicalcpu'), ('ram_bytes', 'hw.memsize')]:
                value = subprocess.run(['sysctl', '-n', name], capture_output=True,
                    text=True, check=True, timeout=10).stdout.strip()
                info[key] = value if key == 'cpu_model' else int(value)
        else:
            info['hardware_note'] = 'Physical memory unavailable on this platform'
    except (OSError, subprocess.SubprocessError, ValueError, StopIteration) as error:
        info['hardware_note'] = f'Hardware probe incomplete: {error}'
    return info


def configure_java():
    candidates = []
    if java_home := os.environ.get('JAVA_HOME'):
        candidates.append(Path(java_home))
    if java := shutil.which(JAVA_EXE):
        candidates.append(Path(java).resolve().parent.parent)
    if os.name == 'nt' and (program_files := os.environ.get('ProgramFiles')):
        for vendor in ['Eclipse Adoptium', 'Microsoft', 'Java']:
            candidates.extend(sorted((Path(program_files) / vendor).glob('jdk-*'), reverse=True))
    for home in dict.fromkeys(path.resolve() for path in candidates):
        java = home / 'bin' / JAVA_EXE
        if not java.is_file():
            continue
        try:
            probe = subprocess.run([str(java), '-version'], capture_output=True,
                text=True, check=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        version = re.search(r'\bversion\s+"(\d+)', probe.stderr + probe.stdout)
        if version and int(version.group(1)) in {17, 21}:
            os.environ['JAVA_HOME'] = str(home)
            return
    raise RuntimeError('Spark 4.0.1 cần JDK 17 hoặc 21. Đặt JAVA_HOME vào thư mục JDK (không gồm bin).')


def spark_session():
    from pyspark.sql import SparkSession

    configure_java()
    os.environ.setdefault('SPARK_LOCAL_IP', '127.0.0.1')
    scratch = ROOT / '.cache' / 'spark'
    scratch.mkdir(parents=True, exist_ok=True)
    session = (SparkSession.builder.master('local[2]').appName('RetailInsightBenchmark')
        .config('spark.ui.enabled', 'false')
        .config('spark.driver.host', '127.0.0.1')
        .config('spark.sql.shuffle.partitions', '4')
        .config('spark.sql.session.timeZone', 'UTC')
        .config('spark.sql.warehouse.dir', (scratch / 'warehouse').as_uri())
        .config('spark.local.dir', str(scratch))
        .getOrCreate())
    session.sparkContext.setLogLevel('ERROR')
    return session


def pandas_query(path, keys):
    frame = pd.read_parquet(path, columns=keys + ['revenue_units', 'cost_units', 'profit_units', 'order_id'])
    return frame.groupby(keys, as_index=False, dropna=False).agg(
        revenue_units=('revenue_units', 'sum'), cost_units=('cost_units', 'sum'),
        profit_units=('profit_units', 'sum'), orders=('order_id', 'nunique')).sort_values(keys).reset_index(drop=True)


def pandas_segments(path):
    frame = pd.read_parquet(path, columns=['channel', 'party_id', 'revenue_units'])
    buyer = frame.groupby(['channel', 'party_id'], as_index=False, dropna=False).revenue_units.sum()
    buyer['segment'] = 'under_200_USD'
    buyer.loc[buyer.revenue_units >= 200 * SCALE, 'segment'] = '200_to_1000_USD'
    buyer.loc[buyer.revenue_units >= 1_000 * SCALE, 'segment'] = '1000_USD_plus'
    return buyer.groupby(['channel', 'segment'], as_index=False, dropna=False).agg(
        buyers=('party_id', 'size'), revenue_units=('revenue_units', 'sum'))


def measure_queries(path, output_dir, repeats, spark, db, measurements):
    plans = io.StringIO()
    for name, (filename, keys) in QUERIES.items():
        query = (SQL_DIR / filename).read_text(encoding='utf-8')
        baseline = None
        for iteration in range(1, repeats + 1):
            first = (iteration - 1) % len(ENGINES)
            engines = ENGINES[first:] + ENGINES[:first]
            for position, engine in enumerate(engines, start=1):
                start = time.perf_counter()
                if engine == 'pandas':
                    result = pandas_segments(path) if name == 'customer_segments' else pandas_query(path, keys)
                elif engine == 'duckdb':
                    db.read_parquet(str(path)).create_view('sales', replace=True)
                    cursor = db.execute(query)
                    # fetchall keeps SUM(HUGEINT) exact above float64 precision.
                    result = pd.DataFrame.from_records(cursor.fetchall(), columns=[column[0] for column in cursor.description])
                else:
                    spark.read.parquet(path.as_posix()).createOrReplaceTempView('sales')
                    statement = spark.sql(query)
                    result = statement.toPandas()
                elapsed = time.perf_counter() - start
                result = result.astype({key: 'string' for key in keys})
                if baseline is None:
                    baseline = result.copy()
                measurement = {'query': name, 'engine': engine, 'iteration': iteration,
                    'execution_order': position, 'seconds': elapsed, 'result_rows': len(result),
                    'matches_baseline': False, 'sum_revenue_units': int(result.revenue_units.sum())}
                measurements.append(measurement)
                prefix = 'spark' if engine == 'spark_sql' else engine
                result.to_csv(output_dir / f'{prefix}_{name}.csv', index=False)
                assert_frame_equal(result, baseline, check_dtype=False, check_exact=True)
                measurement['matches_baseline'] = True
                print(f'{name} {engine} #{iteration}: {elapsed:.4f}s; exact match', flush=True)
        print(f'\n{name} | DuckDB\n{db.execute("EXPLAIN " + query).fetchone()[1]}', file=plans)
        print(f'\n{name} | Spark SQL', file=plans)
        with redirect_stdout(plans):
            statement.explain(mode='formatted')
    (output_dir / 'sql_plans.txt').write_text(plans.getvalue(), encoding='utf-8')


def compare(path, output_dir, repeats=3):
    if repeats < 1:
        raise ValueError('repeats phải >= 1')
    path, output_dir = Path(path).resolve(), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    measurements = []
    parquet = pq.ParquetFile(path)
    metadata = {'python': platform.python_version(), 'os': platform.platform(),
        **hardware_info(), 'pandas': pd.__version__, 'pyarrow': pyarrow.__version__, 'duckdb': duckdb.__version__,
        'duckdb_threads': 2, 'arrow_cpu_count': 2,
        'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'input_path': str(path), 'input_sha256': file_sha256(path),
        'input_bytes': path.stat().st_size, 'input_rows': parquet.metadata.num_rows,
        'input_schema': str(parquet.schema_arrow), 'repeats': repeats,
        'benchmark_source_sha256': file_sha256(__file__),
        'sql_sha256': {file.name: file_sha256(file) for file in sorted(SQL_DIR.glob('*.sql'))},
        'baseline': 'First measured pandas result per query; exact per-group comparison',
        'timing_boundary': 'Parquet scan + groupby + distinct + sort + collect to pandas; no persist/cache',
        'cache_policy': 'OS cache not cleared; rotate three engines; no warm-up excluded',
        'timer': 'time.perf_counter wall-clock seconds',
        'storage_note': 'Local filesystem; disk throughput and peak memory not measured',
        'java_home': os.environ.get('JAVA_HOME'), 'status': 'running'}
    spark = None
    original_arrow_threads = pyarrow.cpu_count()
    try:
        started = time.perf_counter()
        spark = spark_session()
        metadata['spark_startup_seconds'] = time.perf_counter() - started
        metadata.update(spark=spark.version, master=spark.sparkContext.master,
            shuffle_partitions=int(spark.conf.get('spark.sql.shuffle.partitions')),
            spark_config={key: spark.sparkContext.getConf().get(key, 'default') for key in
                ['spark.driver.memory', 'spark.executor.memory', 'spark.default.parallelism']},
            sql_config={key: spark.conf.get(key) for key in ['spark.sql.session.timeZone',
                'spark.sql.adaptive.enabled', 'spark.sql.execution.arrow.pyspark.enabled',
                'spark.sql.ansi.enabled']})
        metadata['java_home'] = os.environ['JAVA_HOME']
        java = Path(os.environ['JAVA_HOME']) / 'bin' / JAVA_EXE
        metadata['java_version'] = subprocess.run([str(java), '-version'],
            capture_output=True, text=True, check=True, timeout=10).stderr
        pyarrow.set_cpu_count(2)
        started = time.perf_counter()
        with duckdb.connect(config={'threads': 2}) as db:
            metadata['duckdb_startup_seconds'] = time.perf_counter() - started
            measure_queries(path, output_dir, repeats, spark, db, measurements)
        metadata['input_sha256_after'] = file_sha256(path)
        if metadata['input_sha256_after'] != metadata['input_sha256']:
            raise ValueError('Input Parquet changed during benchmark')
        metadata['status'] = 'passed'
    except Exception as error:
        metadata.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        try:
            result = pd.DataFrame(measurements, columns=['query', 'engine', 'iteration',
                'execution_order', 'seconds', 'result_rows', 'matches_baseline', 'sum_revenue_units'])
            result.to_csv(output_dir / 'benchmark.csv', index=False)
            summary = result.groupby(['query', 'engine'], as_index=False).agg(
                median_seconds=('seconds', 'median'), min_seconds=('seconds', 'min'),
                max_seconds=('seconds', 'max'), exact_match=('matches_baseline', 'all'))
            summary['complete'] = metadata['status'] == 'passed'
            summary.to_csv(output_dir / 'benchmark_summary.csv', index=False)
            (output_dir / 'benchmark_environment.json').write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
        finally:
            pyarrow.set_cpu_count(original_arrow_threads)
            if spark is not None:
                spark.stop()
    return result


def make_load_data(path, output, scale):
    original = pq.read_table(path)
    output.mkdir(exist_ok=True)
    target = output / 'synthetic_fact.parquet'
    with pq.ParquetWriter(target, original.schema) as writer:
        for replica in range(scale):
            part = original
            for key in ['order_id', 'party_id', 'line_id']:
                field = original.schema.field(key)
                suffix = pyarrow.scalar(f':replica{replica}', type=field.type)
                values = pc.binary_join_element_wise(original[key], suffix, pyarrow.scalar('', type=field.type))
                part = part.set_column(original.schema.get_field_index(key), field, values)
            writer.write_table(part)
    (output / 'synthetic_provenance.json').write_text(json.dumps({'replication_factor': scale,
        'source_rows': len(original), 'synthetic_rows': len(original) * scale,
        'purpose': 'load test only; copied observations are not independent new business data'}, indent=2), encoding='utf-8')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--scale', type=int, default=1, help='Nhân bản kiểm tra tải, không phải giao dịch mới')
    args = parser.parse_args()
    run = current_run()
    if args.scale < 1 or args.scale > 20:
        parser.error('scale phải trong [1,20] để giới hạn bộ nhớ demo local')
    path = run / 'gold' / 'fact_sales.parquet'
    output = run
    if args.scale > 1:
        output = run / f'load_scale_{args.scale}'
        path = make_load_data(path, output, args.scale)
    compare(path, output, args.repeats)


if __name__ == '__main__':
    main()
