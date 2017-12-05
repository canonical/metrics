#!/usr/bin/env python3
"""Submit metrics for merge-o-matic statistics.

Copyright 2017 Canonical Ltd.
Joshua Powers <josh.powers@canonical.com>
"""
import argparse
import re
import urllib.request

import distro_info

from metrics.helpers import util

BASE_URL = 'http://cdimage.ubuntu.com/ubuntu-server/'


def get_iso_size_data(release, lts=False):
    """Get ISO size stats for a release."""
    results = {'amd64': 0, 'arm64': 0, 'i386': 0, 'ppc64el': 0, 's390x': 0}

    url = '%s/daily/current/' % (BASE_URL)
    if lts:
        url = '%s/%s/daily/current/' % (BASE_URL, release)

    try:
        print(url)
        response = urllib.request.urlopen(url)
        text = response.read().decode('utf-8')
    except urllib.error.HTTPError:
        return results

    for arch in results:
        # search for the specific line for this ISO
        regex = r'<tr>.*>%s-server-%s.iso<.*</tr>' % (release, arch)

        try:
            match = re.search(regex, text).group(0)
        except AttributeError:
            continue
        # search for the size in MB or GB
        regex = r'[0-9]*\.*[0-9]+(M|G)'
        size = re.search(regex, match).group(0)

        if size.endswith('M'):
            results[arch] = int(size.strip('M'))
        elif size.endswith('G'):
            results[arch] = int(float(size.strip('G')) * 1000)

    return results


def collect(dryrun=False):
    """Submit data to Push Gateway."""
    try:
        devel = distro_info.UbuntuDistroInfo().devel()
    except distro_info.DistroDataOutdated:
        devel = distro_info.UbuntuDistroInfo().stable()

    devel_results = get_iso_size_data(devel)
    print('%s: %s' % (devel, devel_results))

    lts = distro_info.UbuntuDistroInfo().lts()
    lts_results = get_iso_size_data(lts, True)
    print('%s: %s' % (lts, lts_results))

    if not dryrun:
        print('Pushing data...')
        data = [
            {
                'measurement': 'iso_size_devel',
                'fields': devel_results,
            },
            {
                'measurement': 'iso_size_lts',
                'fields': lts_results,
            }
        ]

        util.influxdb_insert(data)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
