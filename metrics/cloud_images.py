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


DAILY_CLOUD_NAMES = ['azure', 'aws', 'download', 'gce']
RELEASE_CLOUD_NAMES = DAILY_CLOUD_NAMES + [
    'aws-cn', 'aws-govcloud', 'joyent', 'rax']
CLOUD_NAMES = {'daily': DAILY_CLOUD_NAMES, 'release': RELEASE_CLOUD_NAMES}
DAILY_URL_PATTERN = ('http://cloud-images.ubuntu.com/daily/streams/v1'
                     '/com.ubuntu.cloud:daily:{cloud_name}.json')
RELEASE_URL_PATTERN = ('http://cloud-images.ubuntu.com/releases/streams/v1'
                       '/com.ubuntu.cloud:released:{cloud_name}.json')
URL_PATTERNS = {'daily': DAILY_URL_PATTERN, 'release': RELEASE_URL_PATTERN}


def parse_simplestreams_for_images(cloud_name, image_type):
    """Use sstream-query to fetch supported image information."""
    url = URL_PATTERNS[image_type].format(cloud_name=cloud_name)
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
    for image_type in ['daily', 'release']:
        for cloud_name in CLOUD_NAMES[image_type]:
            print('Counting {} images for {}...'.format(image_type,
                                                        cloud_name))
            data = parse_simplestreams_for_images(cloud_name, image_type)
            for release in data:
                for arch in data[release]:
                    count = data[release][arch]
                    print('Found {} {} images for {} {} {}'.format(
                        count, image_type, cloud_name, release, arch))
                    gauge.labels(
                        image_type, cloud_name, release, arch).set(count)

    if not dryrun:
        print('Pushing data...')
        util.push2gateway('cloud-image-count-foundations', registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
