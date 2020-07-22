#!/usr/bin/env python3
"""Submit metrics for proposed-migration statistics."""
import argparse
import csv
from io import StringIO
import logging
import urllib

from metrics.helpers import util


def get_proposed_migration_queue(data):
    """Get information about current proposed-migration queue."""
    src = 'https://people.canonical.com/~ubuntu-archive/proposed-migration/' \
          + 'update_excuses.csv'
    logging.info('Pulling proposed-migration stats')
    with urllib.request.urlopen(src) as req:
        code = req.getcode()
        if code != 200:
            logging.error('URL %s failed with code %u', req.geturl(), code)
            return
        csvdata = StringIO(req.read().decode('UTF-8'))

    csv_handle = csv.reader(csvdata)
    latest = list(csv_handle)[-1]
    valid, not_considered = [int(x) for x in latest[1:3]]
    median_age, backlog = [int(x) for x in latest[4:6]]

    data.append({
        'measurement': 'foundations_devel_proposed_migration',
        'fields': {
            # Number of packages waiting in devel-proposed
            'valid_candidates': valid,
            'not_considered': not_considered,
            # Median age of packages waiting in devel-proposed
            'median_age': median_age,
            # Size of devel-proposed backlog (packages x days)
            'backlog': backlog,
        },
    })


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    logging.basicConfig(level=logging.DEBUG)

    DATA = []
    try:
        get_proposed_migration_queue(DATA)
    finally:
        if ARGS.dryrun:
            print('Valid candidates: %i' %
                  DATA[0]['fields']['valid_candidates'])
            print('Not considered candidates: %i' %
                  DATA[0]['fields']['not_considered'])
            print('Median age: %i' % DATA[0]['fields']['median_age'])
            print('Backlog: %i' % DATA[0]['fields']['backlog'])
        else:
            util.influxdb_insert(DATA)
