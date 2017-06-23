"""Various Launchpad queries.

See https://api.launchpad.net/devel.html for more details.

Copyright 2017 Canonical Ltd.
Joshua Powers <josh.powers@canonical.com>
"""
from datetime import datetime, timedelta

from launchpadlib.launchpad import Launchpad

LP = Launchpad.login_anonymously('metrics', 'production', version='devel')


def get_series_name(series_link):
    """Return series name."""
    return LP.load(series_link).name


def get_person_name(person_link):
    """Return person name."""
    if person_link:
        return LP.load(person_link).name

    return None


def get_ubuntu():
    """Return Ubuntu specific distribution."""
    return LP.distributions['ubuntu']


def get_bug_count(package, status=None):
    """Reports total bugs for a package"""
    project = LP.projects[package]

    if status:
        result = project.searchTasks(status=status)
    else:
        result = project.searchTasks()

    return len(result)


def get_ubuntu_bug_count(package, status=None):
    """Reports total bugs in Ubuntu for a package."""
    distro = LP.distributions['Ubuntu']
    src_pkg = distro.getSourcePackage(name=package)

    if status:
        result = src_pkg.searchTasks(status=status)
    else:
        result = src_pkg.searchTasks()

    return len(result)


def get_active_review_count(package):
    """Determine repo type and return review count."""
    if is_git_repo(package):
        return get_git_active_review_count(package)
    return get_bzr_active_review_count(package)


def get_git_active_review_count(package):
    """Reports total git reviews for a package."""
    reviews = LP.git_repositories.getByPath(path=package).landing_candidates
    return len([x for x in reviews if x.queue_status == 'Needs review'])


def get_bzr_active_review_count(package):
    """Reports total bzr reviews for a package."""
    reviews = LP.branches.getByPath(path=package).landing_candidates
    return len([x for x in reviews if x.queue_status == 'Needs review'])


def get_team_backlog_count(team, distro):
    """Reports total bugs for Launchpad team on a distro."""
    lp_distro = LP.distributions[distro]
    lp_team = LP.people[team]
    return len(lp_distro.searchTasks(bug_subscriber=lp_team))


def get_team_daily_triage_count(team, distro, blacklist=None):
    """Reports total bugs for a Launchpad team that need triage."""
    lp_distro = LP.distributions[distro]
    lp_team = LP.people[team]

    date_start = datetime.now().date().strftime('%Y-%m-%d')
    date_end = (datetime.now().date() + timedelta(days=1)).strftime('%Y-%m-%d')

    # structural_subscriber sans already subscribed
    bugs_since_start = {
        task.self_link: task for task in lp_distro.searchTasks(
            modified_since=date_start, structural_subscriber=lp_team
        )}
    bugs_since_end = {
        task.self_link: task for task in lp_distro.searchTasks(
            modified_since=date_end, structural_subscriber=lp_team
        )}

    bugs_in_range = {
        link: task for link, task in bugs_since_start.items()
        if link not in bugs_since_end
    }

    results = [b for b in bugs_in_range if b.split('/')[-3] not in blacklist]

    return len(results)


def is_git_repo(pkg):
    """Determine if package has a git repo or not."""
    return True if LP.git_repositories.getByPath(path=pkg) else False
