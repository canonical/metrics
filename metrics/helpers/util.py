"""Various utility functions.

Copyright 2017 Canonical Ltd.
Robbie Basak <robie.basak@canonical.com>
Joshua Powers <josh.powers@canonical.com>
"""
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
try:
    from urllib.error import URLError
    from urllib.request import urlopen
except ImportError:
    # Python 2
    from urllib2 import URLError
    from urllib2 import urlopen

from influxdb import InfluxDBClient
from prometheus_client import push_to_gateway

INSTANCE = 'ubuntu-server'


def bzr_contributors(pkg):
    """Return numbers on bzr project contributors."""
    with tempfile.TemporaryDirectory() as temp:
        run('bzr branch %s %s/%s' % (pkg, temp, pkg))
        out, _, _ = run('bzr stats -q %s/%s' % (temp, pkg))
        emails = re.findall(r'<\S+@\S+>', out.decode("utf-8"))
        # strip the < and > from emails, needs these in regex, but not
        # results to be consistant with git results.
        return ([s.strip('>').strip('<') for s in emails])


def git_contributors(git_url):
    """Return numbers on git project contributors."""
    import git
    with tempfile.TemporaryDirectory() as temp:
        print('Cloning %s into %s' % (git_url, temp))
        git.Repo.clone_from(git_url, temp)
        return list(set(git.Git(temp).log('--pretty=%ae').split('\n')))


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


def get_contributors(project):
    """Get a list of contributor emails."""
    if not project:
        return []

    if 'lp:' in project:
        return bzr_contributors(project)

    return git_contributors(project)


def get_json_from_url(json_url):
    """Return JSON from a URL."""
    with urlopen(json_url) as url:
        data = json.loads(url.read().decode())

    return data


def get_team_packages(team='ubuntu-server'):
    """Return a team's packages based on package-team mapping."""
    url = ("http://people.canonical.com/~ubuntu-archive/"
           "package-team-mapping.json")
    return get_json_from_url(url)[team]


def get_launchpad_team_name(team):
    """Return a Launchpad team name based on the shorter name given."""
    mapping = {
        'foundations': 'foundations-bugs',
        'server': 'ubuntu-server',
        'security': 'ubuntu-security',
        'openstack': 'ubuntu-openstack',
    }
    return mapping[team]


def influxdb_connect():
    """Connect to an InfluxDB instance."""
    try:
        hostname = os.environ['INFLUXDB_HOSTNAME']
        port = os.environ['INFLUXDB_PORT']
        username = os.environ['INFLUXDB_USERNAME']
        password = os.environ['INFLUXDB_PASSWORD']
        database = os.environ['INFLUXDB_DATABASE']
    except KeyError:
        print('error: please source influx credentials before running')
        sys.exit(1)

    return InfluxDBClient(hostname, port, username, password, database)


def influxdb_insert(data, batch_size=None):
    """Write given data to InfluxDB.

    @param data: array of dictionaries of data
    """
    client = influxdb_connect()

    if data:
        client.write_points(data, batch_size=batch_size)


def run(cmd):
    """Run local command."""
    print(cmd)
    process = subprocess.Popen(shlex.split(cmd),
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    out, err = process.communicate()
    return out, err, process.returncode


def get_prometheus_ip():
    """Determine Prometheus pushgateway IP or exit if not set."""
    key = 'METRICS_PROMETHEUS'
    if key in os.environ:
        return os.environ.get(key)
    else:
        print('ERROR: environment variable \'%s\' is not set! '
              'Please set to pushgateway IP address and try again.' % key)
        sys.exit(1)


def push2gateway(pkg, registry):
    """Wrap around push_to_gateway."""
    try:
        push_to_gateway(get_prometheus_ip(),
                        job=pkg,
                        grouping_key={'instance': INSTANCE},
                        registry=registry)
    except URLError:
        print('Could not connect to push gateway!')
        sys.exit(1)
