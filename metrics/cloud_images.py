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

import distro_info  # pylint: disable=wrong-import-order
import requests

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
AWS_VIRT_STORE_SKIPS = {
    # These virt/storage combinations were present in early xenial development
    # dailies, but were dropped before release.
    'xenial': ['hvm-ebs', 'hvm-io1', 'pv-ebs', 'pv-io1'],
}


def _parse_serial_date_int_from_string(serial_str):
    match = re.match(r'\d+', serial_str)
    if match is None:
        raise Exception('No serial found in {}'.format(serial_str))
    return int(match.group(0))


def _gen_influx_metric(measurement, value, **kwargs):
    """
    Generate InfluxDB-shaped datapoint dictionary.

    :param measurement: measurement suffix
    :param value: measurement value
    :param kwargs: dict of tags to associate with the measurement
    :return: dict, influx-db shaped datapoint
    """
    tags = {k: None for k in ['image_type', 'cloud', 'release']}
    tags.update({'job': 'cloud-image-count-foundations'})
    tags.update(kwargs)

    return {
        'time': datetime.datetime.utcnow(),
        'measurement': 'foundations_cloud_images_'+measurement,
        'tags': tags,
        'fields': {'value': value},
    }


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
    """
    Use sstream-query to fetch supported image information.

    For non-AWS clouds, this returns a tuple of
    ({release: {arch: count_of_images}}, {release: latest_serial}).  For
    AWS clouds, the first element of the tuple remains the same, but the
    second is {release: {virt_storage: {latest_serial}}}.
    """
    url = URL_PATTERNS[image_type].format(cloud_name=cloud_name)
    output = subprocess.check_output(['sstream-query', '--json', url])
    image_counts = defaultdict(lambda: defaultdict(int))
    if cloud_name.startswith('aws'):
        # For AWS, we capture latest serial by virt/root store
        latest_serials = defaultdict(lambda: defaultdict(int))
    else:
        latest_serials = defaultdict(int)
    for product_dict in json.loads(output.decode('utf-8')):
        release = product_dict['release']
        image_counts[release][product_dict['arch']] += 1
        serial = product_dict['version_name']
        if 'beta' in serial or 'LATEST' in serial:
            continue
        serial = _parse_serial_date_int_from_string(serial)
        if cloud_name.startswith('aws'):
            virt_storage = '-'.join(
                [product_dict['virt'], product_dict['root_store']])
            if serial > latest_serials[release][virt_storage]:
                latest_serials[release][virt_storage] = serial
        else:
            if serial > latest_serials[release]:
                latest_serials[release] = serial
    return image_counts, latest_serials


def _determine_serial_age(serial):
    serial_datetime = datetime.datetime.strptime(str(serial), '%Y%m%d')
    return (TODAY - serial_datetime.date()).days


def do_aws_specific_collection(cloud_name, image_type, metrics_collection):
    """
    Report AWS-specific metrics and return generic cloud data.

    This returns the non-AWS-specific version of
    parse_simplestreams_for_images' return tuples.
    """
    image_counts, aws_latest_serials = parse_simplestreams_for_images(
        cloud_name, image_type)
    latest_serials = {}
    for release in aws_latest_serials:
        # Some virt/storage combinations should be ignored, so we filter those
        # out before we do anything else
        aws_latest_serials[release] = {
            k: v for k, v in aws_latest_serials[release].items()
            if k not in AWS_VIRT_STORE_SKIPS.get(release, [])}
        # aws_latest_serials contains an entry for each virt/storage combo; we
        # want to use the oldest as the main cloud entry
        latest_serials[release] = min(aws_latest_serials[release].values())
        for virt_store in aws_latest_serials[release]:
            aws_cloud_name = '{}:{}'.format(cloud_name, virt_store)
            serial = aws_latest_serials[release][virt_store]
            age = _determine_serial_age(serial)

            tags = dict(image_type=image_type, cloud=aws_cloud_name,
                        release=release)
            metrics_collection.append(
                _gen_influx_metric('current_serial', serial, **tags))
            metrics_collection.append(
                _gen_influx_metric('current_serial_age', age, **tags))

    return image_counts, latest_serials


def collect(dryrun=False):
    """Push published cloud image counts."""
    metrics_collection = []

    for image_type in ['daily', 'release']:
        for cloud_name in CLOUD_NAMES[image_type]:
            print('Counting {} images for {}...'.format(image_type,
                                                        cloud_name))
            if 'aws' in cloud_name:
                image_counts, latest_serials = do_aws_specific_collection(
                    cloud_name, image_type, metrics_collection)
            else:
                image_counts, latest_serials = parse_simplestreams_for_images(
                    cloud_name, image_type)
            for release in image_counts:
                for arch in image_counts[release]:
                    count = image_counts[release][arch]
                    print('Found {} {} images for {} {} {}'.format(
                        count, image_type, cloud_name, release, arch))

                    metrics_collection.append(_gen_influx_metric(
                        'published',
                        count,
                        image_type=image_type,
                        cloud=cloud_name,
                        release=release,
                        arch=arch
                    ))

            for release in latest_serials:
                serial = latest_serials[release]
                age = _determine_serial_age(serial)

                tags = dict(image_type=image_type, cloud=cloud_name,
                            release=release)
                metrics_collection.append(
                    _gen_influx_metric('current_serial', serial, **tags))
                metrics_collection.append(
                    _gen_influx_metric('current_serial_age', age, **tags))

            if not dryrun:
                print('Pushing data...')
                util.influxdb_insert(metrics_collection)
            else:
                import pprint
                pprint.pprint(metrics_collection)
            metrics_collection = []

    print('Finding serials for docker-core...')
    docker_core_serials = get_current_download_serials(DOCKER_CORE_ROOT)
    for release, serial in docker_core_serials.items():
        age = _determine_serial_age(serial)
        print('Found {} latest serial: {} ({} days old)'.format(
            release, serial, age))

        tags = dict(image_type='daily', cloud='docker-core', release=release)
        metrics_collection.append(
            _gen_influx_metric('current_serial', serial, **tags))
        metrics_collection.append(
            _gen_influx_metric('current_serial_age', age, **tags))

    if not dryrun:
        print('Pushing data...')
        util.influxdb_insert(metrics_collection)
    else:
        import pprint
        pprint.pprint(metrics_collection)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
