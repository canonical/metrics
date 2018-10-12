#!/usr/bin/env python3
"""Generate published cloud image counts.

Copyright 2017 Canonical Ltd.
Daniel Watkins <daniel.watkins@canonical.com>
"""
import argparse
import datetime
import os.path
import re
from collections import defaultdict
import distro_info  # pylint: disable=wrong-import-order
import requests

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
    <download_root>/<suite>/current/unpacked/build-info.txt for supported
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


def update_stat_entry_item(stat_lvl, serial):
    """
    Track a simplestream item metrics in the stat_lvl dictionary.

    :param stat_lvl: the stat_entry dict, as per parse_simplestreams_for_images
    :param serial: item serial string (e.g '20181011.1')
    :return:
    """
    stat_lvl['count'] = stat_lvl.get('count', 0) + 1

    if 'beta' in serial or 'LATEST' in serial:
        return

    serial = _parse_serial_date_int_from_string(serial)

    current_serial = stat_lvl.get('latest_serial')
    if current_serial is None or serial > current_serial:
        stat_lvl['latest_serial'] = serial
        stat_lvl['age'] = _determine_serial_age(serial)


def recursive_defaultdict():
    """
    Produce a recursive defaultdict.

    :return: defaultdict of defaultdicts
    """
    return defaultdict(recursive_defaultdict)


def parse_simplestreams_for_images(images):
    """
    Generate metrics dict, describing `images` simplestream items collection.

    :return: a dict that is structured like this:
    daily.aws.vivid - <stat_entry>
                  | - [by-machine] = { pv-instance: <stat_entry> }
                  | - [by-arch] = { amd64: <stat_entry> }
    where <stat_entry> looks like:
        {lastest_serial: 20180901, age: 866, count: 1}
    """
    stats = recursive_defaultdict()

    for image in images:
        # simplestreams items are all of images ever published
        # we create a 3-level deep dict to keep counters and latest_serials
        # for them, to find out what, and how old are the latest serials

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
        update_stat_entry_item(stat_entry, serial)

        # Some metrics we only track per machine type or arch,
        # that is why they are kept as separate <stat_item> records

        # serials make sense per machine type
        machine_lvl = stat_entry['by-machine'][machine_type]
        update_stat_entry_item(machine_lvl, serial)

        # counts are tracked per arch, w/ no regard for machine type
        arch_lvl = stat_entry['by-arch'][arch]
        update_stat_entry_item(arch_lvl, serial)

    return stats


def _determine_serial_age(serial):
    serial_datetime = datetime.datetime.strptime(str(serial), '%Y%m%d')
    return (TODAY - serial_datetime.date()).days


def _emit_metric(measurement, value, **kwargs):
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


def gen_metrics_from_stats(stats):
    """
    Generate influxdb-metric entries from the metrics dict.

    :param stats: a dict as returned by parse_simplestreams_for_images
    """
    for image_type, clouds in stats.items():
        for cloud_name, releases in clouds.items():
            for release, stat_entry in releases.items():
                yield from gen_metrics_from_stat_item(
                    image_type, cloud_name, release, stat_entry)


def gen_metrics_from_stat_item(image_type, cloud_name, release, stat_entry):
    """
    Generate <image_type>.<cloud_name>.<release> stats record.

    :param image_type: daily/release
    :param cloud_name: aws/azure/download, etc.
    :param release: artful/bionic, etc.
    :param stat_entry: a release-level accumulated <stat_entry>,
    that has 'by-machine' and 'by-arch' records, containing <stat_entry> under
    respective keys.
    :return: InfluxDB metric generator
    """
    tags = dict(image_type=image_type, cloud=cloud_name, release=release)

    for arch, stat in stat_entry['by-arch'].items():
        yield _emit_metric(
            'published',
            stat['count'],
            arch=arch,
            **tags
        )

    # Note: some machine-types can fail to publish, the oldest machine type
    # should be reported to help catch those occurences.
    oldest_machine = max(stat_entry['by-machine'].values(),
                         key=lambda i: i.get('age', 0))
    if 'latest_serial' in oldest_machine:
        yield _emit_metric(
            'current_serial', oldest_machine['latest_serial'], **tags)
        yield _emit_metric(
            'current_serial_age', oldest_machine['age'], **tags)

    if len(stat_entry['by-machine']) > 1:
        for machine_type, stat in stat_entry['by-machine'].items():
            if 'latest_serial' not in stat:
                continue

            tags['cloud'] = cloud_name + ':' + machine_type

            yield _emit_metric('current_serial', stat['latest_serial'], **tags)
            yield _emit_metric('current_serial_age', stat['age'], **tags)


def collect(dryrun=False):
    """Push published cloud image counts."""
    metrics = []

    interesting_images = filter_interesting_images()
    aws_clouds = ifilter('cloudname ~ ^aws')
    not_aws_clouds = -aws_clouds

    print('Finding serials for non-aws clouds...')
    metrics += collect_metrics(not_aws_clouds, interesting_images)

    print('Finding serials for AWS clouds...')
    # These virt/storage combinations were present in early xenial development
    # dailies, but were dropped before release.
    aws_deprecated = (ifilter('release = xenial') &
                      ifilter('virt ~ ^(hvm|pv)$') &
                      ifilter('root_store ~ ^(io1|ebs)$'))

    metrics += collect_metrics(aws_clouds,
                               interesting_images & -aws_deprecated)

    print('Finding serials for docker-core...')
    docker_core_serials = get_current_download_serials(DOCKER_CORE_ROOT)
    for release, serial in docker_core_serials.items():
        age = _determine_serial_age(serial)
        print('Found {} latest serial: {} ({} days old)'.format(
            release, serial, age))

        tags = dict(image_type='daily', cloud='docker-core', release=release)
        metrics += [
            _emit_metric('current_serial', serial, **tags),
            _emit_metric('current_serial_age', age, **tags)
        ]

    if not dryrun:
        print('Pushing data...')
        util.influxdb_insert(metrics)
    else:
        import pprint
        pprint.pprint(metrics)


def collect_metrics(stream_filter, item_filter):
    """
    Generate metrics for images in ubuntu simplestreams.

    Use UbuntuCloudImages to collect counts, latest_serial and it's age for
    every permutation of image type, cloud name, release, arch and machine type
    and create metric events for InfluxDB.

    :param stream_filter: a SimpleStreams filter for stream feeds
    :param item_filter: a SimpleStreams filter for image items
    """
    images = UbuntuCloudImages().get_product_items(stream_filter, item_filter)
    stats = parse_simplestreams_for_images(images)
    return list(gen_metrics_from_stats(stats))


def filter_interesting_images():
    """
    Produce a nested filter that considers the clouds that are part of KPIs.

    :return: SimpleStreams filter object
    """
    release_clouds = ifilter('index_path = releases') & ifilter(
        'content_id ~ ({})$'.format('|'.join(RELEASE_CLOUD_NAMES)))

    daily_clouds = ifilter('index_path = daily') & ifilter(
        'content_id ~ ({})$'.format('|'.join(DAILY_CLOUD_NAMES)))

    interesting_images = (release_clouds | daily_clouds) & \
                         (ifilter('cloudname !=') |
                          ifilter('datatype = image-downloads'))
    return interesting_images


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()

    collect(ARGS.dryrun)
