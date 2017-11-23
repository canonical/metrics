#!/usr/bin/env python3
"""Generate published cloud image counts.

Copyright 2017 Canonical Ltd.
Daniel Watkins <daniel.watkins@canonical.com>
"""
import argparse
import datetime
import json
import os.path
import re
import subprocess
from collections import defaultdict

import distro_info
import requests
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
TODAY = datetime.date.today()
URL_PATTERNS = {'daily': DAILY_URL_PATTERN, 'release': RELEASE_URL_PATTERN}
DOCKER_CORE_ROOT = 'https://partner-images.canonical.com/core'


def _parse_serial_date_int_from_string(serial_str):
    match = re.match(r'\d+', serial_str)
    if match is None:
        raise Exception('No serial found in {}'.format(serial_str))
    return int(match.group(0))


def get_current_download_serials(download_root):
    """
    Given a download root, determine the latest current serial.

    This works, specifically, by inspecting
    <download_root>/<suite>/current/unpacked/build-info.txt for all valid
    releases.
    """
    current_serials = {}
    for release in distro_info.UbuntuDistroInfo().all:
        url = os.path.join(
            download_root, release, 'current', 'unpacked', 'build-info.txt')
        build_info_response = requests.get(url)
        if not build_info_response.ok:
            # If the release doesn't have images, we should ignore it
            continue
        for line in build_info_response.text.splitlines():
            if line.lower().startswith('serial='):
                serial = _parse_serial_date_int_from_string(
                    line.split('=')[1])
                break
        else:
            # If the build-info.txt doesn't contain a serial, we should ignore
            # it
            continue
        current_serials[release] = serial
    return current_serials


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
        serial = _parse_serial_date_int_from_string(serial)
        if serial > latest_serials[release]:
            latest_serials[release] = serial
    return image_counts, latest_serials


def _determine_serial_age(serial):
    serial_datetime = datetime.datetime.strptime(str(serial), '%Y%m%d')
    return (TODAY - serial_datetime.date()).days


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
                latest_serial_age_gauge.labels(
                    image_type, cloud_name, release).set(
                        _determine_serial_age(serial))
    print('Finding serials for docker-core...')
    docker_core_serials = get_current_download_serials(DOCKER_CORE_ROOT)
    for release, serial in docker_core_serials.items():
        age = _determine_serial_age(serial)
        print('Found {} latest serial: {} ({} days old)'.format(
            release, serial, age))
        latest_serial_gauge.labels(
            'daily', 'docker-core', release).set(serial)
        latest_serial_age_gauge.labels(
            'daily', 'docker-core', release).set(age)

    if not dryrun:
        print('Pushing data...')
        util.push2gateway('cloud-image-count-foundations', registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
