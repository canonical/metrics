#!/usr/bin/env python3
"""Submit metrics for merge-o-matic statistics.

Copyright 2017 Canonical Ltd.
Joshua Powers <josh.powers@canonical.com>
"""
import argparse
from collections import deque
import os
import sys

from prometheus_client import CollectorRegistry, Gauge

from metrics.helpers import util

METRIC_FILE = '/srv/patches.ubuntu.com/stats-ubuntu-server.txt'


def get_merge_data():
    """Get statistics from merge-o-matic"""
    results = {'local': 0, 'modified': 0, 'needs-merge': 0, 'needs-sync': 0,
               'repackaged': 0, 'total': 0, 'unmodified': 0}

    if not os.path.isfile(METRIC_FILE):
        print('Missing metric results file: %s' % METRIC_FILE)
        sys.exit(1)

    with open(METRIC_FILE) as metrics:
        entries = deque(metrics, 4)

    for entry in entries:
        values = entry.strip().split(' ')[3:]
        for value in values:
            k, v = value.split('=')
            results[k] = results[k] + int(v)

    return results


def collect(dryrun=False):
    """Submit data to Push Gateway."""
    results = get_merge_data()
    print('%s' % (results))

    if not dryrun:
        print('Pushing data...')
        registry = CollectorRegistry()

        Gauge('server_mom_local_total',
              '',
              None,
              registry=registry).set(results['local'])

        Gauge('server_mom_modified_total',
              '',
              None,
              registry=registry).set(results['modified'])

        Gauge('server_mom_needs_merge_total',
              '',
              None,
              registry=registry).set(results['needs-merge'])

        Gauge('server_mom_needs_sync_total',
              '',
              None,
              registry=registry).set(results['needs-sync'])

        Gauge('server_mom_repackaged_total',
              '',
              None,
              registry=registry).set(results['repackaged'])

        Gauge('server_mom_unmodified_total',
              '',
              None,
              registry=registry).set(results['unmodified'])

        util.push2gateway('merge', registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
