from crowdlink import db, root
from crowdlink.tests import stripe_card_token_real, stripe_bank_token_real
from crowdlink.models import Email, User, Project, Issue, Solution, Comment
from crowdlink.fin_models import Charge, Earmark, Recipient, Transfer

from random import choice
from flask import current_app
from flask.ext.login import login_user

import yaml
import time
import stripe

def provision():
    """ Creates fixture data for the tests by making real connections with
    Stripe and setting up test projects, issues, etc """
    # ensure we aren't sending any emails
    current_app.config['send_emails'] = False
    stripe.api_key = current_app.config['stripe_secret_key']
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

    # get a list of issues to potentially earmark
    issues = []
    for p in projects.values():
        issues += [issue['obj'] for issue in p['issues'].values()]

    # Setup tons of test financial data
    ##########################################################################
    # setup some accounts as recipients for transfers
    for user, name in [('scooby', 'Scooby Do'),
                       ('barney', 'Barney Rubble')]:
        recp = Recipient.create(
            stripe_bank_token_real(),
            name,
            False,
            user=users[user])
        recp.verified = True

    # put moneies in a few accounts
    for name in ['shaggy', 'daphne', 'scrappy', 'velma', 'fred']:
        for _ in xrange(3):
            amount = choice([1000, 2000])
            Charge.create(stripe_card_token_real(), amount, users[name])
            time.sleep(0.02)  # try not to timeout stripe

    # earmark onto a few different issues with a few users
    for i in xrange(8):
        for name in ['shaggy', 'daphne', 'velma']:
            user = users[name]
            amount = round(user.available_balance * (.1))
            Earmark.create(issues[i], amount, user=user)

    # now that we have some earmarks, mature some
    for i in xrange(6):
        for earmark in issues[i].earmarks:
            earmark.mature()
        db.session.commit()

    # mark our issue as completed
    for i in xrange(5):
        issues[i].status = 'Completed'
    db.session.commit()

    # Assign the earmark to some users
    for i in xrange(4):
        for earmark in issues[i].earmarks:
            earmark.assign([(users['scooby'], 33),
                            (users['barney'], 33),
                            (users['daphne'], 34)])
        db.session.commit()

    # now clear a few of these earmarks to put money in some accounts
    for i in xrange(2):
        for earmark in issues[i].earmarks:
            earmark.clear()

    # now we have some people with money from marks
    # daphne spends, barney transfers, scooby lets it sit
    user = users['daphne']
    amount = round(user.available_balance * .75)
    Earmark.create(issues[0], amount, user=user)

    user = users['barney']
    amount = round(user.available_balance)
    Transfer.create(amount, user.recipients[0], user=user)
