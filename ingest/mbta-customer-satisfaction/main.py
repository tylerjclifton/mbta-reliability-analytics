"""
MBTA customer satisfaction ingest — the MBTA's monthly rider survey

Source:     MBTA Service Customer Satisfaction, a CSV on the MBTA's ArcGIS open
            data portal: each month's survey results, one row per question,
            with how many answered and the share giving each of its seven
            answers, from 2016-02 on
Cadence:    Weekly (the MBTA adds a month at a time: on 2026-11-14 it ran
            through the October 2026 survey)
Each run:   Pulls the whole file (~500 rows), so revised months are captured
Writes to:  bronze.mbta_customer_satisfaction (append) — one row per survey ×
            question per run

Rows are kept as published (decision 0019): wide, the seven answers in order
from most negative to most positive, each with its text and share.
"""

# Import standard libraries
import io
import logging

# Import third party libraries
import pandas as pd

# Import shared ingest helpers
from common.fetch import fetch
from common.load import append_to_bronze
from common.run import fail

# The file itself: "MBTA Service Customer Satisfaction".
CSV_URL = 'https://www.arcgis.com/sharing/rest/content/items/a15bbd44359840fa95423052980dc89d/data'

# Each question's seven answers: their text and the share giving each.
ANSWERS = range(1, 8)
TEXT_COLUMNS = ['question_description', *[f'response_{n}_text' for n in ANSWERS]]
SHARE_COLUMNS = [f'response_{n}_percent' for n in ANSWERS]

# ── Fetch ─────────────────────────────────────────────────────────────────────

response = fetch(CSV_URL, timeout=120)
logging.info(f'Fetched the file: {len(response.content):,} bytes')

# ── Shape ─────────────────────────────────────────────────────────────────────

# Columns are read by name, in the file's order; a row without a date or a
# question is skipped. Respondents stay whole numbers, NULL where missing.
columns = ['survey_date', 'question_description', 'response_total',
           *[f'response_{n}_{part}' for n in ANSWERS for part in ('text', 'percent')]]
df = pd.read_csv(io.BytesIO(response.content), usecols=columns, dtype={c: str for c in TEXT_COLUMNS})
df = df[columns].dropna(subset=['survey_date', 'question_description'])
df['survey_date'] = pd.to_datetime(df['survey_date'], format='%m/%d/%Y').dt.date
df['response_total'] = pd.to_numeric(df['response_total'], errors='coerce').round().astype('Int64')
df[SHARE_COLUMNS] = df[SHARE_COLUMNS].apply(pd.to_numeric, errors='coerce')

if df.empty:
    fail('The customer satisfaction file held no surveys')

logging.info(f"Shaped {len(df)} rows, {df['survey_date'].min()} to {df['survey_date'].max()}, "
             f"{df['question_description'].nunique()} questions")

# ── Load ──────────────────────────────────────────────────────────────────────

append_to_bronze(df)
