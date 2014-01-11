from crowdlink import db, root
from crowdlink.models import Email, User, Project, Issue, Solution, Comment

from flask import current_app
from flask.ext.login import login_user

import yaml

def provision():
    """ Creates fixture data for the tests by making real connections with
    Stripe and setting up test projects, issues, etc """
    # ensure we aren't sending any emails
    current_app.config['send_emails'] = False
    users = {}

    # make an admin user, and set him as the current user
    admin = User.create("admin", "testing", "admin@crowdlink.io")
    admin.admin = True  # make them an admin
    db.session.commit()
    assert Email.activate_email('admin@crowdlink.io', force=True)
    login_user(admin)

    # make a bunch of testing users
    # =========================================================================
    # fred isn't activated, no email address verified
    fred = User.create("fred", "testing", "fred@crowdlink.io")
    users['fred'] = fred
    db.session.commit()

    # regular users...
    for username in ['velma', 'scrappy', 'shaggy', 'scooby', 'daphne', 'crowdlink',
                     'barney', 'betty']:
        usr = User.create(username, "testing", username + "@crowdlink.io")
        db.session.commit()
        assert Email.activate_email(username + '@crowdlink.io', force=True)
        users[username] = usr

    # Create projects, issues, comments, etc from a template file
    # =========================================================================
    pdata = yaml.load(file(root + '/assets/provision.yaml'))
    projects = {}
    for project in pdata['projects']:
        # create a sweet new project...
        proj = Project(
            maintainer=users[project['maintainer']],
            name=project['name'],
            website=project['website'],
            url_key=project['url_key'],
            desc=project['desc']).save()
        curr_proj = {'obj': proj}
        projects[proj.url_key] = curr_proj

        # subscribe some users if requested in config
        if 'subscribers' in project:
            for sub in project['subscribers']:
                proj.set_subscribed(True, user=users[sub])

        # Add out issues to the database
        curr_proj['issues'] = {}
        for issue in project.get('issues', []):
            # add some solutions to the issue
            new_issue = Issue.create(
                user=users[issue.get('creator', proj.maintainer.username)],
                title=issue['title'],
                desc=issue.get('desc'),
                project=proj).save()

            curr_issue = {'obj': new_issue}
            curr_proj['issues'][issue.get('key', new_issue.url_key)] = curr_issue

            # add solution to the db if they are listed
            curr_issue['solutions'] = {}
            for sol_tmpl in issue.get('solutions', []):
                sol = Solution.create(
                    title=sol_tmpl['title'],
                    user=users[sol_tmpl.get('creator', proj.maintainer.username)],
                    issue=new_issue,
                    desc=sol_tmpl.get('desc')).save()
                curr_issue['solutions'][sol_tmpl.get('key', sol.url_key)] = (
                    {'obj': sol})

            # add comments to the issue
            curr_issue['comments'] = {}
            for comm_tmpl in issue.get('comments', []):
                comm = Comment.create(
                    thing=new_issue,
                    user=users[comm_tmpl.get('creator', new_issue.creator.username)],
                    message=comm_tmpl.get('message')).save()
                curr_issue['comments'][sol_tmpl.get('key', comm.id)] = (
                    {'obj': comm})
