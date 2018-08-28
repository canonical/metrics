#!/usr/bin/env python3
"""Submit metrics for merge-o-matic statistics.

Copyright 2017 Canonical Ltd.
Joshua Powers <josh.powers@canonical.com>
"""
import argparse
from collections import defaultdict, deque
import urllib.request

from prometheus_client import CollectorRegistry, Gauge

from metrics.helpers import util

URL_TEMPLATE = 'https://merges.ubuntu.com/stats-{launchpad_team_name}.txt'


def get_merge_data(team_name):
    """Get statistics from merge-o-matic."""
    results_by_component = defaultdict(dict)

    metric_url = URL_TEMPLATE.format(
        launchpad_team_name=util.get_launchpad_team_name(team_name))

    response = urllib.request.urlopen(metric_url)
    data = response.read().decode('utf-8').split('\n')
    entries = deque(filter(None, data), 4)

    for entry in entries:
        entry_parts = entry.strip().split(' ')
        component = entry_parts[2]
        if component != 'main':
            continue
        values = entry_parts[3:]
        for value in values:
            key, value = value.split('=')
            if key == 'total':
                continue
            results_by_component[component][key] = int(value)

    return results_by_component


def collect(team_name, dryrun=False):
    """Submit data to Push Gateway."""
    results_by_component = get_merge_data(team_name)
    print('%s' % (results_by_component,))

    if not dryrun:
        print('Pushing data...')

        main = results_by_component['main']
        data = [
            {
                'measurement': 'metric_merges_%s' % team_name,
                'fields': {
                    'excluded': main['excluded'],
                    'local': main['local'],
                    'modified': main['modified'],
                    'needs-merge': main['needs-merge'],
                    'needs-sync': main['needs-sync'],
                    'repackaged': main['repackaged'],
                    'unmodified': main['unmodified'],
                }
            }
        ]

        util.influxdb_insert(data)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('team_name', help='team name')
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.team_name, ARGS.dryrun)
