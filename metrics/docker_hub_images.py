#!/usr/bin/env python3
"""
Submit metrics for Docker Hub Ubuntu image publications times/size.

Copyright 2017 Canonical Ltd.
Daniel Watkins <daniel.watkins@canonical.com>
"""
import argparse
import requests

from metrics.helpers import util

MEASUREMENT = 'docker_hub_images'
URL = 'https://hub.docker.com/v2/repositories/library/ubuntu/tags/'


def _get_repository_dicts(url):
    """Iterate over Docker Hub responses to get all repositories."""
    response = requests.get(url)
    response.raise_for_status()
    body = response.json()
    for repository in body['results']:
        yield repository
    next_url = body.get('next')
    if next_url is not None:
        yield from _get_repository_dicts(next_url)


def _get_data_points():
    """Generate InfluxDB data points."""
    for repository in _get_repository_dicts(URL):
        if '-' not in repository['name']:
            # Ignore the "latest" entry, as it's captured within the
            # serial-specific data which also gives us serial
            continue
        if repository['last_updated'] is None:
            # Some older images don't have a last_updated timestamp, so skip
            # them
            continue
        suite, serial = repository['name'].split('-')
        yield {
            'time': repository['last_updated'],
            'measurement': MEASUREMENT,
            'tags': {'suite': suite},
            'fields': {
                'serial': serial,
                'full_size': repository['full_size'],
            },
        }


def collect(dryrun=False):
    """Collect data and push to InfluxDB."""
    data = list(_get_data_points())
    if not dryrun:
        print('Pushing data...')
        util.influxdb_insert(data)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
