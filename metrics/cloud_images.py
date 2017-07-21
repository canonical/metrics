#!/usr/bin/env python3
"""Generate published cloud image counts.

Copyright 2017 Canonical Ltd.
Daniel Watkins <daniel.watkins@canonical.com>
"""
import argparse
import datetime
import json
import re
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
    image_counts = defaultdict(lambda: defaultdict(int))
    latest_serials = defaultdict(int)
    for product_dict in json.loads(output.decode('utf-8')):
        release = product_dict['release']
        image_counts[release][product_dict['arch']] += 1
        serial = product_dict['version_name']
        if 'beta' in serial or 'LATEST' in serial:
            continue
        match = re.match(r'\d+', serial)
        if match is None:
            raise Exception('No serial found in {}'.format(serial))
        serial = int(match.group(0))
        if serial > latest_serials[release]:
            latest_serials[release] = serial
    return image_counts, latest_serials


def collect(dryrun=False):
    """Push published cloud image counts."""
    registry = CollectorRegistry()
    count_gauge = Gauge('foundations_cloud_images_published',
                        'The number of cloud images published',
                        ['image_type', 'cloud', 'release', 'arch'],
                        registry=registry)
    latest_serial_gauge = Gauge('foundations_cloud_images_current_serial',
                                'The date portion of the latest serial',
                                ['image_type', 'cloud', 'release'],
                                registry=registry)
    latest_serial_age_gauge = Gauge(
        'foundations_cloud_images_current_serial_age',
        'The time in days between the last serial and today',
        ['image_type', 'cloud', 'release'], registry=registry)
    for image_type in ['daily', 'release']:
        for cloud_name in CLOUD_NAMES[image_type]:
            print('Counting {} images for {}...'.format(image_type,
                                                        cloud_name))
            image_counts, latest_serials = parse_simplestreams_for_images(
                cloud_name, image_type)
            for release in image_counts:
                for arch in image_counts[release]:
                    count = image_counts[release][arch]
                    print('Found {} {} images for {} {} {}'.format(
                        count, image_type, cloud_name, release, arch))
                    count_gauge.labels(
                        image_type, cloud_name, release, arch).set(count)
            for release in latest_serials:
                serial = latest_serials[release]
                latest_serial_gauge.labels(
                    image_type, cloud_name, release).set(serial)
                serial_datetime = datetime.datetime.strptime(str(serial),
                                                             '%Y%m%d')
                serial_age = (datetime.date.today()
                              - serial_datetime.date()).days
                latest_serial_age_gauge.labels(
                    image_type, cloud_name, release).set(serial_age)

    if not dryrun:
        print('Pushing data...')
        util.push2gateway('cloud-image-count-foundations', registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
