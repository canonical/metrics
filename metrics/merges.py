#!/usr/bin/env python3
"""Submit metrics for merge-o-matic statistics.

Copyright 2017 Canonical Ltd.
Joshua Powers <josh.powers@canonical.com>
"""
import argparse
from collections import deque
import urllib.request

from prometheus_client import CollectorRegistry, Gauge

from metrics.helpers import util

URL_TEMPLATE = 'https://merges.ubuntu.com/stats-{launchpad_team_name}.txt'


def get_merge_data(team_name):
    """Get statistics from merge-o-matic."""
    results = {'local': 0, 'modified': 0, 'needs-merge': 0, 'needs-sync': 0,
               'repackaged': 0, 'total': 0, 'unmodified': 0}

    metric_url = URL_TEMPLATE.format(
        launchpad_team_name=util.get_launchpad_team_name(team_name))

    response = urllib.request.urlopen(metric_url)
    data = response.read().decode('utf-8').split('\n')
    entries = deque(filter(None, data), 4)

    for entry in entries:
        values = entry.strip().split(' ')[3:]
        for value in values:
            key, value = value.split('=')
            results[key] = results[key] + int(value)

    return results


def collect(team_name, dryrun=False):
    """Submit data to Push Gateway."""
    results = get_merge_data(team_name)
    print('%s' % (results))

    if not dryrun:
        print('Pushing data...')
        registry = CollectorRegistry()

        Gauge('{}_mom_local_total'.format(team_name),
              '',
              None,
              registry=registry).set(results['local'])

        Gauge('{}_mom_modified_total'.format(team_name),
              '',
              None,
              registry=registry).set(results['modified'])

        Gauge('{}_mom_needs_merge_total'.format(team_name),
              '',
              None,
              registry=registry).set(results['needs-merge'])

        Gauge('{}_mom_needs_sync_total'.format(team_name),
              '',
              None,
              registry=registry).set(results['needs-sync'])

        Gauge('{}_mom_repackaged_total'.format(team_name),
              '',
              None,
              registry=registry).set(results['repackaged'])

        Gauge('{}_mom_unmodified_total'.format(team_name),
              '',
              None,
              registry=registry).set(results['unmodified'])

        util.push2gateway('%s-merge' % team_name, registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('team_name', help='team name')
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.team_name, ARGS.dryrun)
