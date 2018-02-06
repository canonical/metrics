#!/usr/bin/env python3
"""Generate published cloud image sizes.

Copyright 2018 Canonical Ltd.
Brian Murray <brian.murray@canonical.com>
"""
import argparse
import json
import subprocess

from prometheus_client import CollectorRegistry, Gauge

from metrics.helpers import util

DAILY_URL = ('http://cloud-images.ubuntu.com/daily/streams/v1'
             '/com.ubuntu.cloud:daily:download.json')
IMAGE_TYPE = 'daily'
IMAGE_FORMAT = 'disk1.img'


def parse_simplestreams_for_images():
    """
    Use sstream-query to fetch supported image information.

    This returns a dictionary of
    {release: {arch: {'size': size_of_image}, {'version': version_name}}}.
    """
    url = DAILY_URL
    output = subprocess.check_output(['sstream-query', '--json', url])
    image_sizes = {}
    for product_dict in json.loads(output.decode('utf-8')):
        if product_dict['supported'] == 'False':
            continue
        if product_dict['ftype'] != IMAGE_FORMAT:
            continue
        release = product_dict['release']
        if release not in image_sizes:
            image_sizes[release] = {}
        arch = product_dict['arch']
        if arch not in image_sizes[release]:
            image_sizes[release][arch] = {}
        if 'version' in image_sizes[release][arch]:
            version = image_sizes[release][arch]['version']
            if version > product_dict['version_name']:
                continue
        image_sizes[release][arch]['version'] = product_dict['version_name']
        image_sizes[release][arch]['size'] = product_dict['size']
    return image_sizes


def collect(dryrun=False):
    """Push published cloud image sizes."""
    registry = CollectorRegistry()
    size_gauge = Gauge('foundations_cloud_images_sizes',
                       'The size of cloud images',
                       ['image_type', 'format', 'release', 'arch'],
                       registry=registry)
    print('Getting size of daily images')
    image_sizes = parse_simplestreams_for_images()
    for release in image_sizes:
        for arch in image_sizes[release]:
            size = image_sizes[release][arch]['size']
            print('Found {} image {} of size {} for {} {}'.format(
                IMAGE_TYPE, IMAGE_FORMAT, size, release, arch))
            size_gauge.labels(
                IMAGE_TYPE, IMAGE_FORMAT, release, arch).set(size)

    if not dryrun:
        print('Pushing data...')
        util.push2gateway('cloud-image-size-foundations', registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
