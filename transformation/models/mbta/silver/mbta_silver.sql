{#
  Silver Layer - Combined MBTA Data
  
  Joins all MBTA bronze sources together using CTE pattern:
  - alerts_base (base CTE with field renaming/casting)
  - routes_base (joined CTE with field renaming/casting)
  
  Uses native dbt MERGE for incremental updates.
#}

{{ build_silver_with_joins('mbta', 'alerts') }}
