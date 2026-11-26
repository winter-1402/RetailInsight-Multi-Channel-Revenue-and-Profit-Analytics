"""Run Q1-Q8 on in-memory pandas tables and Spark SQL views, retaining evidence."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import time

import pandas as pd
import pyarrow
from pandas.testing import assert_frame_equal

from src.benchmark.prepare import DIMENSIONS, FACTS, prepare_tables, raw_hashes
from src.benchmark.mart import hardware_info, spark_session
from src.benchmark.queries import (
    QUERIES, SQL_DIR, normalize_result, register_spark_tables, run_pandas_query, spark_query)
from src.utils.config import RAW, ROOT
from src.ingestion.source import download
from src.utils.files import file_sha256


def write_report(destination, metadata, measurements):
    summary = measurements.groupby(['query', 'engine'], as_index=False).agg(
        samples=('seconds', 'size'), median_seconds=('seconds', 'median'),
        min_seconds=('seconds', 'min'), max_seconds=('seconds', 'max'),
        result_rows=('result_rows', 'first'), exact_match=('matches_baseline', 'all'))
    summary['complete'] = metadata['status'] == 'passed'
    summary.to_csv(destination / 'summary.csv', index=False)
    lines = ['# Q1–Q8: pandas và Spark SQL', '', f'Trạng thái: **{metadata["status"]}**.', '',
        f'Run: `{destination.name}`; số mẫu đã ghi: {len(measurements)}.', '',
        f'CPU: {metadata.get("cpu_model", "unknown")}; RAM: {metadata.get("ram_bytes", "unknown")} byte; '
        f'CPU logic: {metadata.get("logical_cpus", "unknown")}.', '',
        f'OS: {metadata["os"]}; Python: {metadata["python"]}; pandas: {metadata["pandas"]}; '
        f'Spark: {metadata.get("spark", "not started")}.', '',
        f'Spark startup: {metadata.get("spark_startup_seconds", "unavailable")} giây. '
        'Chi tiết cấu hình và giới hạn bộ nhớ: [environment.json](environment.json).', '',
        '| Q | pandas median (s) | Spark median (s) | Spark/pandas | Dòng kết quả | Khớp |',
        '|---|---:|---:|---:|---:|---|']
    if metadata['status'] == 'passed':
        for query, group in summary.groupby('query'):
            group = group.set_index('engine')
            baseline, actual = group.loc['pandas'], group.loc['spark_sql']
            ratio = actual.median_seconds / baseline.median_seconds
            lines.append(f'| {query} | {baseline.median_seconds:.6f} | {actual.median_seconds:.6f} | '
                f'{ratio:.2f}× | {actual.result_rows} | 100% |')
    else:
        lines.extend(['', f'Lỗi: {metadata.get("error", "run incomplete")}'])
    lines.extend(['', 'Tỷ số >1 nghĩa là pandas nhanh hơn. Chỉ so sánh hai engine trong cùng Q.', '',
        'Mốc đo: truy vấn bảng pandas trong bộ nhớ / temporary view Spark → JOIN/filter/group/window/sort '
        '→ materialize về pandas. Không đọc Parquet. '
        'Không tính chuẩn bị nguồn, nạp bảng vào Spark, khởi động JVM, hash, đối chiếu, ghi CSV hoặc lấy execution plan.', '',
        f'Nạp bảng vào Spark: {metadata.get("spark_table_setup_seconds", "unavailable")} giây. '
        'Không persist/cache dữ liệu ứng dụng; không xóa cache OS. '
        'Giữ lượt đầu, không bỏ warm-up. Thứ tự Q xáo bằng seed cố định; luân phiên engine.', '',
        'Các truy vấn chẩn đoán EXPLAIN chạy sau các lượt đo để tránh làm nóng optimizer trước phép đo. '
        'Mỗi Q lưu formatted plan trước action và executed plan sau action.', '',
        'Số tiền là số nguyên 1/10.000 USD; so khớp tuyệt đối từng ô sau sắp thứ tự. '
        'Q7 phân tích loại hình đại lý, không giả lập phương thức thanh toán.', '',
        'Không đo peak memory, tải nền hoặc tốc độ ổ đĩa. Local[2] không chứng minh hiệu năng cụm phân tán.', '',
        'Minh chứng: [measurements.csv](measurements.csv), [summary.csv](summary.csv), '
        '[input_manifest.json](input_manifest.json), [environment.json](environment.json), '
        '[benchmark.log](benchmark.log), thư mục `results/` và `plans/`. '
        'SQL và SHA-256 được lưu trong environment.json.'])
    (destination / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def run_benchmark(output=ROOT / 'output/sql_benchmark', raw_dir=RAW, repeats=5, seed=17):
    if repeats < 1:
        raise ValueError('repeats must be >= 1')
    output, raw_dir = Path(output).resolve(), Path(raw_dir).resolve()
    if output == raw_dir or output.is_relative_to(raw_dir):
        raise ValueError('Output must be outside the original data directory')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination = output / 'runs' / run_id
    destination.mkdir(parents=True)
    for folder in ['results', 'plans']:
        (destination / folder).mkdir()
    metadata = {**hardware_info(), 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'python': platform.python_version(), 'os': platform.platform(),
        'pandas': pd.__version__, 'pyarrow': pyarrow.__version__, 'repeats': repeats, 'seed': seed,
        'status': 'running', 'timer': 'time.perf_counter wall-clock seconds',
        'timing_boundary': 'In-memory query/projection + JOIN/filter/group/window/sort + collect/normalize to pandas; source loading and Spark table setup excluded',
        'input_mode': 'Validated CSV data held in pandas DataFrames and Spark temporary views; no Parquet',
        'cache_policy': 'No application persist/cache; OS cache not cleared; first runs retained',
        'storage_note': 'Local filesystem; disk type/throughput, background load and peak memory not measured',
        'query_projections': QUERIES,
        'source_sha256': {str(file.relative_to(ROOT)): file_sha256(file) for file in
            [Path(__file__), ROOT / 'src/benchmark/queries.py', ROOT / 'src/benchmark/mart.py',
             ROOT / 'src/benchmark/prepare.py', ROOT / 'src/ingestion/source.py',
             ROOT / 'src/cleaning/source.py', ROOT / 'src/utils/files.py']}}
    measurements, messages, baselines = [], [], {}
    spark = None
    try:
        tables, manifest = prepare_tables(raw_dir)
        (destination / 'input_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        metadata['preparation_seconds'] = manifest['preparation_seconds']
        metadata['sql_sha256'], statements = {}, {}
        metadata['sql_statements'] = statements
        for query in QUERIES:
            sql = SQL_DIR / f'{query}.sql'
            metadata['sql_sha256'][query] = file_sha256(sql)
            statements[query] = sql.read_text(encoding='utf-8')
        started = time.perf_counter()
        spark = spark_session()
        metadata['spark_startup_seconds'] = time.perf_counter() - started
        metadata.update(spark=spark.version, master=spark.sparkContext.master,
            default_parallelism=spark.sparkContext.defaultParallelism,
            driver_heap_max_bytes=int(spark._jvm.java.lang.Runtime.getRuntime().maxMemory()),
            sql_config={key: spark.conf.get(key) for key in ['spark.sql.shuffle.partitions',
                'spark.sql.session.timeZone', 'spark.sql.adaptive.enabled',
                'spark.sql.autoBroadcastJoinThreshold', 'spark.sql.execution.arrow.pyspark.enabled',
                'spark.sql.ansi.enabled']},
            spark_memory_config={key: spark.sparkContext.getConf().get(key, 'default')
                for key in ['spark.driver.memory', 'spark.executor.memory']})
        java = Path(os.environ['JAVA_HOME']) / 'bin' / ('java.exe' if os.name == 'nt' else 'java')
        metadata['java_version'] = subprocess.run([str(java), '-version'], capture_output=True,
            text=True, check=True, timeout=10).stderr
        started = time.perf_counter()
        register_spark_tables(spark, tables)
        metadata['spark_table_setup_seconds'] = time.perf_counter() - started
        schedule = random.Random(seed)
        for iteration in range(1, repeats + 1):
            queries = list(QUERIES)
            schedule.shuffle(queries)
            for query_position, query in enumerate(queries, start=1):
                engines = ['pandas', 'spark_sql'] if iteration % 2 else ['spark_sql', 'pandas']
                for engine_position, engine in enumerate(engines, start=1):
                    started = time.perf_counter()
                    if engine == 'pandas':
                        result = run_pandas_query(query, tables)
                    else:
                        frame = spark_query(query, spark, statements[query])
                        result = normalize_result(query, frame.toPandas())
                    seconds = time.perf_counter() - started
                    if query not in baselines:
                        baselines[query] = result.copy()
                    record = {'query': query, 'engine': engine, 'iteration': iteration,
                        'query_order': query_position, 'engine_order': engine_position,
                        'seconds': seconds, 'result_rows': len(result),
                        'input_rows': sum(manifest['tables'][table]['rows_after'] for table in QUERIES[query]['tables']),
                        'source_csv_bytes': sum(manifest['tables'][table]['raw_bytes'] for table in QUERIES[query]['tables']),
                        'matches_baseline': False}
                    measurements.append(record)
                    result_path = destination / 'results' / f'{query}_{engine}.csv'
                    result.to_csv(result_path, index=False)
                    record['result_csv_bytes'] = result_path.stat().st_size
                    assert_frame_equal(result, baselines[query], check_dtype=False, check_exact=True)
                    record['matches_baseline'] = True
                    message = f'{query} {engine} #{iteration}: {seconds:.6f}s; {len(result)} rows; exact match'
                    messages.append(message)
                    print(message, flush=True)
        for query in QUERIES:
            frame = spark_query(query, spark, statements[query])
            plan = spark._jvm.PythonSQLUtils.explainString(frame._jdf.queryExecution(), 'formatted')
            (destination / 'plans' / f'{query}_formatted.txt').write_text(
                '\n'.join(line.rstrip() for line in plan.splitlines()) + '\n', encoding='utf-8')
            frame.toPandas()
            (destination / 'plans' / f'{query}_executed.txt').write_text(
                '\n'.join(line.rstrip() for line in frame._jdf.queryExecution().executedPlan().toString().splitlines()) + '\n',
                encoding='utf-8')
        metadata['diagnostic_queries_after_measurement'] = len(QUERIES)
        metadata['raw_sha256_after_measurement'] = raw_hashes(raw_dir)
        metadata['raw_unchanged'] = metadata['raw_sha256_after_measurement'] == manifest['raw_sha256_before']
        metadata['sql_unchanged'] = all(file_sha256(SQL_DIR / f'{query}.sql') == digest
            for query, digest in metadata['sql_sha256'].items())
        if not metadata['raw_unchanged'] or not metadata['sql_unchanged']:
            raise ValueError('Input data changed during benchmark')
        metadata['status'] = 'passed'
    except Exception as error:
        metadata.update(status='failed', error=f'{type(error).__name__}: {error}')
        messages.append(metadata['error'])
        raise
    finally:
        try:
            (destination / 'environment.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
            (destination / 'benchmark.log').write_text('\n'.join(messages) + '\n', encoding='utf-8')
            frame = pd.DataFrame(measurements, columns=['query', 'engine', 'iteration', 'query_order',
                'engine_order', 'seconds', 'result_rows', 'input_rows', 'source_csv_bytes', 'matches_baseline', 'result_csv_bytes'])
            frame.to_csv(destination / 'measurements.csv', index=False)
            write_report(destination, metadata, frame)
        finally:
            if spark is not None:
                spark.stop()
    pointer = destination / 'current.tmp'
    pointer.write_text(run_id, encoding='utf-8')
    pointer.replace(output / 'current.txt')
    readme = destination / 'README.tmp'
    readme.write_text(f'# Spark SQL Q1–Q8\n\nRun thành công gần nhất: '
        f'[{run_id}](runs/{run_id}/REPORT.md).\n', encoding='utf-8')
    readme.replace(output / 'README.md')
    print(f'Results: {destination}', flush=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--seed', type=int, default=17)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/sql_benchmark')
    parser.add_argument('--raw-dir', type=Path, default=RAW)
    args = parser.parse_args()
    if args.raw_dir.resolve() == RAW.resolve() and args.repeats >= 1:
        download(tables=[*DIMENSIONS, *FACTS])
    run_benchmark(args.output, args.raw_dir, args.repeats, args.seed)


if __name__ == '__main__':
    main()
