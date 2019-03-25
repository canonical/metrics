#!/usr/bin/env python3
"""Submit metrics regarding retracing of crashes for the Error Tracker.

Copyright 2019 Canonical Ltd.
Brian Murray <brian@canonical.com>
"""

import argparse
import sys

from datetime import date, datetime

from metrics.helpers import util

BASE_ERRORS_URL = 'https://errors.ubuntu.com/api/1.0'
TODAY = date.today()


def get_rresults_data(base_errors_url):
    """Download retracers results url and return json data."""
    # limit of 1 will only return today's data
    results_url = '%s/retracers-results/?limit=1&format=json' % base_errors_url
    results_json = util.get_json_from_url(results_url)
    return results_json


def collect(environment, dryrun=False):
    """Collect and push retracers results metrics."""
    base_errors_url = BASE_ERRORS_URL
    if environment == 'staging':
        base_errors_url = base_errors_url.replace('errors.', 'errors.staging.')
    retrace_results_json = get_rresults_data(base_errors_url)

    if len(retrace_results_json['objects']) == 0:
        print("No retracing has occurred")
        sys.exit(1)
    if retrace_results_json['objects'][0]['date'] != TODAY.strftime('%Y%m%d'):
        print("The results are not for today, quitting.")
        sys.exit(0)

    results = retrace_results_json['objects'][0]['value']
    for value in results:
        data = []
        arch = ''
        release = value
        if ':' in value:
            release, arch = value.split(':')
        if dryrun:
            if arch:
                print("%s:%s" % (release, arch))
            else:
                print("%s" % value)
        for result in results[value]:
            count = results[value][result]
            if not result:
                result = 'unclassified'
            if dryrun:
                print("%s: %s" % (result, count))
                continue
            data.append({
                # we don't need per minute counts of results
                'time': datetime(TODAY.year, TODAY.month, TODAY.day),
                'measurement': 'foundations_%s_retracers_results' %
                               environment,
                'fields': {
                    'count': count,
                },
                'tags': {
                    'release': release,
                    'arch': arch,
                    'result': result,
                }
            })

        if not dryrun:
            util.influxdb_insert(data)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    PARSER.add_argument('--environment', help='Error Tracker environment')
    ARGS = PARSER.parse_args()
    ENVIRONMENT = ARGS.environment

    if ENVIRONMENT not in ['staging', 'production']:
        print("Unknown environment %s" % ENVIRONMENT)
        sys.exit(1)
    collect(ENVIRONMENT, ARGS.dryrun)
