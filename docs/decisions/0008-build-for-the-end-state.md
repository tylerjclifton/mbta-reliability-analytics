# 0008 — Build metrics for the end state, with data thresholds

**Status:** Accepted · **Date:** 2026-10-23

## Context
Many metrics are thin at first: alert tracking began mid-2026, and station tracking on 2026-10-24. A stopgap ("use the monthly median until we have a year of data") means revisiting the site later.

## Decision
- Build the method that is most correct once enough history exists.
- Hide results below minimum-data thresholds until they qualify (e.g. ridership by alert effect needs 10 days and 4 calm weekdays per bar), and label what's still collecting.
- No "switch over later" steps. Windows are "trailing 12 months, or since tracking began, whichever is shorter."

## Consequences
- Some charts start sparse, which is acceptable and explained in their subtitles.
- The site keeps getting more complete without code changes.
