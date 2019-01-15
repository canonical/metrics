#!/usr/bin/env python3
"""Submit metrics for the specified project.

Copyright 2017-2018 Canonical Ltd.
Joshua Powers <josh.powers@canonical.com>
"""
import argparse

from metrics.helpers import lp
from metrics.helpers import util


def collect(project, repo='', dryrun=False, pkg_name=None):
    """Submit data to Push Gateway."""
    print(project)

    if pkg_name is None:
        pkg_name = project

    project_new = lp.get_bug_count(project, status='New')
    project_total = lp.get_bug_count(project)
    ubuntu_new = lp.get_ubuntu_bug_count(pkg_name, status='New')
    ubuntu_total = lp.get_ubuntu_bug_count(pkg_name)
    reviews = lp.get_active_review_count(project)

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
        pkg_str = project.replace('-', '') if '-' in project else project

        data = [
            {
                'measurement': 'pkg_%s' % pkg_str,
                'fields': {
                    'bug_total': project_total - project_new,
                    'bug_new': project_new,
                    'bug_ubuntu_total': ubuntu_total - ubuntu_new,
                    'bug_ubuntu_new': ubuntu_new,
                    'review_total': reviews,
                    'contrib_total': len(contrib),
                    'contrib_external_total': len(contrib_external),
                    'contrib_internal_total': len(contrib_internal),
                }
            }
        ]

        util.influxdb_insert(data)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('name', help='project name')
    PARSER.add_argument('--dryrun', action='store_true')
    PARSER.add_argument('--repo',
                        help=('repo url (e.g. lp:curtin or '
                              'https://git.launchpad.net/cloud-init'))
    PARSER.add_argument('--package-name', default=None,
                        help='package name, only needed if different to'
                             ' project name')
    ARGS = PARSER.parse_args()
    collect(ARGS.name, ARGS.repo, ARGS.dryrun, ARGS.package_name)
