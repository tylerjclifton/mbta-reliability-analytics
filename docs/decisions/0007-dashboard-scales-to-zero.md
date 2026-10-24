# 0007 — The dashboard scales to zero; cold starts are acceptable

**Status:** Accepted · **Date:** 2026-10-21

## Context
An always-on Cloud Run instance would remove the few-second first load, at roughly $10–15/month.

## Decision
- `serve` keeps `min_instance_count = 0`, and the first visitor waits a few seconds; a loading message covers it.
- `max_instance_count = 2` caps cost under a traffic flood. Each instance takes up to 80 concurrent connections (Cloud Run's default; one per open tab).

## Consequences
- Only free or near-free cold-start fixes are in scope (a lighter image, faster startup).
- Contrast with [0001](0001-append-only-bronze.md): paying to keep data is worth it, paying for speed isn't.
