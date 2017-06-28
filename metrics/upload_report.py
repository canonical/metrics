#!/usr/bin/python3
"""Determine uploads into development release and SRUs.

Copyright 2017 Canonical Ltd.
Robbie Basak <robie.basak@canonical.com>
Joshua Powers <josh.powers@canonical.com>
"""
from functools import lru_cache
import itertools
import sys

import launchpadlib.launchpad


@lru_cache()
def series_name(launchpad, series_link):
    """Translate series link to a name."""
    return launchpad.load(series_link).name


@lru_cache()
def person_name(launchpad, person_link):
    """Translate name link to a name."""
    if person_link:
        return launchpad.load(person_link).name
    return None


def generate_uploads(start_date):
    """Determine uploads from a particular date."""
    launchpad = launchpadlib.launchpad.Launchpad.login_with(
        'ubuntu-server upload report',
        'production',
        version='devel',
    )

    packages = [
        p.name
        for p in launchpad.people['ubuntu-server'].getBugSubscriberPackages()
    ]

    ubuntu = launchpad.distributions['ubuntu']
    devels = ubuntu.getDevelopmentSeries()
    assert len(devels) == 1
    devel = devels[0].name
    archive = ubuntu.main_archive

    for package in packages:
        spphs = archive.getPublishedSources(
            created_since_date=start_date,
            order_by_date=True,  # essential ordering for migration detection
            source_name=package,
            exact_match=True,
        )
        migrated_versions = set()
        for spph in spphs:
            report_entry = {
                'package': spph.source_package_name,
                'version': spph.source_package_version,
                'series': series_name(launchpad, spph.distro_series_link),
                'signer': person_name(launchpad, spph.package_signer_link),
                'sponsor': person_name(launchpad, spph.sponsor_link),
                'pocket': spph.pocket,
                'created': spph.date_created,
            }
            if report_entry['series'] == devel:
                if report_entry['pocket'] == 'Release':
                    migrated_versions.add(report_entry['version'])
                    continue  # ignore migration from an upload perspective
                elif report_entry['pocket'] == 'Proposed':
                    report_entry['migrated'] = (
                        report_entry['version'] in migrated_versions
                    )
                report_entry['category'] = 'Development release'
            else:
                report_entry['category'] = 'SRU'

            if report_entry['sponsor'] == 'ubuntu-archive-robot':
                continue  # skip syncs
            yield report_entry


def main():
    """Get report and print."""
    report = sorted(
        generate_uploads(sys.argv[1]),
        key=lambda r: r['category']
    )

    grouped_report = itertools.groupby(
        report,
        key=lambda r: r['category'],
    )

    for category, entries in grouped_report:
        count = 0
        print('Category: %s' % category)
        for entry in entries:
            count += 1
            if category == 'SRU':
                print('%s, %s, %s, %s' % (entry['package'], entry['series'],
                                          entry['version'], entry['signer']))
            else:
                print('%s, %s, %s' % (entry['package'], entry['version'],
                                      entry['signer']))

        print('Total: %s' % count)
        print()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Please enter a date in the format YYYY-MM-DD')
        sys.exit(1)

    main()
