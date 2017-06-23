#!/usr/bin/env python3
"""Submit metrics for the specififed project.

Copyright 2017 Canonical Ltd.
Joshua Powers <josh.powers@canonical.com>
"""
import argparse

from prometheus_client import CollectorRegistry, Gauge

import liblaunchpad as llp
import libgateway as lgw


def collect(pkg):
    """Main function to submit data to Push Gateway."""
    # Prometheus does not like '-' in names (e.g. cloud-init)
    pkg_str = pkg.replace('-', '') if '-' in pkg else pkg

    registry = CollectorRegistry()

    Gauge('server_%s_bug_total' % pkg_str,
          'Bugs in project',
          registry=registry).set(llp.get_bug_count(pkg))

    Gauge('server_%s_bug_new_total' % pkg_str,
          'Bugs in project, marked new',
          registry=registry).set(llp.get_bug_count(pkg, status='New'))

    Gauge('server_%s_bug_ubuntu_total' % pkg_str,
          'Bugs in Ubuntu pkg',
          registry=registry).set(llp.get_ubuntu_bug_count(pkg))

    Gauge('server_%s_bug_ubuntu_new_total' % pkg_str,
          'Bugs in Ubuntu pkg, marked new',
          registry=registry).set(llp.get_ubuntu_bug_count(pkg, status='New'))

    Gauge('server_%s_review_total' % pkg_str,
          'Active reviews',
          registry=registry).set(llp.get_active_review_count(pkg))

    lgw.push2gateway(pkg_str, registry)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('-n', '--name', help='project name', required=True)
    ARGS = PARSER.parse_args()
    collect(ARGS.name)
