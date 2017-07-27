#!/usr/bin/env python3
"""Submit metrics for various SRU related statistics.

Copyright 2017 Canonical Ltd.
Łukasz 'sil2100' Zemczak <lukasz.zemczak@canonical.com>
"""

import argparse
import logging
import urllib.request

from bs4 import BeautifulSoup
from prometheus_client import CollectorRegistry, Gauge

try:
    from html.parser import HTMLParseError
except ImportError as exception:
    # Taken from bs4 code.
    class HTMLParseError(Exception):
        """Dummy exception."""

        pass

from metrics.helpers import lp
from metrics.helpers import util


def sru_queue_count():
    """Get the number of UNAPPROVED uploads for each series."""
    ubuntu = lp.get_ubuntu()
    stable_series = [s for s in ubuntu.series if s.active]
    stable_series.remove(ubuntu.current_series)

    per_series = {}
    for series in stable_series:
        per_series[series.name] = len(series.getPackageUploads(
            status='Unapproved',
            pocket='Proposed',
            archive=ubuntu.main_archive))

    return per_series


def sru_ready_for_updates_count():
    """Get the number of verified -proposed packages."""
    # Most of this code is taken from lp:~brian-murray/+junk/bug-agent, just
    # modified to do what we want.
    url = 'http://people.canonical.com/~ubuntu-archive/pending-sru.html'
    report_page = urllib.request.urlopen(url)
    report_contents = report_page.read()
    try:
        soup = BeautifulSoup(report_contents, 'lxml')
    except HTMLParseError:
        logging.error('Error parsing SRU report')
        return

    ready_srus = {}
    tables = soup.findAll('table')
    for table in tables:
        if not table.has_attr('id'):
            continue

        release = table.previous.previous
        if release == 'Upload queue status at a glance:':
            continue

        ready_srus[release] = 0
        trs = table.findAll('tr')
        for tag in trs:
            cols = tag.findAll('td')
            length = len(cols)
            if length == 0:
                continue
            if int(cols[5].string) >= 7:
                bugs = cols[4].findChildren('a')
                verified = True
                for bug in bugs:
                    if 'verified' not in bug['class']:
                        verified = False
                        break
                if verified:
                    ready_srus[release] += 1

    return ready_srus


def collect(dryrun=False):
    """Collect and push SRU-related metrics."""
    sru_queues = sru_queue_count()
    ready_srus = sru_ready_for_updates_count()

    print('Number of Uploads in the Unapproved Queue per Series:')
    for series, count in sru_queues.items():
        print('%s: %s' % (series, count))

    print('Number of Publishable Updates in Proposed per Series:')
    for series, count in ready_srus.items():
        print('%s: %s' % (series, count))

    if not dryrun:
        print('Pushing data...')
        registry = CollectorRegistry()

        gauge = Gauge('foundations_sru_unapproved_count',
                      'Number of Uploads in the Unapproved Queue per Series',
                      ['series'],
                      registry=registry)
        for series, count in sru_queues.items():
            gauge.labels(series).set(count)

        gauge = Gauge('foundations_sru_verified_count',
                      'Number of Publishable Updates in Proposed per Series',
                      ['series'],
                      registry=registry)
        for series, count in ready_srus.items():
            gauge.labels(series).set(count)

        util.push2gateway('triage', registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
