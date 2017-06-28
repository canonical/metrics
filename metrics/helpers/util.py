"""Various utility functions.

Copyright 2017 Canonical Ltd.
Robbie Basak <robie.basak@canonical.com>
Joshua Powers <josh.powers@canonical.com>
"""
import json
import subprocess
import sys
import urllib.error
import urllib.request

from prometheus_client import push_to_gateway

INSTANCE = 'ubuntu-server'
PROMETHEUS_IP = '10.245.168.18:9091'


def dpkg_compare_versions(upkg, dpkg):
    """Compare two dpkg versions."""
    if "-" in upkg:
        uver = upkg.split("-")[0]
        dver = dpkg.split("-")[0]
    else:
        uver = upkg
        dver = dpkg

    if uver == dver:
        return "="

    greater_than = subprocess.call(['dpkg', '--compare-versions',
                                    upkg, 'ge', dpkg])
    if greater_than == 0:
        return ">"

    return "<"


def get_json_from_url(json_url):
    """Return JSON from a URL."""
    with urllib.request.urlopen(json_url) as url:
        data = json.loads(url.read().decode())

    return data


def get_team_packages(team='ubuntu-server'):
    """Return a team's packages based on package-team mapping."""
    url = ("http://people.canonical.com/~ubuntu-archive/"
           "package-team-mapping.json")
    return get_json_from_url(url)[team]


def push2gateway(pkg, registry):
    """Wrap around push_to_gateway."""
    try:
        push_to_gateway(PROMETHEUS_IP,
                        job=pkg,
                        grouping_key={'instance': INSTANCE},
                        registry=registry)
    except urllib.error.URLError:
        print('Could not connect to push gateway!')
        sys.exit(1)
