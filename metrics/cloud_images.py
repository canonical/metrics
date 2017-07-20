#!/usr/bin/env python3
"""Generate published cloud image counts.

Copyright 2017 Canonical Ltd.
Daniel Watkins <daniel.watkins@canonical.com>
"""
import argparse
import json
import subprocess
from collections import defaultdict

from prometheus_client import CollectorRegistry, Gauge

from metrics.helpers import util


CLOUD_NAMES = ['azure', 'aws', 'aws-cn', 'aws-govcloud', 'download', 'joyent',
               'gce', 'rax']
URL_PATTERN = ('http://cloud-images.ubuntu.com/releases/streams/v1'
               '/com.ubuntu.cloud:released:{cloud_name}.json')


def parse_simplestreams_for_images(cloud_name):
    """Use sstream-query to fetch supported image information."""
    url = URL_PATTERN.format(cloud_name=cloud_name)
    output = subprocess.check_output(['sstream-query', '--json', url])
    data = defaultdict(lambda: defaultdict(int))
    for product_dict in json.loads(output.decode('utf-8')):
        data[product_dict['release']][product_dict['arch']] += 1
    return data


def collect(dryrun=False):
    """Push published cloud image counts."""
    registry = CollectorRegistry()
    gauge = Gauge('foundations_cloud_images_published', '',
                  ['image_type', 'cloud', 'release', 'arch'],
                  registry=registry)
    for cloud_name in CLOUD_NAMES:
        print('Counting images for {}...'.format(cloud_name))
        data = parse_simplestreams_for_images(cloud_name)
        for release in data:
            for arch in data[release]:
                count = data[release][arch]
                print('Found {} images for {} {} {}'.format(
                    count, cloud_name, release, arch))
                gauge.labels(
                    'release', cloud_name, release, arch).set(count)

    if not dryrun:
        print('Pushing data...')
        util.push2gateway('cloud-image-count-foundations', registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
