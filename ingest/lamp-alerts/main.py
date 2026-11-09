"""
LAMP alerts ingest — the MBTA's archive of its alerts feed

Source:     LAMP_RT_ALERTS.parquet on performancedata.mbta.com, the MBTA's own
            archive of its real-time alerts feed: every alert since 2018, every
            mode, one file rewritten about hourly (docs/roadmap.md, "The MBTA's
            LAMP archive")
Cadence:    On demand (it supplies alerts from before this project's own
            full-JSON capture; decision 0016)
Each run:   Loads the whole file, in batches
Writes to:  bronze.lamp_alerts (append) — one row per alert × version ×
            informed entity × active period per run

Columns are LAMP's, with ".translation.text" dropped and "." → "_" (schema in
infra/bigquery.tf). A version never changes once posted, so a run that fails
partway leaves only rows a later run loads again, and silver drops the repeats
(lamp_alerts__base).
"""

# Import standard libraries
import io
import logging

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

# Integers stay nullable integers; pandas would otherwise turn a column with
# NULLs into floats, which the INTEGER columns reject.
INTEGER_TYPES = {arrow_type: pd.Int64Dtype() for arrow_type in (pa.int8(), pa.int16(), pa.int32(), pa.int64())}

# ── Fetch ─────────────────────────────────────────────────────────────────────

parquet = pq.ParquetFile(io.BytesIO(fetch(LAMP_URL, timeout=300).content))
logging.info(f'Fetched the LAMP file: {parquet.metadata.num_rows} rows')

if parquet.metadata.num_rows == 0:
    fail('The LAMP file held no rows')

# ── Shape and load, one batch at a time ───────────────────────────────────────

for batch in parquet.iter_batches(batch_size=BATCH_ROWS):
    df = batch.to_pandas(types_mapper=INTEGER_TYPES.get)
    df.columns = [column.removesuffix('.translation.text').replace('.', '_') for column in df.columns]
    append_to_bronze(df)
