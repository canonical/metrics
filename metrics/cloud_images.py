#!/usr/bin/env python3
"""Generate published cloud image counts.

Copyright 2017 Canonical Ltd.
Daniel Watkins <daniel.watkins@canonical.com>
"""
import argparse
import datetime
import logging
import sys
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

logger = logging.getLogger('cloud_images')

import os.path
import re
from collections import defaultdict

import distro_info  # pylint: disable=wrong-import-order
import requests
from prometheus_client import CollectorRegistry, Gauge
from metrics.helpers.sstreams import UbuntuCloudImages, ifilter
from metrics.helpers import util


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
    for release in distro_info.UbuntuDistroInfo().supported():
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


def _update_stat_entry_item(stat_lvl, serial):
    stat_lvl['count'] = stat_lvl.get('count', 0) + 1

    if 'beta' in serial or 'LATEST' in serial:
        return

    serial = _parse_serial_date_int_from_string(serial)

    current_serial = stat_lvl.get('latest_serial')
    if current_serial is None or serial > current_serial:
        stat_lvl['latest_serial'] = serial
        stat_lvl['age'] = _determine_serial_age(serial)


def parse_simplestreams_for_images(images):
    """
    Use sstream-query to fetch supported image information.

    For non-AWS clouds, this returns a tuple of
    ({release: {arch: count_of_images}}, {release: latest_serial}).  For
    AWS clouds, the first element of the tuple remains the same, but the
    second is {release: {virt_storage: {latest_serial}}}.
    """
    recursive_dict = lambda: defaultdict(recursive_dict)
    stats = recursive_dict()

    for image in images:
        image_type = INDEX_PATH_TO_IMAGE_TYPE[image['index_path']]
        cloudname = image.get('cloudname')
        if not cloudname and image['datatype'] == 'image-downloads':
            cloudname = 'download'

        release = image.get('release') or image.get('version', 'unknown')
        serial = image.get('version_name', 'LATEST')
        arch = image.get('arch', 'noarch')
        machine_type = '-'.join([image[f] for f in MACHINE_TYPE_FIELDS
                                 if f in image])

        # base stat entries
        stat_entry = stats[image_type][cloudname][release]
        _update_stat_entry_item(stat_entry, serial)

        # serials also make sense per machine type
        machine_lvl = stat_entry['by-machine'][machine_type]
        _update_stat_entry_item(machine_lvl, serial)

        # counts are tracked per arch, w/ no regard for machine type
        arch_lvl = stat_entry['by-arch'][arch]
        _update_stat_entry_item(arch_lvl, serial)

    return stats


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

    # <stat_entry> looks like: {lastest_serial: 20180901, age: 866, count: 1}
    # stats look like:
    # daily.aws.vivid - <stat_entry>
    #               | - [by-machine] = { pv-instance: <stat_entry> }
    #                \- [by-arch] = { amd64: <stat_entry> }

    for image_type, clouds in stats.items():
        for cloud_name, releases in clouds.items():
            for release, stat_entry in releases.items():

                for arch, stat in stat_entry['by-arch'].items():
                    count_gauge.labels(
                        image_type, cloud_name, release, arch
                    ).set(stat['count'])

                if 'latest_serial' in stat_entry:
                    latest_serial_gauge.labels(
                        image_type, cloud_name, release
                    ).set(stat_entry['latest_serial'])

                    latest_serial_age_gauge.labels(
                        image_type, cloud_name, release
                    ).set(stat_entry['age'])

                if len(stat_entry['by-machine']) > 1:
                    for machine_type, stat in stat_entry['by-machine'].items():
                        if 'latest_serial' not in stat:
                            continue

                        cloud_variant = cloud_name + ':' + machine_type
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

    release_clouds = ifilter('index_path = releases') & ifilter(
        'content_id ~ ({})$'.format('|'.join(RELEASE_CLOUD_NAMES)))

    daily_clouds = ifilter('index_path = daily') & ifilter(
        'content_id ~ ({})$'.format('|'.join(DAILY_CLOUD_NAMES)))

    interesting_images = (release_clouds | daily_clouds) & \
                         (ifilter('cloudname !=') |
                          ifilter('datatype = image-downloads'))
    aws_clouds = ifilter('cloudname ~ ^aws')

    print('Finding serials for non-aws clouds...')
    images = mirror.get_product_items(-aws_clouds, interesting_images)
    stats = parse_simplestreams_for_images(images)
    set_gauges_from_stats(stats, gauges)

    print('Finding serials for AWS clouds...')
    aws_deprecated = ifilter('release = xenial') & \
                     ifilter('virt ~ ^(hvm|pv)$') & \
                     ifilter('root_store ~ ^(io1|ebs)$')

    aws_images = mirror.get_product_items(aws_clouds,
                                          interesting_images & -aws_deprecated)
    aws_stats = parse_simplestreams_for_images(aws_images)
    set_gauges_from_stats(aws_stats, gauges)

    print('Finding serials for docker-core...')
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
    else:
        from prometheus_client import generate_latest
        print(generate_latest(registry).decode('utf-8'))


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()

    collect(ARGS.dryrun)
