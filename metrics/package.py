#!/usr/bin/env python3
"""Submit metrics for the specififed project.

Copyright 2017 Canonical Ltd.
Joshua Powers <josh.powers@canonical.com>
"""
import argparse

from prometheus_client import CollectorRegistry, Gauge

from metrics.helpers import lp
from metrics.helpers import util


def collect(pkg, repo='', dryrun=False):
    """Submit data to Push Gateway."""
    print(pkg)

    project_new = lp.get_bug_count(pkg, status='New')
    project_total = lp.get_bug_count(pkg)
    ubuntu_new = lp.get_ubuntu_bug_count(pkg, status='New')
    ubuntu_total = lp.get_ubuntu_bug_count(pkg)
    reviews = lp.get_active_review_count(pkg)

    print('%s total bugs (%s new)' % (project_total, project_new))
    print('%s pkg bugs (%s new)' % (ubuntu_total, ubuntu_new))

    contrib = util.get_contributors(repo)
    contrib_internal = [x for x in contrib if x.endswith('@canonical.com')]
    contrib_external = [x for x in contrib if not x.endswith('@canonical.com')]

    print('Total Contributors: %s' % len(contrib))
    print('Total Internal Contributors: %s' % len(contrib_internal))
    print('Total External Contributors: %s' % len(contrib_external))

    if not dryrun:
        print('Pushing data...')
        # Prometheus does not like '-' in names (e.g. cloud-init)
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

        Gauge('server_%s_contrib_total' % pkg_str,
              'Contributors',
              None,
              registry=registry).set(len(contrib))

        Gauge('server_%s_contrib_external_total' % pkg_str,
              'External Contributors',
              None,
              registry=registry).set(len(contrib_external))

        Gauge('server_%s_contrib_internal_total' % pkg_str,
              'Internal Contributors',
              None,
              registry=registry).set(len(contrib_internal))

        util.push2gateway(pkg_str, registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('name', help='project name')
    PARSER.add_argument('--dryrun', action='store_true')
    PARSER.add_argument('--repo',
                        help=('repo url (e.g. lp:curtin or '
                              'https://git.launchpad.net/cloud-init'))
    ARGS = PARSER.parse_args()
    collect(ARGS.name, ARGS.repo, ARGS.dryrun)
