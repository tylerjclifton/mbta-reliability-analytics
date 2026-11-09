"""
MBTA API settings — shared by the alerts, routes, shapes, and stops jobs

  - API_URL       the API's base URL
  - RAIL_ROUTES   the routes this project covers
  - api_headers() request headers carrying the API key

RAIL_ROUTES is the one place the project's routes are written down. The
routes, shapes, and stops jobs snapshot exactly these, and silver takes the
list from the routes table those snapshots build (silver.mbta_routes__base).
The alerts job captures the whole feed, and silver narrows it (decision 0011).
"""

# Import standard libraries
import os

API_URL = 'https://api-v3.mbta.com'

# Heavy rail and the Green Line branches. Mattapan (light rail) and the Silver
# Line (bus) are out of scope.
RAIL_ROUTES = ['Red', 'Blue', 'Orange', 'Green-B', 'Green-C', 'Green-D', 'Green-E']


def api_headers():
    """
    Request headers with the MBTA API key from MBTA_API_KEY, when it's set.

    The key is optional, but removes the anonymous rate limit (Secret Manager
    provides it to the jobs that call the API; see infra/cloud-run-jobs.tf). It
    goes in a header because a connection error quotes the request's URL, query
    string included, and that text reaches the failure report and its email.
    """
    key = os.getenv('MBTA_API_KEY')
    return {'x-api-key': key} if key else {}
