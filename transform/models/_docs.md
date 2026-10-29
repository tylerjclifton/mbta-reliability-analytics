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
One real-world event the MBTA may have posted as several alerts (updates, "earlier disabled train" follow-ups). Alerts share an incident when they have the same route, cause, effect, and location and follow on within 2 hours (6 hours for "earlier"/"residual" follow-ups). The value is the incident's first alert ID. See silver.mbta_alerts__by_route.
{% enddocs %}

{% docs first_seen_at %}
First ingest run that included this alert (UTC).
{% enddocs %}

{% docs last_seen_at %}
Latest ingest run that included this alert (UTC).
{% enddocs %}

{% docs alert_header %}
Short alert text.
{% enddocs %}

{% docs alert_description %}
Long alert text.
{% enddocs %}

{% docs alert_severity %}
MBTA severity, 0 (least) to 10 (most).
{% enddocs %}

{% docs alert_created_at %}
When MBTA created the alert (UTC).
{% enddocs %}

{% docs alert_updated_at %}
When MBTA last updated the alert (UTC).
{% enddocs %}

{% docs alert_start_at %}
When the alert took effect (UTC). Posted start, else when MBTA created the alert.
{% enddocs %}

{% docs alert_is_in_feed %}
True when the alert was in the latest ingest run, i.e. still listed by the API.
{% enddocs %}

{% docs incident_header %}
Short text of the incident's most recent alert.
{% enddocs %}

{% docs incident_start_at %}
Earliest start among the incident's alerts (UTC).
{% enddocs %}

{% docs incident_end_at %}
Latest end among the incident's alerts (UTC); NULL while any is ongoing.
{% enddocs %}

{% docs incident_is_in_feed %}
True when any of the incident's alerts is still listed by the API.
{% enddocs %}

{% docs route_name %}
Route display name (e.g. "Green Line B").
{% enddocs %}

{% docs station_name %}
Station name.
{% enddocs %}

{% docs station_latitude %}
Station latitude (WGS84).
{% enddocs %}

{% docs station_longitude %}
Station longitude (WGS84).
{% enddocs %}

{% docs is_wheelchair_accessible %}
True/False per the MBTA; NULL when it has no information.
{% enddocs %}
