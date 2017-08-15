#!/usr/bin/env python3
"""Submit metrics for Stable Release Update queue related statistics.

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
    """Get the number of UNAPPROVED uploads for proposed for each series."""
    ubuntu = lp.get_ubuntu()
    stable_series = [s for s in ubuntu.series if s.active]
    stable_series.remove(ubuntu.current_series)

    per_series = {}
    for series in stable_series:
        per_series[series.name] = len(series.getPackageUploads(
            status='Unapproved',
            pocket='Proposed'))

    return per_series


def unapproved_sru_ages():
    """Determine age of UNAPPROVED uploads for proposed for each series."""
    from datetime import datetime
    ubuntu = lp.get_ubuntu()
    stable_series = [s for s in ubuntu.series if s.active]
    stable_series.remove(ubuntu.current_series)

    per_series = {}
    for series in stable_series:
        uploads = series.getPackageUploads(status='Unapproved',
                                           pocket='Proposed')
        oldest_age_in_days = 0
        backlog_age = 0
        backlog_count = 0
        today = datetime.today()
        for upload in uploads:
            # the granularity only needs to be in days so tzinfo doesn't need
            # to be accurate
            age_in_days = (today -
                           upload.date_created.replace(tzinfo=None)).days
            if age_in_days > oldest_age_in_days:
                oldest_age_in_days = age_in_days
            # items in the queue for > 10 days have gone through at least a
            # weeks worth of reviewers and should be considered late
            if age_in_days > 10:
                backlog_age += age_in_days - 10
                backlog_count += 1
        per_series[series.name] = {}
        per_series[series.name]['oldest_age_in_days'] = oldest_age_in_days
        per_series[series.name]['ten_day_backlog_count'] = backlog_count
        per_series[series.name]['ten_day_backlog_age'] = backlog_age

    return per_series


def sru_verified_and_ready_count():
    """Get the number -proposed packages that are verified and good to go."""
    # Most of this code is taken from lp:~brian-murray/+junk/bug-agent, just
    # modified to do what we want.
    url = 'http://people.canonical.com/~ubuntu-archive/pending-sru.html'
    report_contents = urllib.request.urlopen(url).read()
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
            failure = cols[0].text
            if ('Failed' in failure or
                    'Dependency wait' in failure or
                    'Cancelled' in failure or
                    'Regression in autopkgtest' in failure):
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


def proposed_package_ages():
    """Categorize and determine age of packages in -proposed."""
    # Most of this code is taken from lp:~brian-murray/+junk/bug-agent, just
    # modified to do what we want.
    url = 'http://people.canonical.com/~ubuntu-archive/pending-sru.html'
    report_contents = urllib.request.urlopen(url).read()
    try:
        soup = BeautifulSoup(report_contents, 'lxml')
    except HTMLParseError:
        logging.error('Error parsing SRU report')
        return

    per_series = {}
    tables = soup.findAll('table')
    for table in tables:
        if not table.has_attr('id'):
            continue

        release = table.previous.previous
        if release == 'Upload queue status at a glance:':
            continue

        per_series[release] = {}
        unverified_backlog_count = 0
        unverified_backlog_age = 0
        verified_backlog_count = 0
        verified_backlog_age = 0
        vfailed_backlog_count = 0
        vfailed_backlog_age = 0
        trs = table.findAll('tr')
        for tag in trs:
            cols = tag.findAll('td')
            length = len(cols)
            if length == 0:
                continue
            failure = cols[0].text
            age_in_days = int(cols[5].string)
            # give the SRU 14 days to be verified
            if age_in_days > 14:
                bugs = cols[4].findChildren('a')
                category = 'unknown'
                # there is a failure so consider it unverified
                if ('Failed' in failure or
                        'Dependency wait' in failure or
                        'Cancelled' in failure or
                        'Regression in autopkgtest' in failure):
                    verified = False
                    category = 'unverified'
                for bug in bugs:
                    # vfailed will overwrite the unverified status of an SRU
                    if 'verificationfailed' in bug['class']:
                        category = 'vfailed'
                        break
                    if 'verified' not in bug['class']:
                        category = 'unverified'
                        break
                    if 'verified' in bug['class']:
                        # if it is unverified for any reason then it can't be
                        # isn't verified i.e. every bug needs verification
                        if category != 'unverified':
                            category = 'verified'
                if category == 'unverified':
                    unverified_backlog_count += 1
                    unverified_backlog_age += age_in_days - 14
                    # print('%s old and unverified' % cols[0].find('a').text)
                elif category == 'verified':
                    verified_backlog_count += 1
                    verified_backlog_age += age_in_days - 14
                elif category == 'vfailed':
                    vfailed_backlog_count += 1
                    vfailed_backlog_age += age_in_days - 14

        per_series[release]['fourteen_day_unverified_backlog_count'] = \
            unverified_backlog_count
        per_series[release]['fourteen_day_unverified_backlog_age'] = \
            unverified_backlog_age
        per_series[release]['fourteen_day_verified_backlog_count'] = \
            verified_backlog_count
        per_series[release]['fourteen_day_verified_backlog_age'] = \
            verified_backlog_age
        per_series[release]['fourteen_day_vfailed_backlog_count'] = \
            vfailed_backlog_count
        per_series[release]['fourteen_day_vfailed_backlog_age'] = \
            vfailed_backlog_age

    return per_series


def collect(dryrun=False):
    """Collect and push SRU-related metrics."""
    sru_queues = sru_queue_count()
    ready_srus = sru_verified_and_ready_count()
    proposed_sru_age_data = proposed_package_ages()
    unapproved_sru_age_data = unapproved_sru_ages()

    q_name = 'Proposed Uploads in the Unapproved Queue per Series'

    print('Number of %s:' % q_name)
    for series, count in sru_queues.items():
        print('%s: %s' % (series, count))

    print('Age in days of oldest %s:' % q_name.replace('Uploads', 'Upload'))
    for series in unapproved_sru_age_data:
        print('%s: %s' %
              (series, unapproved_sru_age_data[series]['oldest_age_in_days']))

    print('Backlog age in days of %s:' % q_name)
    for series in unapproved_sru_age_data:
        print('%s: %s' %
              (series, unapproved_sru_age_data[series]['ten_day_backlog_age']))

    print('Number of backlogged %s:' % q_name)
    for series in unapproved_sru_age_data:
        print('%s: %s' %
              (series,
               unapproved_sru_age_data[series]['ten_day_backlog_count']))

    topic = 'Updates in Proposed per Series'

    print('Number of Publishable %s:' % topic)
    for series, count in ready_srus.items():
        print('%s: %s' % (series, count))

    for category in ('unverified', 'verified', 'vfailed'):
        print('Number of backlogged %s %s:' % (category, topic))
        for series in proposed_sru_age_data:
            print('%s: %s' %
                  (series,
                   proposed_sru_age_data[series]
                   ['fourteen_day_%s_backlog_count' % category]))

        print('Backlog age in days of %s %s:' % (category, topic))
        for series in proposed_sru_age_data:
            print('%s: %s' %
                  (series,
                   proposed_sru_age_data[series]
                   ['fourteen_day_%s_backlog_age' % category]))

    if not dryrun:
        print('Pushing data...')
        registry = CollectorRegistry()

        gauge = Gauge(
            'distro_sru_unapproved_proposed_count',
            'Number of %s' % q_name,
            ['series'],
            registry=registry)
        for series, count in sru_queues.items():
            gauge.labels(series).set(count)

        gauge = Gauge(
            'distro_sru_unapproved_proposed_oldest_age',
            'Age in days of oldest %s' % q_name.replace('Uploads', 'Upload'),
            ['series'],
            registry=registry)
        for series in unapproved_sru_age_data:
            gauge.labels(series).set(
                unapproved_sru_age_data[series]['oldest_age_in_days'])

        gauge = Gauge(
            'distro_sru_unapproved_proposed_ten_day_backlog_age',
            'Backlog age in days of %s' % q_name,
            ['series'],
            registry=registry)
        for series in unapproved_sru_age_data:
            gauge.labels(series).set(
                unapproved_sru_age_data[series]['ten_day_backlog_age'])

        gauge = Gauge(
            'distro_sru_unapproved_proposed_ten_day_backlog_count',
            'Number of backlogged %s' % q_name,
            ['series'],
            registry=registry)
        for series in unapproved_sru_age_data:
            gauge.labels(series).set(
                unapproved_sru_age_data[series]['ten_day_backlog_count'])

        gauge = Gauge(
            'distro_sru_verified_and_ready_count',
            'Number of Publishable Updates in Proposed per Series',
            ['series'],
            registry=registry)
        for series, count in ready_srus.items():
            gauge.labels(series).set(count)

        for cat in ('unverified', 'verified', 'vfailed'):
            gauge = Gauge(
                'distro_sru_%s_proposed_fourteen_day_backlog_age' % cat,
                'Backlog age in days of %s %s' % (cat, topic),
                ['series'],
                registry=registry)
            for series in proposed_sru_age_data:
                gauge.labels(series).set(
                    proposed_sru_age_data[series]
                    ['fourteen_day_%s_backlog_age' % cat])

            gauge = Gauge(
                'distro_sru_%s_proposed_fourteen_day_backlog_count' % cat,
                'Number of backlogged %s %s' % (cat, topic),
                ['series'],
                registry=registry)
            for series in proposed_sru_age_data:
                gauge.labels(series).set(
                    proposed_sru_age_data[series]
                    ['fourteen_day_%s_backlog_count' % cat])

        util.push2gateway('triage', registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
