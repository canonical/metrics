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


def collect(dryrun=False):
    """Submit data to Push Gateway."""
    triage = lp.get_team_daily_triage_count(team='ubuntu-server',
                                            distro='Ubuntu',
                                            blacklist=BLACKLIST)
    backlog = lp.get_team_backlog_count(team='ubuntu-server',
                                        distro='Ubuntu')

    print('Backlog Total: %s' % backlog)
    print('Triage Total: %s' % triage)

    if not dryrun:
        print('Pushing data...')
        registry = CollectorRegistry()

        Gauge('server_triage_backlog_total',
              'Bugs in team backlog',
              None,
              registry=registry).set(backlog)

        Gauge('server_triage_daily_triage_total',
              'Bugs to review daily',
              None,
              registry=registry).set(triage)

        util.push2gateway('triage', registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.dryrun)
