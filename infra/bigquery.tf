# ══════════════════════════════════════════════════════════════════════════════
# BigQuery — medallion datasets and bronze tables
#
#   bronze  Append-only raw history, written directly by ingest jobs. Rows are
#           only ever added, never updated or deleted, so nothing depends on a
#           source keeping its own history. Tables are defined here (not by
#           dbt or the ingest jobs) so their schemas are owned in one place;
#           ingest jobs load against the live table schema. Renaming one, or
#           any change Terraform would make by replacing it, follows decision
#           0013 instead.
#   silver  dbt models: each source's cleaned copy plus steps built on it
#           (views, except three incremental alert tables).
#   gold    dbt tables the dashboard reads, rebuilt every transform run.
#
# Dev sandboxes mirror the layers for local work, so nothing local touches the
# live datasets: dev_bronze (local ingest runs, ingest/common/load.py), and
# dev_silver / dev_gold (local dbt builds, which read the real bronze).
#
# Naming: tables are `<source>_<entity>`; silver's models built from each are
# `<source>_<entity>__<step>` (`__base` is the cleaned copy); the dataset says
# which layer. A `_legacy` suffix marks a frozen table kept as history, never
# written again. Columns ending `_at` are TIMESTAMPs, `_date` are DATEs. Every
# bronze table ends with the same two audit columns.
# ══════════════════════════════════════════════════════════════════════════════

locals {
  # Audit columns appended to every bronze table by ingest/common/load.py.
  bronze_audit_columns = [
    { name = "ingested_at", type = "TIMESTAMP", description = "When the ingest run started (UTC); shared by every row written in that run" },
    { name = "ingested_by", type = "STRING", description = "Cloud Run job that wrote the row" },
  ]

  # How long local test data lives in the dev sandboxes.
  dev_retention_ms = 7 * 24 * 60 * 60 * 1000

  # One entry per bronze table. Column names follow the source system; renaming
  # to project conventions happens in silver.
  bronze_tables = {
    mbta_alerts_legacy = {
      description = "FROZEN — never written since 2026-10-24, never delete. 15-minute snapshots of the MBTA alerts API (rail routes only) as the old ingest shaped them, 2026-06-07 to 2026-10-24; mbta_alerts replaced it (decision 0002). Grain: alert × route × ingest run."
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

    mbta_alerts = {
      description = "15-minute snapshots of the MBTA alerts API, each alert's full JSON as returned — including the stops it affects and every active period, which the legacy table dropped. Started 2026-10-24 (rail routes only); the whole feed, every mode, since 2026-10-28 (decision 0011). Grain: alert × ingest run."
      clustering  = ["alert_id"]
      columns = [
        { name = "alert_id", type = "STRING", description = "MBTA alert ID" },
        { name = "alert_json", type = "STRING", description = "The alert's JSON:API object exactly as returned (id, type, attributes, links), compact JSON" },
      ]
    }

    # Columns are LAMP's, with ".translation.text" dropped and "." → "_".
    # *_datetime is Eastern local time; *_timestamp is the same moment in epoch
    # seconds.
    lamp_alerts = {
      description = "The MBTA's LAMP alerts archive (performancedata.mbta.com): every alert since 2018, every mode, as LAMP flattens it. Loaded on demand, not on a schedule (decision 0016). Grain: alert × version × informed entity × active period × ingest run."
      clustering  = ["id"]
      columns = [
        { name = "id", type = "INTEGER", description = "MBTA alert ID (the API's alert_id, as a number)" },
        { name = "cause", type = "STRING", description = "GTFS-realtime cause enum (e.g. TECHNICAL_PROBLEM)" },
        { name = "cause_detail", type = "STRING", description = "MBTA cause enum, as the API's cause (e.g. SIGNAL_PROBLEM)" },
        { name = "effect", type = "STRING", description = "GTFS-realtime effect enum (e.g. DETOUR)" },
        { name = "effect_detail", type = "STRING", description = "MBTA effect enum, as the API's effect (e.g. SHUTTLE)" },
        { name = "severity_level", type = "STRING", description = "GTFS-realtime severity level (INFO, WARNING, SEVERE)" },
        { name = "severity", type = "INTEGER", description = "MBTA severity, 0 (least) to 10 (most)" },
        { name = "alert_lifecycle", type = "STRING", description = "MBTA lifecycle enum (e.g. NEW, ONGOING, UPCOMING)" },
        { name = "duration_certainty", type = "STRING", description = "MBTA duration certainty enum (KNOWN, ESTIMATED, UNKNOWN)" },
        { name = "header_text", type = "STRING", description = "Short alert text (English)" },
        { name = "description_text", type = "STRING", description = "Long alert text (English)" },
        { name = "service_effect_text", type = "STRING", description = "Short summary of the effect (English)" },
        { name = "timeframe_text", type = "STRING", description = "When the alert applies, as text (English)" },
        { name = "recurrence_text", type = "STRING", description = "How the alert recurs, as text (English)" },
        { name = "created_datetime", type = "DATETIME", description = "When MBTA created the alert, Eastern" },
        { name = "created_timestamp", type = "INTEGER", description = "When MBTA created the alert, epoch seconds" },
        { name = "last_modified_datetime", type = "DATETIME", description = "When this version was posted, Eastern" },
        { name = "last_modified_timestamp", type = "INTEGER", description = "When this version was posted, epoch seconds" },
        { name = "last_push_notification_datetime", type = "DATETIME", description = "When MBTA last sent a push notification for the alert, Eastern" },
        { name = "last_push_notification_timestamp", type = "INTEGER", description = "When MBTA last sent a push notification for the alert, epoch seconds" },
        { name = "closed_datetime", type = "DATETIME", description = "When MBTA closed (ended) the alert, Eastern; NULL while open" },
        { name = "closed_timestamp", type = "INTEGER", description = "When MBTA closed (ended) the alert, epoch seconds; NULL while open" },
        { name = "active_period_start_datetime", type = "DATETIME", description = "Start of this active period, Eastern" },
        { name = "active_period_start_timestamp", type = "INTEGER", description = "Start of this active period, epoch seconds" },
        { name = "active_period_end_datetime", type = "DATETIME", description = "End of this active period, Eastern; NULL when open-ended" },
        { name = "active_period_end_timestamp", type = "INTEGER", description = "End of this active period, epoch seconds; NULL when open-ended" },
        { name = "informed_entity_route_id", type = "STRING", description = "MBTA route ID this entity names (e.g. Red, Green-B); NULL for a stop or facility alone" },
        { name = "informed_entity_route_type", type = "INTEGER", description = "GTFS route type: 0 = light rail, 1 = subway, 2 = commuter rail, 3 = bus, 4 = ferry" },
        { name = "informed_entity_direction_id", type = "INTEGER", description = "GTFS direction (0 or 1); NULL for both" },
        { name = "informed_entity_stop_id", type = "STRING", description = "GTFS stop ID this entity names" },
        { name = "informed_entity_facility_id", type = "STRING", description = "MBTA facility ID (elevator, escalator, …)" },
        { name = "informed_entity_activities", type = "STRING", description = "Affected rider activities, pipe-separated (e.g. BOARD|EXIT|RIDE)" },
      ]
    }

    mbta_shapes = {
      description = "Weekly snapshots of the MBTA shapes API: the path of each rail route's canonical patterns and their variants. Grain: shape × route × ingest run."
      clustering  = ["shape_id", "route_id"]
      columns = [
        { name = "route_id", type = "STRING", description = "MBTA route ID whose shapes were requested (e.g. Red, Green-B); the API doesn't return it" },
        { name = "shape_id", type = "STRING", description = "GTFS shape ID; a canonical- prefix marks the route's official paths" },
        { name = "polyline", type = "STRING", description = "The path, in Google's encoded polyline format" },
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
      description = "Gated station entries per day and line from MBTA ArcGIS open data: the layer's last two years every run, and days before 2024-10-01 from its yearly archive (decision 0015). Grain: service date × line × ingest run."
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

  # Bill storage on compressed bytes: repeated snapshots compress ~100× (0014).
  storage_billing_model = "PHYSICAL"

  # Bronze is the only copy of data the sources don't keep themselves.
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

# Sandboxes for local work (decision 0012), so test data never accumulates:
#   dev_bronze           local ingest runs: ingest/common/load.py writes here
#                        unless BQ_DATASET_ID says otherwise (the Cloud Run jobs
#                        set it to bronze). Its tables are defined below, so
#                        rows expire by partition instead of whole tables.
#   dev_silver, dev_gold local dbt builds (`--target local`, see
#                        transform/macros/generate_schema_name.sql); whole
#                        tables expire, and rebuilding recreates them.
resource "google_bigquery_dataset" "dev" {
  for_each = {
    dev_bronze = "Local ingest runs (ingest/common/load.py's default); rows expire after 7 days"
    dev_silver = "Local dbt builds (target local); tables expire after 7 days"
    dev_gold   = "Local dbt builds (target local); tables expire after 7 days"
  }

  dataset_id                  = each.key
  friendly_name               = "Dev ${title(trimprefix(each.key, "dev_"))}"
  description                 = each.value
  location                    = var.location
  default_table_expiration_ms = each.key == "dev_bronze" ? null : local.dev_retention_ms
}

# ── Bronze tables ─────────────────────────────────────────────────────────────

resource "google_bigquery_table" "bronze" {
  for_each = local.bronze_tables

  dataset_id          = google_bigquery_dataset.bronze.dataset_id
  table_id            = each.key
  description         = each.value.description
  deletion_protection = true

  # Partition by ingest day and cluster by grain key so silver's
  # "latest version per key" lookups stay cheap as history grows.
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

# The same tables and schemas in dev_bronze, for local ingest runs. Frozen
# (_legacy) tables are left out, since nothing writes them. A run's rows
# expire with their ingest-day partition; the tables themselves stay.
resource "google_bigquery_table" "dev_bronze" {
  for_each = { for name, table in local.bronze_tables : name => table if !endswith(name, "_legacy") }

  dataset_id          = google_bigquery_dataset.dev["dev_bronze"].dataset_id
  table_id            = each.key
  description         = "Dev copy of bronze.${each.key} for local ingest runs; rows expire after 7 days."
  deletion_protection = false

  clustering = each.value.clustering
  time_partitioning {
    type          = "DAY"
    field         = "ingested_at"
    expiration_ms = local.dev_retention_ms
  }

  schema = jsonencode(concat(each.value.columns, local.bronze_audit_columns))
}
