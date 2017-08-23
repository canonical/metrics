#!/usr/bin/env python3
"""Submit metrics regarding most common crashes in errors.u.c.

Copyright 2017 Canonical Ltd.
Brian Murray <brian@canonical.com>
"""

import argparse
import sys
import urllib.error
import urllib.request

from datetime import date, timedelta
import simplejson as json
from prometheus_client import CollectorRegistry, Gauge

from metrics.helpers import lp
from metrics.helpers import util

BASE_ERRORS_URL = 'https://errors.ubuntu.com/api/1.0'
MCP_ERRORS_URL = BASE_ERRORS_URL + '/most-common-problems'


def team_subscribed_mcp_count(team_name):
    """Query for the per release count of errors for team subbed pkgs."""
    # find the active releases
    ubuntu = lp.get_ubuntu()
    active_series = [s for s in ubuntu.series if s.active]
    per_series = {}
    # just examine the top 10 crashs
    limit = 10
    mcp_url = '%s/?format=json&user=%s&limit=%i' % \
              (MCP_ERRORS_URL, team_name, limit)
    # if we use today's date the count will reset to 0 at the start of the
    # day, instead filter using yesterday
    today = date.today()
    yesterday = today - timedelta(days=1)
    yesterday_str = yesterday.isoformat()
    mcp_url += '&from=%s&to=%s' % (yesterday_str, yesterday_str)

    # query errors for no release, not quite a sum of every release because
    # with limit 10 it could be 3 from Z, 2 from T, 5 from X.
    try:
        mcp_file = urllib.request.urlopen(mcp_url)
    except urllib.error.HTTPError:
        print('Timeout connecting to errors.ubuntu.com')
        sys.exit(1)
    mcp_data = json.load(mcp_file)
    top_ten_sum = 0
    for datum in mcp_data['objects']:
        top_ten_sum += datum['count']
    per_series['all_series'] = {}
    per_series['all_series']['sum_top_ten_counts'] = top_ten_sum

    # query for each active release
    for series in active_series:
        mcp_url += '&release=Ubuntu%%20%s' % series.version
        try:
            mcp_file = urllib.request.urlopen(mcp_url)
        except urllib.error.HTTPError:
            print('Timeout connecting to errors.ubuntu.com')
            sys.exit(1)
        mcp_data = json.load(mcp_file)
        per_series[series.name] = {}
        top_ten_sum = 0
        for datum in mcp_data['objects']:
            top_ten_sum += datum['count']
        per_series[series.name]['sum_top_ten_counts'] = top_ten_sum

    return per_series


def collect(team_name, dryrun=False):
    """Collect and push errors.u.c related metrics."""
    # check to see if its a vaild team LP team
    try:
        lp.LP.people[team_name]
    except KeyError:
        print('Team %s does not exist in LP.' % team_name)
        return

    mcp_data = team_subscribed_mcp_count(team_name)

    for series in mcp_data:
        print("%s: %s" % (series, mcp_data[series]['sum_top_ten_counts']))

    if not dryrun:
        # metric names can not have a hyphen in them
        team_name = team_name.replace('-', '_')

        print('Pushing data...')
        registry = CollectorRegistry()

        gauge = Gauge('%s_errors_mcp_sum_top_ten' % team_name,
                      "Sum of yesterday's top ten crashes in errors",
                      ['series'],
                      registry=registry)
        for series in mcp_data:
            gauge.labels(series).set(
                mcp_data[series]['sum_top_ten_counts'])

        util.push2gateway('%s_mcp_errors' % team_name, registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    PARSER.add_argument('--teams', nargs='+',
                        help='Team(s) to use', required=True)
    ARGS = PARSER.parse_args()

    print("Sum of yesterday's top ten crashes for:")
    for team in ARGS.teams:
        print("\n%s" % team)
        print("-"*(len(team)))
        collect(team, ARGS.dryrun)
