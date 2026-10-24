# ══════════════════════════════════════════════════════════════════════════════
# BigQuery — medallion datasets and bronze tables
#
#   bronze  Append-only raw history, written directly by ingest jobs. Rows are
#           only ever added, never updated or deleted, so nothing depends on a
#           source keeping its own history. Tables are defined here (not by dbt)
#           so their schemas are owned in one place; ingest jobs load against
#           the live table schema.
#   silver  dbt views: the latest version of each record, cleaned and typed.
#   gold    dbt tables the dashboard reads, rebuilt every transform run.
#
# Naming: tables are `<source>_<entity>` and keep the same name in bronze and
# silver; the dataset says which layer. A `_raw` suffix marks a table holding
# the source's records whole, as JSON, rather than chosen columns. Columns
# ending `_at` are TIMESTAMPs, `_date` are DATEs. Every bronze table ends with
# the same two audit columns.
# ══════════════════════════════════════════════════════════════════════════════

locals {
  # Audit columns appended to every bronze table by ingest/common/bronze.py
  bronze_audit_columns = [
    { name = "ingested_at", type = "TIMESTAMP", description = "When the ingest run started (UTC); shared by every row written in that run" },
    { name = "ingested_by", type = "STRING", description = "Cloud Run job that wrote the row" },
  ]

  # One entry per bronze table. Column names follow the source system; renaming
  # to project conventions happens in silver.
  bronze_tables = {
    mbta_alerts = {
      description = "15-minute snapshots of the MBTA alerts API (rail routes only). Grain: alert × route × ingest run."
      clustering  = ["alert_id", "route"]
      columns = [
        { name = "alert_id", type = "STRING", description = "MBTA alert ID" },
        { name = "route", type = "STRING", description = "MBTA route ID the alert applies to (e.g. Red, Green-B)" },
        { name = "active_period_start", type = "TIMESTAMP", description = "Start of the alert's first active period; epoch when unset" },
        { name = "active_period_end", type = "TIMESTAMP", description = "End of the alert's first active period; NULL or epoch when unset" },
        { name = "duration_certainty", type = "STRING", description = "MBTA duration certainty enum (KNOWN, ESTIMATED, UNKNOWN)" },
        { name = "header", type = "STRING", description = "Short alert text" },
        { name = "description", type = "STRING", description = "Long alert text" },
        { name = "cause", type = "STRING", description = "MBTA cause enum (e.g. SIGNAL_PROBLEM)" },
        { name = "effect", type = "STRING", description = "MBTA effect enum (e.g. DELAY, SHUTTLE)" },
        { name = "severity", type = "INTEGER", description = "MBTA severity, 0 (least) to 10 (most)" },
        { name = "created_at", type = "TIMESTAMP", description = "When MBTA created the alert" },
        { name = "updated_at", type = "TIMESTAMP", description = "When MBTA last updated the alert" },
      ]
    }

    mbta_alerts_raw = {
      description = "15-minute snapshots of the MBTA alerts API (rail routes only), each alert's full JSON as returned — including the stops it affects and every active period, which bronze.mbta_alerts drops. Started 2026-10-24. Grain: alert × ingest run."
      clustering  = ["alert_id"]
      columns = [
        { name = "alert_id", type = "STRING", description = "MBTA alert ID" },
        { name = "alert_json", type = "STRING", description = "The alert's JSON:API object exactly as returned (id, attributes, relationships), compact JSON" },
      ]
    }

    mbta_stops = {
      description = "Weekly snapshots of the MBTA stops API: each rail route's stations plus the stops inside them (platforms, entrances, nodes). Grain: stop × route × ingest run."
      clustering  = ["stop_id", "route_id"]
      columns = [
        { name = "route_id", type = "STRING", description = "MBTA route whose stations were requested; a station and its child stops repeat for each route serving it" },
        { name = "stop_id", type = "STRING", description = "MBTA stop ID: a station (place-…) or a stop inside one (platform, entrance, node)" },
        { name = "stop_name", type = "STRING", description = "Stop name; platforms carry their station's name" },
        { name = "location_type", type = "INTEGER", description = "GTFS location type: 0 = platform, 1 = station, 2 = entrance, 3 = node, 4 = boarding area" },
        { name = "parent_station_id", type = "STRING", description = "Station a child stop belongs to; NULL for stations" },
        { name = "platform_name", type = "STRING", description = "Platform's direction or destination (e.g. Boston College); NULL for non-platforms" },
        { name = "platform_code", type = "STRING", description = "Platform code, where posted" },
        { name = "description", type = "STRING", description = "MBTA stop description" },
        { name = "latitude", type = "FLOAT", description = "WGS84 latitude" },
        { name = "longitude", type = "FLOAT", description = "WGS84 longitude" },
        { name = "municipality", type = "STRING", description = "City or town" },
        { name = "address", type = "STRING", description = "Street address, where posted" },
        { name = "on_street", type = "STRING", description = "Street the stop is on, where posted" },
        { name = "at_street", type = "STRING", description = "Cross street, where posted" },
        { name = "vehicle_type", type = "INTEGER", description = "GTFS route type served: 0 = light rail, 1 = heavy rail" },
        { name = "wheelchair_boarding", type = "INTEGER", description = "GTFS accessibility: 0 = no info, 1 = accessible, 2 = not accessible" },
      ]
    }

    mbta_routes = {
      description = "Snapshots of the MBTA routes API (rail routes only). Grain: route × ingest run."
      clustering  = ["route_id"]
      columns = [
        { name = "route_id", type = "STRING", description = "MBTA route ID (e.g. Red, Green-B)" },
        { name = "long_name", type = "STRING", description = "Route display name (e.g. Green Line B)" },
        { name = "route_type", type = "INTEGER", description = "GTFS route type: 0 = light rail, 1 = heavy rail" },
        { name = "color", type = "STRING", description = "Route hex color without #" },
        { name = "description", type = "STRING", description = "MBTA route description" },
        { name = "direction_destinations", type = "STRING", description = "Terminal stations, as a stringified list" },
      ]
    }

    mbta_ridership = {
      description = "Gated station entries per day and line from MBTA ArcGIS open data; full published history every run. Grain: service date × line × ingest run."
      clustering  = ["service_date", "route_or_line"]
      columns = [
        { name = "service_date", type = "DATE", description = "MBTA service date" },
        { name = "route_or_line", type = "STRING", description = "Line name as published (e.g. Red Line)" },
        { name = "gated_entries", type = "FLOAT", description = "Sum of gated entries across all stations and time periods (fractional at shared stations)" },
      ]
    }

    noaa_weather = {
      description = "NOAA GHCN-Daily values for Boston Logan (USW00014739) in source units; recent window re-pulled every run. Grain: observation date × ingest run."
      clustering  = ["observation_date"]
      columns = [
        { name = "station_id", type = "STRING", description = "GHCN station ID" },
        { name = "observation_date", type = "DATE", description = "Local-standard-time day the values summarize" },
        { name = "tmax", type = "INTEGER", description = "Max temperature, tenths of °C" },
        { name = "tmax_attributes", type = "STRING", description = "GHCN flags for tmax: measurement,quality,source[,time]" },
        { name = "tmin", type = "INTEGER", description = "Min temperature, tenths of °C" },
        { name = "tmin_attributes", type = "STRING", description = "GHCN flags for tmin" },
        { name = "prcp", type = "INTEGER", description = "Precipitation (liquid equivalent, includes melted snow), tenths of mm" },
        { name = "prcp_attributes", type = "STRING", description = "GHCN flags for prcp" },
        { name = "snow", type = "INTEGER", description = "Snowfall, mm" },
        { name = "snow_attributes", type = "STRING", description = "GHCN flags for snow" },
      ]
    }
  }
}

# ── Datasets ──────────────────────────────────────────────────────────────────

resource "google_bigquery_dataset" "bronze" {
  dataset_id    = "bronze"
  friendly_name = "Bronze"
  description   = "Append-only raw history written by ingest jobs (all sources)"
  location      = var.location

  # Bronze is the only copy of data the sources don't keep themselves
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_dataset" "silver" {
  dataset_id    = "silver"
  friendly_name = "Silver"
  description   = "Latest version of each record per source, cleaned and typed (dbt views)"
  location      = var.location
}

resource "google_bigquery_dataset" "gold" {
  dataset_id    = "gold"
  friendly_name = "Gold"
  description   = "Cross-source tables served to the dashboard (dbt tables)"
  location      = var.location
}

# Sandboxes for local dbt builds (`--target local` writes dev_silver/dev_gold,
# see transform/macros/generate_schema_name.sql). Tables expire after 7 days so
# test builds never accumulate; rebuilding recreates them.
resource "google_bigquery_dataset" "dev" {
  for_each = toset(["dev_silver", "dev_gold"])

  dataset_id                  = each.key
  friendly_name               = "Dev ${title(trimprefix(each.key, "dev_"))}"
  description                 = "Local dbt builds (target local); tables expire after 7 days"
  location                    = var.location
  default_table_expiration_ms = 7 * 24 * 60 * 60 * 1000
}

# ── Bronze tables ─────────────────────────────────────────────────────────────

resource "google_bigquery_table" "bronze" {
  for_each = local.bronze_tables

  dataset_id          = google_bigquery_dataset.bronze.dataset_id
  table_id            = each.key
  description         = each.value.description
  deletion_protection = true

  # Partition by ingest day and cluster by grain key so silver's
  # "latest version per key" lookups stay cheap as history grows
  clustering = each.value.clustering
  time_partitioning {
    type  = "DAY"
    field = "ingested_at"
  }

  schema = jsonencode(concat(each.value.columns, local.bronze_audit_columns))

  lifecycle {
    prevent_destroy = true
  }
}
