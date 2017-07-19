#!/usr/bin/env python3
"""
Map a Prometheus prefix to the corresponding Launchpad team name.

Copyright 2017 Canonical Ltd.
Daniel Watkins <daniel.watkins@canonical.com>
"""
import argparse

from metrics.helpers.util import get_launchpad_team_name


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('team_name', help='team name')
    ARGS = PARSER.parse_args()
    print(get_launchpad_team_name(ARGS.team_name))
