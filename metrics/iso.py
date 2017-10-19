#!/usr/bin/env python3
"""Submit metrics for merge-o-matic statistics.

Copyright 2017 Canonical Ltd.
Joshua Powers <josh.powers@canonical.com>
"""
import argparse
import re
import urllib.request

import distro_info
from prometheus_client import CollectorRegistry, Gauge

from metrics.helpers import util

BASE_URL = 'http://cdimage.ubuntu.com/ubuntu-server/'


def get_iso_size_data(release, lts=False):
    """Get ISO size stats for a release."""
    results = {'amd64': 0, 'arm64': 0, 'i386': 0, 'ppc64el': 0, 's390x': 0}

    url = BASE_URL + '/daily/current/'
    if lts:
        url = BASE_URL + release + '/daily/current/'

    print(url)
    response = urllib.request.urlopen(url)
    text = response.read().decode('utf-8')

    for arch in results:
        # search for the specific line for this ISO
        regex = r'<tr>.*>%s-server-%s.iso<.*</tr>' % (release, arch)
        match = re.search(regex, text).group(0)
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
        registry = CollectorRegistry()

        Gauge('server_iso_devel_amd64_size_total',
              'dev amd64 size',
              None,
              registry=registry).set(devel_results['amd64'])

        Gauge('server_iso_devel_arm64_size_total',
              'dev arm64 size',
              None,
              registry=registry).set(devel_results['arm64'])

        Gauge('server_iso_devel_i386_size_total',
              'dev i386 size',
              None,
              registry=registry).set(devel_results['i386'])

        Gauge('server_iso_devel_ppc64el_size_total',
              'dev ppc64el size',
              None,
              registry=registry).set(devel_results['ppc64el'])

        Gauge('server_iso_devel_s390x_size_total',
              'dev s390x size',
              None,
              registry=registry).set(devel_results['s390x'])

        Gauge('server_iso_lts_amd64_size_total',
              'lts amd64 size',
              None,
              registry=registry).set(lts_results['amd64'])

        Gauge('server_iso_lts_arm64_size_total',
              'lts arm64 size',
              None,
              registry=registry).set(lts_results['arm64'])

        Gauge('server_iso_lts_i386_size_total',
              'lts i386 size',
              None,
              registry=registry).set(lts_results['i386'])

        Gauge('server_iso_lts_ppc64el_size_total',
              'lts ppc64el size',
              None,
              registry=registry).set(lts_results['ppc64el'])

        Gauge('server_iso_lts_s390x_size_total',
              'lts s390x size',
              None,
              registry=registry).set(lts_results['s390x'])

        util.push2gateway('server-iso', registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
