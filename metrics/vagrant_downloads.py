#!/usr/bin/env python3
"""Download counts for various ubuntu images on vagrant.

Copyright 2018 Canonical Ltd.
Joshua Powers <josh.powers@canonical.com>
"""
import argparse
import re
import urllib.request

from bs4 import BeautifulSoup
import requests

from metrics.helpers import util

BASE_URL = 'https://app.vagrantup.com/ubuntu'


def get_vagrant_data():
    """Get download for specific release."""
    try:
        page = requests.get(BASE_URL)
    except urllib.error.HTTPError as exception:
        print('failed to get vagrant data')
        raise ValueError from exception

    soup = BeautifulSoup(page.content, 'lxml')

    results = {}
    for item in soup.findAll('a', {'class': 'list-group-item'}):
        # ubuntu/trusty64 --> trusty64
        release = item.find_next('img', alt=True)['alt'].replace('ubuntu/', '')
        # '30,095,931 downloads' -- > 30095931
        downloads = item.find_next(text=re.compile('downloads')).strip()
        downloads = int(downloads.replace(',', '').replace(' downloads', ''))
        results[release] = downloads

    return results


def collect(dryrun=False):
    """Submit data to Push Gateway."""
    results = get_vagrant_data()
    print(results)

    if not dryrun:
        print('Pushing data...')
        data = [
            {
                'measurement': 'vagrant_downloads',
                'fields': results,
            }
        ]

        util.influxdb_insert(data)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
