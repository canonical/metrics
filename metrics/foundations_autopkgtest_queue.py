#!/usr/bin/env python3
"""Submit metrics regarding queue depth for autopkgtest service.

Copyright 2017 Canonical Ltd.
Brian Murray <brian@canonical.com>
"""

import argparse

from prometheus_client import CollectorRegistry, Gauge

from metrics.helpers import util


def get_queue_data():
    """Download queue url and return json data."""
    queue_url = 'http://autopkgtest.ubuntu.com/queues.json'
    queue_json = util.get_json_from_url(queue_url)
    return queue_json


def collect(queue_name, dryrun=False):
    """Collect and push autopkgtest queue depth metrics."""
    queue_details = QUEUES_JSON[queue_name]

    for release in queue_details:
        for arch in queue_details[release]:
            count = len(queue_details[release][arch])
            print('%s %s: %i' % (release.title(), arch, count))

    if not dryrun:
        print('Pushing data...')
        registry = CollectorRegistry()

        for release in queue_details:
            for arch in queue_details[release]:
                count = len(queue_details[release][arch])
                Gauge('autopkgtest_queue_size_%s_%s_%s' %
                      (queue_name, release, arch),
                      "Autopkgtest queue size",
                      None,
                      registry=registry).set(count)

        util.push2gateway('foundations-autopkgtest', registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    PARSER.add_argument('--queues', nargs='+',
                        help='Queue(s) to use', required=True)
    ARGS = PARSER.parse_args()

    QUEUES_JSON = get_queue_data()
    print("Quantity of test requests in queue:")
    for queue in ARGS.queues:
        # check if its a vaild queue name
        if queue not in QUEUES_JSON.keys():
            print('%s is not a valid queue name.' % queue)
            continue
        print("\n%s" % queue)
        print("-"*(len(queue)))
        collect(queue, ARGS.dryrun)
