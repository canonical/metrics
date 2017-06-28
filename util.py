"""Generate daily upload report.

Copyright 2017 Canonical Ltd.
Robbie Basak <robie.basak@canonical.com>
Joshua Powers <josh.powers@canonical.com>
"""
import json
import subprocess
import urllib.request


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

    ge = subprocess.call(['dpkg', '--compare-versions', upkg, 'ge', dpkg])
    if ge == 0:
        return ">"
    else:
        return "<"


def get_json_from_url(url):
    """Return JSON from a URL."""
    with urllib.request.urlopen(url) as url:
        data = json.loads(url.read().decode())

    return data


def get_team_packages(team='ubuntu-server'):
    """Return a team's packages based on package-team mapping."""
    url = ("http://people.canonical.com/~ubuntu-archive/"
           "package-team-mapping.json")
    return get_json_from_url(url)[team]
