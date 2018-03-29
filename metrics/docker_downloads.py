#!/usr/bin/env python3
"""Download counts for various distribution images on docker.

Copyright 2018 Canonical Ltd.
Joshua Powers <josh.powers@canonical.com>
"""
import argparse
import urllib.request

from metrics.helpers import util

BASE_URL = 'https://hub.docker.com/v2/repositories/library'
DISTROS = ['ubuntu', 'busybox', 'centos', 'debian', 'alpine', 'fedora']


def get_docker_data():
    """Get download for specific distro."""
    results = {}
    for distro in DISTROS:
        print('collecting data for %s' % distro)
        try:
            response = util.get_json_from_url('%s/%s' % (BASE_URL, distro))
        except urllib.error.HTTPError:
            print('failed to get data for %s' % distro)
            continue

        results[distro] = response['pull_count']

    return results


def collect(dryrun=False):
    """Submit data to Push Gateway."""
    results = get_docker_data()
    print(results)

    if not dryrun:
        print('Pushing data...')
        data = [
            {
                'measurement': 'docker_downloads',
                'fields': results,
            }
        ]

        util.influxdb_insert(data)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
