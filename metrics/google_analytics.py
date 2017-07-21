#!/usr/bin/env python
"""Google Analytics to Prometheus metrics exporter.

Based on the Google Analytics Reporting API v4 Python quickstart:
https://developers.google.com/analytics/devguides/reporting/core/v4/quickstart/service-py.

Check the online API docs:
https://developers.google.com/analytics/devguides/reporting/core/v4/rest/v4/reports/batchGet

the interactive API explorer:
https://developers.google.com/apis-explorer/#p/analyticsreporting/v4/analyticsreporting.reports.batchGet.

and the dimensions & metrics explorer:
https://developers.google.com/analytics/devguides/reporting/core/dimsmets

Copyright 2017 Canonical Ltd.
Maximiliano Bertacchini <maximiliano.bertacchini@canonical.com>
"""
import argparse
import logging
import os

import httplib2
from prometheus_client import CollectorRegistry, Gauge
try:
    from googleapiclient.discovery import build
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    # Compatibility with python-googleapi package available in ubuntu 14.04.
    from apiclient.discovery import build
    from metrics.helpers.service_account import ServiceAccountCredentials
    logging.info('Using backported ServiceAccountCredentials')

from metrics.helpers import util


# Explicit discovery URI for backwards compatibility with older versions
# of python-googleapi.
V2_DISCOVERY_URI = ('https://{api}.googleapis.com/$discovery/rest?'
                    'version={apiVersion}')
SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']


def initialize_analyticsreporting(creds_path, scopes):
    """Initialize an analyticsreporting service object.

    Returns: analytics an authorized analyticsreporting service object.

    """
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        creds_path, scopes=scopes)

    proxy = httplib2.proxy_info_from_environment('https')
    if proxy:
        logging.info('Using proxy: %s:%s', proxy.proxy_host, proxy.proxy_port)
        # Force remote DNS resolution through the proxy (default behaviour
        # in newer releases of httplib2).
        proxy.proxy_rdns = True

    http = credentials.authorize(httplib2.Http(proxy_info=proxy))

    # Build the service object.
    analytics = build(
        'analytics', 'v4', http=http, discoveryServiceUrl=V2_DISCOVERY_URI)
    return analytics


def get_report(analytics, view_id, since):
    """Use the Analytics Service Object to query the Reporting API V4."""
    return analytics.reports().batchGet(
        body={
            'reportRequests': [{
                'viewId': view_id,
                'dateRanges': [{
                    'startDate': since,
                    'endDate': 'today',
                }],
                'metrics': [
                    {'expression': 'ga:sessions'},
                    {'expression': 'ga:newUsers'},
                    {'expression': 'ga:users'},
                ],
                'dimensions': [
                    {'name': 'ga:source'},
                ],
            }]
        }).execute()


def set_gauges(registry, response, metric_prefix):
    """Parse the Analytics Reporting API V4 response and sets metrics."""
    # pylint: disable=too-many-locals
    for report in response.get('reports', []):
        column_header = report.get('columnHeader', {})
        dimension_headers = column_header.get('dimensions', [])
        metric_header = column_header.get('metricHeader', {})
        metric_headers = metric_header.get('metricHeaderEntries', [])
        rows = report.get('data', {}).get('rows', [])

        # Dynamically create gauges based on the API query response.
        gauges = {}
        for metric in metric_headers:
            metric_name = metric['name'].replace('ga:', '')
            gauge = Gauge(
                '{}_{}'.format(metric_prefix, metric_name),
                'GA metric for {}'.format(metric_name),
                [d.replace('ga:', '') for d in dimension_headers],
                registry=registry)
            gauges[metric['name']] = gauge

        for row in rows:
            dimensions = row.get('dimensions', [])
            dimensions = [
                x.encode('ascii', errors='replace') for x in dimensions]
            date_range_values = row.get('metrics', [])

            for values in date_range_values:
                values = values.get('values')

                for metric_header, value in zip(metric_headers, values):
                    metric_name = metric_header.get('name')
                    value = int(value)

                    gauges[metric_name].labels(*dimensions).set(value)


def collect(view_id, creds_path, dry_run=False):
    """Submit data to Push Gateway."""
    registry = CollectorRegistry()
    try:
        analytics = initialize_analyticsreporting(creds_path, SCOPES)
        # Get historical, all-time total counters.
        response = get_report(analytics, view_id, '2010-01-01')
        set_gauges(registry, response, 'google_analytics')
    except Exception:  # pylint: disable=broad-except
        logging.exception('Error collecting metrics')
    finally:
        if not dry_run:
            # If set_gauges bombed out for any reason, just upload blank data.
            # Make sure no proxy is used.
            for var in ('http_proxy', 'http_proxy'):
                for envvar in (var.lower(), var.upper()):
                    os.environ.pop(envvar, None)
            util.push2gateway('google_analytics', registry)
        else:  # Debugging enabled.
            import pprint
            pprint.pprint([(x.name, x.samples) for x in registry.collect()])


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    if ARGS.dryrun:
        logging.basicConfig(level=logging.DEBUG)
        httplib2.debuglevel = 1

    VIEW_ID = os.environ['GA_VIEW_ID']
    CREDS_PATH = os.environ['GA_KEY_FILE_LOCATION']
    collect(VIEW_ID, CREDS_PATH, ARGS.dryrun)
