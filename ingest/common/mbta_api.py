"""
Shared settings for the MBTA V3 API jobs (alerts, routes, stops).

  - API_URL      the API's base URL
  - RAIL_ROUTES  the routes this project covers. The routes and stops jobs
                 snapshot exactly these; silver takes the list from the routes
                 table those snapshots build (silver.mbta_routes__base), so this
                 is the one place it's written down. The alerts job captures
                 the whole feed and silver narrows it (decision 0011).
  - api_params() request params plus the API key
"""

# Import standard libraries
import os

API_URL = 'https://api-v3.mbta.com'

# Heavy rail and the Green Line branches. Mattapan (light rail) and the Silver
# Line (bus) are out of scope.
RAIL_ROUTES = ['Red', 'Blue', 'Orange', 'Green-B', 'Green-C', 'Green-D', 'Green-E']


def api_params(params):
    """
    `params` plus the MBTA API key from MBTA_API_KEY, when it's set.

    The key is optional, but removes the anonymous rate limit (Secret Manager
    provides it to the jobs that call the API; see infra/cloud-run-jobs.tf).
    """
    key = os.getenv('MBTA_API_KEY')
    return {**params, 'api_key': key} if key else dict(params)
