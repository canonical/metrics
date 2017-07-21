#!/usr/bin/env python3
"""Submit metrics for Ubuntu Server bug triage.

Copyright 2017 Canonical Ltd.
Joshua Powers <josh.powers@canonical.com>
"""
import argparse

from prometheus_client import CollectorRegistry, Gauge

from metrics.helpers import lp
from metrics.helpers import util

BLACKLIST = {
    'cloud-init',
    'curtin',
    'juju',
    'juju-core',
    'lxc',
    'lxd',
    'maas',
}


def collect(team_name, dryrun=False):
    """Submit data to Push Gateway."""
    lp_team_name = util.get_launchpad_team_name(team_name)
    triage = lp.get_team_daily_triage_count(team=lp_team_name,
                                            distro='Ubuntu',
                                            blacklist=BLACKLIST)
    backlog = lp.get_team_backlog_count(team=lp_team_name,
                                        distro='Ubuntu')

    print('Backlog Total: %s' % backlog)
    print('Triage Total: %s' % triage)

    if not dryrun:
        print('Pushing data...')
        registry = CollectorRegistry()

        Gauge('{}_triage_backlog_total'.format(team_name),
              'Bugs in team backlog',
              None,
              registry=registry).set(backlog)

        Gauge('{}_triage_daily_triage_total'.format(team_name),
              'Bugs to review daily',
              None,
              registry=registry).set(triage)

        util.push2gateway('%s-triage' % team_name, registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('team_name', help='team name', default='server')
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.team_name, ARGS.dryrun)
