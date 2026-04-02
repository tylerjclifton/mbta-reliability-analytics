{# 
  Silver Layer - NWS Weather Data
  
  Applies business logic transformations to bronze weather observations.
  Currently a pass-through, but can be extended with:
  - Data quality filters (remove outlier temperatures, etc.)
  - Derived metrics (heat index, wind chill, etc.)
  - Aggregations (hourly averages, daily summaries, etc.)
  
  Grain: observation_timestamp, station_id
  Source: bronze_weather (nws dataset)
  Pattern: CTE + MERGE (native dbt)
#}

{{ build_silver_with_joins('nws', 'weather') }}
