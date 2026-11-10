"""
LAMP alerts ingest — the MBTA's archive of its alerts feed

Source:     LAMP_RT_ALERTS.parquet on performancedata.mbta.com, the MBTA's own
            archive of its real-time alerts feed: every alert since 2018, every
            mode, one file rewritten about hourly (docs/roadmap.md, "The MBTA's
            LAMP archive")
Cadence:    Weekly (it supplies the alerts this project's own snapshots never
            saw: history before full-JSON capture, and short alerts since;
            decision 0016)
Each run:   Loads the rows LAMP modified in the last LOOKBACK_DAYS days
            (default 14), reading the whole file in batches
Writes to:  bronze.lamp_alerts (append) — one row per alert × version ×
            informed entity × active period per run
Backfill:   LOOKBACK_DAYS set higher at execution time, up to the whole file
            (docs/runbook.md)

Columns are LAMP's, with ".translation.text" dropped and "." → "_" (schema in
infra/bigquery.tf). A version never changes once posted, so the rows two loads
share (the window's overlap, or a run that failed partway) are repeats silver
drops (lamp_alerts__base).
"""

# Import standard libraries
import datetime
import io
import logging
import os

# Import third party libraries
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Import shared ingest helpers
from common.fetch import fetch
from common.load import append_to_bronze
from common.run import fail

LAMP_URL = 'https://performancedata.mbta.com/lamp/tableau/alerts/LAMP_RT_ALERTS.parquet'

# Rows per load. The file holds 5M+ rows, far more than fit in the job's
# memory (infra/cloud-run-jobs.tf) as one DataFrame, so it's shaped and loaded
# in batches: ~50 loads, well under BigQuery's 1,500 per table per day. Peak
# memory, measured 2026-11-03: 1.1 GB (2.5 GB at 500k rows per batch).
BATCH_ROWS = 100_000

# Rows modified in the last LOOKBACK_DAYS days. Weekly runs overlap by a week,
# so one failed run loses nothing.
LOOKBACK_DAYS = int(os.getenv('LOOKBACK_DAYS', '14'))
cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=LOOKBACK_DAYS)

# Integers stay nullable integers; pandas would otherwise turn a column with
# NULLs into floats, which the INTEGER columns reject.
INTEGER_TYPES = {arrow_type: pd.Int64Dtype() for arrow_type in (pa.int8(), pa.int16(), pa.int32(), pa.int64())}

# ── Fetch ─────────────────────────────────────────────────────────────────────

parquet = pq.ParquetFile(io.BytesIO(fetch(LAMP_URL, timeout=300).content))
logging.info(f'Fetched the LAMP file: {parquet.metadata.num_rows} rows')

if parquet.metadata.num_rows == 0:
    fail('The LAMP file held no rows')

# ── Shape and load, one batch at a time ───────────────────────────────────────

kept = 0
for batch in parquet.iter_batches(batch_size=BATCH_ROWS):
    df = batch.to_pandas(types_mapper=INTEGER_TYPES.get)
    df.columns = [column.removesuffix('.translation.text').replace('.', '_') for column in df.columns]
    df = df[(df['last_modified_timestamp'] >= cutoff.timestamp()).fillna(False)]
    kept += len(df)
    append_to_bronze(df)
logging.info(f'Shaped {kept} rows modified since {cutoff:%Y-%m-%d}')

# The MBTA updates alerts every day, so a window with no rows means LAMP has
# stopped updating the file.
if kept == 0:
    fail(f'The LAMP file held no rows modified in the last {LOOKBACK_DAYS} days')
