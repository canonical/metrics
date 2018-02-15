#!/usr/bin/env python3
"""Submit metrics for number of bugs assigned to a particular team.

Copyright 2018 Canonical Ltd.
Łukasz 'sil2100' Zemczak <lukasz.zemczak@canonical.com>
"""
import argparse

from metrics.helpers import lp
from metrics.helpers import util


IMPORTANCE_LIST = [
    'Undecided', 'Critical', 'High', 'Medium', 'Low', 'Wishlist']
STATUS_LIST = [
    'New', 'Confirmed', 'Triaged', 'In Progress', 'Fix Committed',
    'Incomplete']


def collect(team_name, dryrun=False):
    """Collect data and push to InfluxDB."""
    team = lp.LP.people[team_name]

    counts = {i: dict.fromkeys(STATUS_LIST, 0) for i in IMPORTANCE_LIST}
    tasks = lp.LP.bugs.searchTasks(assignee=team, status=STATUS_LIST)
    for task in tasks:
        counts[task.importance][task.status] += 1

    # Thing to note: currently private bugs are not counted.
    data = []
    for importance, statuses in counts.items():
        for status, count in statuses.items():
            print('{} importance assigned bugs with {} status: {}'.format(
                importance, status, count))
            data.append({
                'measurement': '{}_assigned_bugs'.format(
                    team_name.replace('-', '_')),
                'tags': {
                    'importance': importance,
                    'status': status,
                },
                'fields': {'count': count}
            })

    if not dryrun:
        print('Pushing data...')
        util.influxdb_insert(data)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('team_name', help='team name')
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(ARGS.team_name, ARGS.dryrun)
