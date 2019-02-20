"""Various Launchpad queries.

See https://api.launchpad.net/devel.html for more details.

Copyright 2017 Canonical Ltd.
Joshua Powers <josh.powers@canonical.com>
"""
from datetime import datetime, timedelta
import sys

from launchpadlib.errors import BadRequest
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


def get_person_by_email(email):
    """Return person object for email."""
    try:
        return LP.people.getByEmail(email=email)
    except BadRequest:
        return None


def get_ubuntu():
    """Return Ubuntu specific distribution."""
    return LP.distributions['ubuntu']


def get_bug_count(project, status=None):
    """Report count of open or $status bugs for a project."""
    try:
        project = LP.projects[project]
    except KeyError:
        print('Invalid project name: %s' % project)
        sys.exit(1)

    if status:
        result = project.searchTasks(status=status)
    else:
        result = project.searchTasks()

    return len(result)


def get_ubuntu_bug_count(package, status=None):
    """Report count of open or $status bugs in Ubuntu for a package."""
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
    """Report total git reviews for a package."""
    reviews = LP.git_repositories.getByPath(path=package).landing_candidates
    return len([x for x in reviews if x.queue_status == 'Needs review'])


def get_bzr_active_review_count(package):
    """Report total bzr reviews for a package."""
    reviews = LP.branches.getByPath(path=package).landing_candidates
    return len([x for x in reviews if x.queue_status == 'Needs review'])


def get_team_backlog_count(team, distro):
    """Report count of open bugs for Launchpad team on a distro."""
    lp_distro = LP.distributions[distro]
    lp_team = LP.people[team]
    return len(lp_distro.searchTasks(bug_subscriber=lp_team))


def get_team_daily_triage_count(team, distro, blacklist=None):
    """Report count of open bugs for a Launchpad team that need triage."""
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


def get_team_unassigned_bugs(team, distro):
    """
    Report count of new unassigned bugs for Launchpad team on a distro.

    List the number of bugs that are New and unassigned for a particular
    team subscribed to the bugs.
    """
    lp_distro = LP.distributions[distro]
    lp_team = LP.people[team]
    return len(lp_distro.searchTasks(bug_subscriber=lp_team, assignee=None,
                                     status='New'))


def get_team_incomplete_bugs(team, distro):
    """Report count of incomplete bugs for Launchpad team on a distro."""
    lp_distro = LP.distributions[distro]
    lp_team = LP.people[team]
    return len(lp_distro.searchTasks(bug_subscriber=lp_team,
                                     status='Incomplete'))


def get_mirs_in_review():
    """
    Report count of MIRs in active review.

    Open, Triaged or Confirmed (so not yet approved) bug would be assumed
    to be "in active review".
    """
    lp_distro = LP.distributions['Ubuntu']
    lp_team = LP.people['ubuntu-mir']
    return len(lp_distro.searchTasks(bug_subscriber=lp_team,
                                     status=['Triaged', 'Confirmed']))


def get_mirs_in_security_review():
    """Report count of open, assigned to Security bugs."""
    lp_distro = LP.distributions['Ubuntu']
    lp_team = LP.people['ubuntu-mir']
    assignee = LP.people['ubuntu-security']
    return len(lp_distro.searchTasks(bug_subscriber=lp_team,
                                     assignee=assignee))


def get_approved_mirs():
    """Report count of Fix Committed (pending AA review) MIRs."""
    lp_distro = LP.distributions['Ubuntu']
    lp_team = LP.people['ubuntu-mir']
    return len(lp_distro.searchTasks(bug_subscriber=lp_team,
                                     status='Fix Committed'))


def is_git_repo(pkg):
    """Determine if package has a git repo or not."""
    return bool(LP.git_repositories.getByPath(path=pkg))
