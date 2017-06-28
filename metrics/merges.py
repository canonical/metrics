#!/usr/bin/env python3
"""Submit metrics for MOM statistics.

Copyright 2017 Canonical Ltd.
Joshua Powers <josh.powers@canonical.com>
"""
import argparse

from prometheus_client import CollectorRegistry, Gauge

from metrics.helpers import util

BLACKLIST = ['lxd']
URL_MERGE = 'https://merges.ubuntu.com/main.json'


def get_merge_data(team='ubuntu-server'):
    """Get number of merges."""
    merges = util.get_json_from_url(URL_MERGE)
    team_pkgs = util.get_team_packages(team)

    counter = 0
    age = 0
    for package in merges:
        if (package['source_package'] in team_pkgs and
                package['source_package'] not in BLACKLIST):
            value = util.dpkg_compare_versions(package['left_version'],
                                               package['right_version'])

            # Limit to only showing where Ubuntu is behind
            # upstream (i.e. '<')
            if value == '>' or value == '=':
                continue

            counter += 1
            age += package['age']
            print('%s (%s days)' % (package['source_package'],
                                    package['age']))

    return counter, age


def collect(dryrun=False):
    """Submit data to Push Gateway."""
    counter, age = get_merge_data()
    average = age / counter
    print('---\n%s packages (%s avg. days)' % (counter, average))

    if not dryrun:
        print('Pushing data...')
        registry = CollectorRegistry()

        Gauge('server_merge_mom_total',
              'Src pkgs requiring attention',
              None,
              registry=registry).set(counter)

        Gauge('server_merge_mom_age_total',
              'Average age',
              None,
              registry=registry).set(average)

        util.push2gateway('merge', registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('-d', '--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
