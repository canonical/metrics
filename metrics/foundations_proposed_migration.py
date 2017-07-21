#!/usr/bin/env python3
"""Submit metrics for proposed-migration statistics."""
import csv
from io import StringIO
import logging
import urllib

from metrics.helpers import util
from prometheus_client import CollectorRegistry, Gauge


def get_proposed_migration_queue(registry):
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
    valid, not_considered, discard, median_age = [int(x) for x in latest[1:]]

    gauge = Gauge('foundations_devel_proposed_migration_size',
                  'Number of packages waiting in devel-proposed',
                  ['candidate'],
                  registry=registry)
    gauge.labels('Valid Candidates').set(valid)
    gauge.labels('Not Considered').set(not_considered)

    gauge = Gauge('foundations_devel_proposed_migration_age',
                  'Median age of packages waiting in devel-proposed',
                  None,
                  registry=registry).set(median_age)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    REGISTRY = CollectorRegistry()
    try:
        get_proposed_migration_queue(REGISTRY)
    finally:
        util.push2gateway('proposed_migration', REGISTRY)
