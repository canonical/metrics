#!/usr/bin/env python3
"""Submit metrics for the specififed project.

Copyright 2017 Canonical Ltd.
Joshua Powers <josh.powers@canonical.com>
"""
from prometheus_client import CollectorRegistry, Gauge

import libgateway as lgw
import util as util

BLACKLIST = ['lxd']
URL_MERGE = 'https://merges.ubuntu.com/main.json'


def get_merge_data(team='ubuntu-server'):
    """Get number of merges."""
    merges = util.get_json_from_url(URL_MERGE)
    team_pkgs = util.get_team_packages(team)

    age = 0
    counter = 0
    for package in merges:
        if package['source_package'] in team_pkgs:
            if package['source_package'] in BLACKLIST:
                continue

            value = util.dpkg_compare_versions(package['left_version'],
                                               package['right_version'])

            # Limit to only showing where Ubuntu is behind
            # upstream (i.e. '<')
            if value == '>' or value == '=':
                continue

            counter += 1
            age += package['age']

    return counter, age


def collect():
    """Main function to submit data to Push Gateway."""
    counter, age = get_merge_data()
    registry = CollectorRegistry()

    Gauge('server_merge_mom_total',
          'Src pkgs requiring attention',
          registry=registry).set(counter)

    Gauge('server_merge_mom_age_total',
          'Average age',
          registry=registry).set(age / counter)

    lgw.push2gateway('merge', registry)


if __name__ == '__main__':
    collect()
