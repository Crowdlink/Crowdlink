import stripe

def stripe_card_token(number='4242424242424242'):
    token = stripe.Token.create(
        card={
            "number": number,
            "exp_month": 12,
            "exp_year": 2014,
            "cvc": '123'
        },
    )
    # serialize it
    dct_token = dict(token)
    dct_token['card'] = dict(token.card)
    return dct_token

def stripe_bank_token(routing_number='110000000', account_number='000123456789'):
    # create a new token via the api. this is usually done via the JS side
    token = stripe.Token.create(
        bank_account={
            "country": 'US',
            "routing_number": routing_number,
            "account_number": account_number
        },
    )
    # serialize it
    dct_token = dict(token)
    dct_token['bank_account'] = dict(token.bank_account)
    return dct_token

def flatten(tpl):
    """ Makes a list of values prefixed by the first value of a tuple """
    if isinstance(tpl, tuple):
        keys = []
        for key in tpl[1]:
            keys += [flatten(key)]
        return [tpl[0] + "_" + x for x in keys]
    else:
        return tpl


def flatten_dict(dct):
    """ Used to make building ACL lists convenient. Create infinitely nested
    keys that will just precipitate keys joined with _. Ex:
        ('edit', ['this',
                  'that',
                  'those']
                  )
        will make:
        ['edit_this',
         'edit_that',
         'edit_those']
    Recursively safe so nesting tuples works as expected.
    """

    return {key: flatten(value) for (key, value) in dct.iteritems()}


def inherit_dict(*args):
    """ Joines together multiple dictionaries left to right """
    ret = {}
    for arg in args:
        ret.update(arg)
    return ret


def inherit_lst(*args):
    """ Joines together multiple lists left to right """
    ret = []
    for arg in args:
        for val in arg:
            if val not in ret:
                ret.append(val)
    return ret


def provision():
    from crowdlink.util import stripe_card_token
    from crowdlink import db, root
    from crowdlink.models import Email, User, Project, Issue, Solution
    from crowdlink.fin_models import Charge, Earmark

    from random import choice
    from flask import current_app
    from flask.ext.login import login_user

    import yaml
    import time

    stripe.api_key = current_app.config['stripe_secret_key']
    users = {}

    # make an admin user, and set him as the current user
    admin = User.create("admin", "testing", "admin@crowdlink.io")
    admin.admin = True  # make them an admin
    db.session.commit()
    Email.activate_email('admin@crowdlink.io')
    login_user(admin)

    # make a bunch of testing users

    # velma doesn't have a real username
    velma = User.create(None, "testing", "velma@crowdlink.io")
    users['velma'] = velma

    # fred isn't activated, no email address verified
    fred = User.create("fred", "testing", "fred@crowdlink.io")
    users['fred'] = fred
    db.session.commit()

    # regular users...
    for username in ['scrappy', 'shaggy', 'scooby', 'daphne', 'crowdlink',
                     'barney', 'betty']:
        usr = User.create(username, "testing", username + "@crowdlink.io")
        db.session.commit()
        Email.activate_email(username + '@crowdlink.io')
        users[username] = usr

    pdata = yaml.load(file(root + '/assets/provision.yaml'))

    # Create the project for crowdlink
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
                    user=users['crowdlink'],
                    issue=new_issue,
                    desc=sol_tmpl.get('desc')).save()
                curr_issue['solutions'][sol_tmpl.get('key', sol.url_key)] = (
                    {'obj': sol})

    # get a list of issues to potentially earmark
    issues = []
    for p in projects.values():
        issues += [issue['obj'] for issue in p['issues'].values()]

    # Setup tons of test financial data
    ##########################################################################
    # put some money in a few accounts
    for name in ['shaggy', 'daphne', 'scrappy']:
        for _ in xrange(3):
            amount = choice([333, 666, 1000])
            Charge.create(stripe_card_token(), amount, users[name])
            time.sleep(0.02)  # try not to timeout stripe

    # earmark onto a few different issues with a few users
    for i in xrange(4):
        for name in ['shaggy', 'daphne']:
            user = users[name]
            amount = round(user.available_balance * (choice([30]) / 100.0))
            Earmark.create(issues[i], amount, user)

    # now that we have some earmarks, mature some
    for i in xrange(3):
        for earmark in issues[i].earmarks:
            earmark.mature()
        db.session.commit()

    # mark our issue as completed
    for i in xrange(2):
        issues[i].status = 'Completed'
    db.session.commit()

    # Assign the earmark to some users
    for i in xrange(2):
        for earmark in issues[i].earmarks:
            earmark.assign([(users['scooby'], 50),
                            (users['barney'], 50)])
        db.session.commit()

    # now clear a few of these earmarks
    for i in xrange(1):
        for earmark in issues[i].earmarks:
            earmark.clear()
