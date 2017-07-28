#!/usr/bin/env python3
"""Submit metrics for rls-* tagged bugs.

Copyright 2017 Canonical Ltd.
Daniel Watkins <daniel.watkins@canonical.com>
"""
import argparse
import re
import sys

import requests
from prometheus_client import CollectorRegistry, Gauge

from metrics.helpers import util


REPORT_PARENT = 'http://reqorts.qa.ubuntu.com/reports/rls-mgr/'
REPORT_URL_PATTERN = (
    REPORT_PARENT + 'rls-{release_prefix}-{tag}-bug-tasks.html')
TAGS = ['incoming', 'tracking']


def _get_latest_release_prefix():
    response = requests.get(REPORT_PARENT)
    release_prefixes = set(re.findall(r'rls-([a-z]+)-incoming', response.text))
    recent_release_prefixes = (
        prefix for prefix in release_prefixes if len(prefix) == 2)
    return sorted(recent_release_prefixes)[-1]


def _get_tag_counts(release_prefix, tag):
    response = requests.get(REPORT_URL_PATTERN.format(
        release_prefix=release_prefix, tag=tag))
    tag_pairs = re.findall(r'<span id="(.+)-total">(\d+)</span>',
                           response.text)
    if len(tag_pairs) == 0:
        print('No tag counts found; report may be broken. Exiting now to'
              ' avoid pushing invalid data.')
        sys.exit(1)
    return dict(tag_pairs)


def collect(dryrun=False):
    """Submit data to Push Gateway."""
    latest_release_prefix = _get_latest_release_prefix()
    counts = {}
    for tag in TAGS:
        counts[tag] = _get_tag_counts(latest_release_prefix, tag)
    print(counts)
    if not dryrun:
        print('Pushing data...')
        registry = CollectorRegistry()
        gauge = Gauge(
            'rls_bug_tasks', '', ['tag', 'team_name'],
            registry=registry)
        for tag in TAGS:
            for team_name in counts[tag]:
                gauge.labels(tag, team_name).set(counts[tag][team_name])

        util.push2gateway('rls_bug_tasks', registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
