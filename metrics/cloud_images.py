#!/usr/bin/env python3
"""Generate published cloud image counts.

Copyright 2017 Canonical Ltd.
Daniel Watkins <daniel.watkins@canonical.com>
"""
import argparse
import datetime
import logging
import sys
import os.path
import re
from collections import defaultdict

import distro_info  # pylint: disable=wrong-import-order
import requests
from prometheus_client import CollectorRegistry, Gauge
from metrics.helpers.sstreams import UbuntuCloudImages, ifilter


DAILY_CLOUD_NAMES = ['azure', 'aws', 'download', 'gce']
RELEASE_CLOUD_NAMES = DAILY_CLOUD_NAMES + [
    'aws-cn', 'aws-govcloud', 'joyent', 'rax']
MACHINE_TYPE_FIELDS = ['virt', 'root_store']

INDEX_PATH_TO_IMAGE_TYPE = {
    'releases': 'release',
    'minimal/releases': 'release',
    'daily': 'daily',
    'minimal/daily': 'daily'
}

TODAY = datetime.date.today()
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


def parse_simplestreams_for_images(products):
    """
    Use sstream-query to fetch supported image information.

    For non-AWS clouds, this returns a tuple of
    ({release: {arch: count_of_images}}, {release: latest_serial}).  For
    AWS clouds, the first element of the tuple remains the same, but the
    second is {release: {virt_storage: {latest_serial}}}.
    """
    recursive_dict = lambda: defaultdict(recursive_dict)
    image_statistics = recursive_dict()

    for product in products:

        image_type = INDEX_PATH_TO_IMAGE_TYPE[product['index_path']]

        cloudname = product.get('cloudname')
        if not cloudname and product['datatype'] == 'image-downloads':
            cloudname = 'download'

        machine_type = '-'.join(
            filter(None, [product.get(f) for f in MACHINE_TYPE_FIELDS])
        )

        stat = image_statistics\
            [image_type] \
            [cloudname] \
            [product['release']] \
            [product['arch']] \
            [machine_type]

        stat['count'] = stat.get('count', 0) + 1

        serial = product['version_name']
        if 'beta' in serial or 'LATEST' in serial:
            continue
        serial = _parse_serial_date_int_from_string(serial)

        current_serial = stat.get('latest_serial')
        if current_serial is None or serial > current_serial:
            stat['latest_serial'] = serial
            stat['age'] = _determine_serial_age(serial)

    return image_statistics


def _determine_serial_age(serial):
    serial_datetime = datetime.datetime.strptime(str(serial), '%Y%m%d')
    return (TODAY - serial_datetime.date()).days


def create_gauges():
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

    return registry, (count_gauge, latest_serial_gauge, latest_serial_age_gauge)


def set_gauges_from_stats(stats, gauges):
    count_gauge, latest_serial_gauge, latest_serial_age_gauge = gauges

    for image_type, clouds in stats.items():
        for cloud_name, releases in clouds.items():
            for release, arches in releases.items():
                for arch, machines in arches.items():

                    count_gauge.labels(
                        image_type, cloud_name, release, arch
                    ).set(sum([s['count'] for s in machines.values()]))

                    serials = [(s.get('latest_serial'), s['age'])
                               for s in machines.values()
                               if s.get('latest_serial')]

                    if serials:
                        serial, age = max(serials, key=lambda v: v[0])
                        latest_serial_gauge.labels(
                            image_type, cloud_name, release
                        ).set(serial)

                        latest_serial_age_gauge.labels(
                            image_type, cloud_name, release
                        ).set(age)

                    if len(machines) > 1:
                        for machine_type, stat in machines.items():
                            cloud_variant = cloud_name + ':' + machine_type

                            # We don't publish image counts per variant ?
                            # count_gauge.labels(
                            #     image_type, cloud_variant, release, arch
                            # ).set(stat['count'])

                            if 'latest_serial' in stat:
                                latest_serial_gauge.labels(
                                    image_type, cloud_variant, release
                                ).set(stat['latest_serial'])

                                latest_serial_age_gauge.labels(
                                    image_type, cloud_variant, release
                                ).set(stat['age'])


def collect(dryrun=False):
    """Push published cloud image counts."""
    registry, gauges = create_gauges()

    mirror = UbuntuCloudImages()

    release_clouds = ifilter('index_path ~ releases') & ifilter(
        'content_id ~ ({})$'.format('|'.join(RELEASE_CLOUD_NAMES)))

    daily_clouds = ifilter('index_path ~ daily') & ifilter(
        'content_id ~ ({})$'.format('|'.join(DAILY_CLOUD_NAMES)))

    interesting_images = (release_clouds | daily_clouds) & \
                         (ifilter('cloudname !=') |
                          ifilter('datatype = image-downloads'))

    images = mirror.get_product_items(ifilter('cloudname !~ ^aws'), interesting_images)
    stats = parse_simplestreams_for_images(images)
    set_gauges_from_stats(stats, gauges)

    # Special hand-holding for AWS

    aws_deprecated = ifilter('release = xenial') & \
                     ifilter('virt ~ ^(hvm|pv)$') & \
                     ifilter('root_store ~ ^(io1|ebs)$')

    aws_images = mirror.get_product_items(ifilter('cloudname ~ ^aws'),
                                          interesting_images & -aws_deprecated)
    aws_stats = parse_simplestreams_for_images(aws_images)
    set_gauges_from_stats(aws_stats, gauges)

    docker_core_serials = get_current_download_serials(DOCKER_CORE_ROOT)

    count_gauge, latest_serial_gauge, latest_serial_age_gauge = gauges

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
