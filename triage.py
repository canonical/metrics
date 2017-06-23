#!/usr/bin/env python3
"""Submit metrics for Ubuntu Server bug triage.

Copyright 2017 Canonical Ltd.
Joshua Powers <josh.powers@canonical.com>
"""
from prometheus_client import CollectorRegistry, Gauge

import liblaunchpad as llp
import libgateway as lgw

BLACKLIST = {
    'cloud-init',
    'curtin',
    'juju',
    'juju-core',
    'lxc',
    'lxd',
    'maas',
}


def collect():
    """Main function to submit data to Push Gateway."""
    triage = llp.get_team_daily_triage_count(team='ubuntu-server',
                                             distro='Ubuntu',
                                             blacklist=BLACKLIST)
    backlog = llp.get_team_backlog_count(team='ubuntu-server',
                                         distro='Ubuntu')
    registry = CollectorRegistry()

    Gauge('server_triage_backlog_total',
          'Bugs in team backlog',
          registry=registry).set(backlog)

    Gauge('server_triage_daily_triage_total',
          'Bugs to review daily',
          registry=registry).set(triage)

    lgw.push2gateway('triage', registry)


if __name__ == '__main__':
    collect()
