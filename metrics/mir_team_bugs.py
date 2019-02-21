#!/usr/bin/env python3
"""Submit metrics for MIR Team queue sizes.

Copyright 2019 Canonical Ltd.
Mathieu Trudel-Lapierre <mathieu.trudel-lapierre@canonical.com>

Based on triage.py:
Joshua Powers <josh.powers@canonical.com>
"""
import argparse

from metrics.helpers import lp
from metrics.helpers import util


def collect(dryrun=False):
    """Submit data to Push Gateway."""
    unassigned = lp.get_team_subscribed_unassigned_bugs(team='ubuntu-mir',
                                                        distro='Ubuntu')
    incomplete = lp.get_team_subscribed_incomplete_bugs(team='ubuntu-mir',
                                                        distro='Ubuntu')
    pending = lp.get_mirs_in_review()
    security = lp.get_mirs_in_security_review()
    approved = lp.get_approved_mirs()

    print('Unassigned Total: %s' % unassigned)
    print('Incomplete Total: %s' % incomplete)
    print('Pending Total: %s' % pending)
    print('Security Total: %s' % security)
    print('Approved Total: %s' % approved)

    if not dryrun:
        print('Pushing data...')

        data = [
            {
                'measurement': 'distro_mir_team_bugs',
                'fields': {
                    'unassigned': unassigned,
                    'incomplete': incomplete,
                    'pending': pending,
                    'approved': approved,
                }
            }
        ]

        util.influxdb_insert(data)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
