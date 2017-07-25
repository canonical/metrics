#!/usr/bin/env python3
"""Submit metrics for number of active uploaders.

Copyright 2017 Canonical Ltd.
Łukasz 'sil2100' Zemczak <lukasz.zemczak@canonical.com>
"""

import argparse
import psycopg2

from prometheus_client import CollectorRegistry, Gauge

from metrics.helpers import lp
from metrics.helpers import util


def get_all_registered_uploaders():
    """Query launchpad for the list of total uploaders."""
    # Since we have no easy and reliable way of getting people with upload
    # rights from packagesets, we only now look at core-dev and motu.
    teams = ['ubuntu-core-dev', 'motu']
    uploaders = set()
    for team in teams:
        team = lp.LP.people[team]
        for person in team.participants:
            if person.is_valid and not person.is_team:
                uploaders.add(person.name)

    return len(uploaders)


def get_uploaders_per_affiliation(connection):
    """Return lists of recent Ubuntu uploaders per affiliation."""
    cur = connection.cursor()

    cur.execute("""
        select changed_by_email
        from ubuntu_upload_history
        where date >= (now() - '3 months'::INTERVAL)
          and changed_by_name != ''
          and changed_by_email != 'archive@ubuntu.com'
          and changed_by_email != 'katie@jackass.ubuntu.com'
          and changed_by_email != 'language-packs@ubuntu.com'
        group by changed_by_email;
""")
    uploaders = cur.fetchall()

    noncanonical = 0
    canonical = 0
    lp_usernames = set()
    canonical_usernames = set()
    for uploader in uploaders:
        uploader = uploader[0]
        if uploader == 'N/A':
            continue

        # Now, sadly, some ugly guesswork needs to happen.
        # The canonical team is private so we can't really check if a user is a
        # member of the team.  Also, because we're running as an anonymous user
        # we also have no access to the user's confirmed_email_addresses field,
        # so we can't even check if there's a canonical.com address in use.
        # In the current state of things all we can do is 'guess'
        lp_person = lp.get_person_by_email(uploader)
        if not lp_person:
            # In case we can't find the user in LP for some reason, just guess
            # depending on the e-mail field - but this shouldn't really happen.
            if '@canonical.com' in uploader:
                canonical += 1
            else:
                noncanonical += 1
            continue

        lp_usernames.add(lp_person.name)
        if lp_person.name in canonical_usernames:
            continue

        # Now we start guessing.  Those that we guess to be canonical end up in
        # the canonical_usernames bucket.
        if '@canonical.com' in uploader:
            canonical_usernames.add(lp_person.name)
        else:
            found = False
            # If there is an ubuntu.com e-mail, maybe substituting it with a
            # canonical works?  If we end up with the same user as before, it's
            # a hit.
            if '@ubuntu.com' in uploader:
                try_user = lp.get_person_by_email(
                    uploader.replace('@ubuntu.com', '@canonical.com'))
                if try_user and try_user == lp_person:
                    canonical_usernames.add(lp_person.name)
                    found = True

            if not found:
                # Another guess - let's try to take the display name and turn
                # it into a canonical e-mail.
                email = ('%s@canonical.com'
                         % lp_person.display_name.replace(' ', '.'))
                try_user = lp.get_person_by_email(email)
                if try_user and try_user == lp_person:
                    canonical_usernames.add(lp_person.name)

    # Only after scanning all e-mail addresses we can definitely be sure how
    # many canonical and non-canonical usernames we had (since some might do
    # uploads with different e-mail addresses)
    for lp_name in lp_usernames:
        if lp_name in canonical_usernames:
            canonical += 1
        else:
            noncanonical += 1

    return (canonical, noncanonical)


def collect(conn, dryrun=False):
    """Collect and push uploader-related metrics."""
    canonical, noncanonical = get_uploaders_per_affiliation(conn)
    uploaders = get_all_registered_uploaders()

    print('Active Canonical Uploaders: %s' % canonical)
    print('Active Non-Canonical Uploaders: %s' % noncanonical)
    print('Current Users with Upload Rights: %s' % uploaders)

    if not dryrun:
        print('Pushing data...')
        registry = CollectorRegistry()

        Gauge('foundations_recent_canonical_uploaders',
              'Active Canonical Uploaders',
              None,
              registry=registry).set(canonical)

        Gauge('foundations_recent_noncanonical_uploaders',
              'Active Non-Canonical Uploaders',
              None,
              registry=registry).set(noncanonical)

        Gauge('foundations_total_uploaders',
              'Current Users with Upload Rights',
              None,
              registry=registry).set(uploaders)

        util.push2gateway('triage', registry)


if __name__ == '__main__':
    psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
    psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)
    CONN = psycopg2.connect(
        database='udd',
        host='udd-mirror.debian.net',
        user='udd-mirror',
        password='udd-mirror'
        )
    CONN.set_client_encoding('UTF-8')

    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('--dryrun', action='store_true')
    ARGS = PARSER.parse_args()
    collect(CONN, ARGS.dryrun)
