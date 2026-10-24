{# Shared column descriptions, referenced from properties files as {{ doc('name') }} #}

{% docs ingested_at %}
When the ingest run that wrote this version started (UTC). Every row written by the same run shares this value.
{% enddocs %}

{% docs ingested_by %}
Cloud Run job that wrote this version (e.g. `ingest-mbta-alerts`).
{% enddocs %}

{% docs alert_id %}
MBTA alert ID. One alert can apply to several routes.
{% enddocs %}

{% docs route_id %}
MBTA route ID: `Red`, `Orange`, `Blue`, or a Green Line branch (`Green-B` … `Green-E`).
{% enddocs %}

{% docs station_id %}
MBTA station ID (e.g. `place-pktrm`, Park Street). Alerts name platforms; they roll up to this station. See silver.mbta_stops__base.
{% enddocs %}

{% docs line_name %}
Rail line: `Red Line`, `Orange Line`, `Blue Line`, or `Green Line` (all branches). Ridership is reported at this level.
{% enddocs %}

{% docs service_date %}
MBTA service date (Eastern). A service day runs from roughly 5am to 1am the next calendar day.
{% enddocs %}

{% docs observation_date %}
Day the weather values summarize: midnight to midnight local standard time (1am–1am during daylight saving time).
{% enddocs %}

{% docs incident_id %}
One real-world event the MBTA may have posted as several alerts (updates, "earlier disabled train" follow-ups). Alerts share an incident when they have the same route, cause, effect, and location and follow on within 2 hours (6 hours for "earlier"/"residual" follow-ups). The value is the incident's first alert ID. See silver.mbta_alerts__base.
{% enddocs %}
