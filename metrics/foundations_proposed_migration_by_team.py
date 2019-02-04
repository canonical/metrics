#!/usr/bin/env python3
"""Submit metrics for proposed-migration per team statistics."""
import argparse
from io import StringIO
import logging
import urllib
import yaml

from metrics.helpers import util


def get_proposed_migration_queue(team):
    """Get information about current proposed-migration queue."""
    src = 'https://people.canonical.com/~ubuntu-archive/proposed-migration/' \
          + 'update_excuses_by_team.yaml'
    logging.info('Pulling proposed-migration stats')
    with urllib.request.urlopen(src) as req:
        code = req.getcode()
        if code != 200:
            logging.error('URL %s failed with code %u', req.geturl(), code)
            return {}
        yamldata = StringIO(req.read().decode('UTF-8'))
    yaml_handle = yaml.safe_load(yamldata)
    valid = 0
    not_considered = 0
    ages = []
    backlog = 0
    for data in yaml_handle[team]:
        ages.append(int(data['age']))
        # math is from britney1/scripts/backlog-report
        backlog += max(int(data['age']) - 3, 0)
        # valid candidate logic comes from britney2/excuse.py
        if data['data']['is-candidate']:
            valid += 1
        else:
            not_considered += 1
    if ages:
        # math is from britney1/scripts/backlog-report
        median_age = ages[int(len(ages)/2)]
    else:
        median_age = 0

    metric = {
        'measurement': 'foundations_devel_proposed_migration_by_team',
        'fields': {
            'team': team.replace('-', '_'),
            # Number of packages waiting in devel-proposed
            'valid_candidates': valid,
            'not_considered': not_considered,
            # Median age of packages waiting in devel-proposed
            'median_age': median_age,
            # Size of devel-proposed backlog (packages x days)
            'backlog': backlog,
        },
    }

    return metric


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    PARSER.add_argument('--team', help='team_name')
    ARGS = PARSER.parse_args()
    logging.basicConfig(level=logging.DEBUG)

    TEAM = ARGS.team
    try:
        DATA = get_proposed_migration_queue(TEAM)
    finally:
        if not ARGS.dryrun:
            print('Pushing data...')
            util.influxdb_insert([DATA])
        else:
            print('Valid candidates: %i' % DATA['fields']['valid_candidates'])
            print('Not considered candidates: %i' %
                  DATA['fields']['not_considered'])
            print('Median age: %i' % DATA['fields']['median_age'])
            print('Backlog: %i' % DATA['fields']['backlog'])
