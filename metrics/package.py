#!/usr/bin/env python3
"""Submit metrics for the specififed project.

Copyright 2017 Canonical Ltd.
Joshua Powers <josh.powers@canonical.com>
"""
import argparse

from prometheus_client import CollectorRegistry, Gauge

from metrics.helpers import lp
from metrics.helpers import util


def collect(pkg, dryrun=False):
    """Submit data to Push Gateway."""
    # Prometheus does not like '-' in names (e.g. cloud-init)
    project_new = lp.get_bug_count(pkg, status='New')
    project_total = lp.get_bug_count(pkg)
    ubuntu_new = lp.get_ubuntu_bug_count(pkg, status='New')
    ubuntu_total = lp.get_ubuntu_bug_count(pkg)
    reviews = lp.get_active_review_count(pkg)

    print(pkg)
    print('%s total bugs (%s new)' % (project_total, project_new))
    print('%s pkg bugs (%s new)' % (ubuntu_total, ubuntu_new))

    if not dryrun:
        print('Pushing data...')
        pkg_str = pkg.replace('-', '') if '-' in pkg else pkg

        registry = CollectorRegistry()

        Gauge('server_%s_bug_total' % pkg_str,
              'Bugs in project',
              None,
              registry=registry).set(project_total - project_new)

        Gauge('server_%s_bug_new_total' % pkg_str,
              'Bugs in project, marked new',
              None,
              registry=registry).set(project_new)

        Gauge('server_%s_bug_ubuntu_total' % pkg_str,
              'Bugs in Ubuntu pkg',
              None,
              registry=registry).set(ubuntu_total - ubuntu_new)

        Gauge('server_%s_bug_ubuntu_new_total' % pkg_str,
              'Bugs in Ubuntu pkg, marked new',
              None,
              registry=registry).set(ubuntu_new)

        Gauge('server_%s_review_total' % pkg_str,
              'Active reviews',
              None,
              registry=registry).set(reviews)

        util.push2gateway(pkg_str, registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('-d', '--dryrun', action='store_true')
    PARSER.add_argument('name', help='project name')
    ARGS = PARSER.parse_args()
    collect(ARGS.name, ARGS.dryrun)
