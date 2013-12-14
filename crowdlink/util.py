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
    from random import choice
    from crowdlink.models import Email, User, Project, Issue, Solution
    from crowdlink.fin_models import Transaction
    from flask import current_app
    from flask.ext.login import login_user
    import json

    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']

    # Create a simple project and user
    usr = User.create_user("crowdlink", "testing", "support@crowdlink.com")
    Email.activate_email('support@crowdlink.com')

    # Create the project for crowdlink
    proj = Project(
        maintainer=usr,
        name='crowdlink',
        website="http://crowdlink.com",
        url_key='crowdlink',
        desc="A platform for user feedback")
    proj.safe_save()
    proj.subscribe(user=usr)

    issues = [
('Graphing of Improvement popularity', 'Generate simple d3 graphs that show how many votes an Improvement has recieved since its creation. Current thought was a on day to day basis.',
    ['test']),
('Change log for Improvements', 'Like gists on Github, show a historical revision log for an Improvements descriptions'),
('Hot sorting metric for Improvements', 'Periodically re-calculate a "hot" value for various improvements based on how quickly they\'ve recieved votes over time. Similar to reddit, or other websites trending function'),
('Allow revoking of Github synchronization via crowdlink', 'Currently, desynchronizing can only be done via Github.'),
('Approval option for Improvements', 'Similar function to a lot of mailing lists, Improvements would be by default hidden until approved by a project maintainer. Perhaps a user could be put on an approved list as well, allowing their suggestions to be auto-approved.'),
('Promote with donations', 'Instead of dontaing to the project, donate to a charity, yet earmark this donation towards a project or Improvement to show your support'),
('Google Analytics Hooks', 'Allow project maintainers to specify a Google Analytics Key and select from a range of events that they would like logged into their GA account'),
        ]
    for data in issues:
        if len(data) > 2:
            title, desc, solutions = data
        else:
            title, desc = data
        issue = Issue(
            creator=usr,
            title=title,
            desc=desc)
        proj.add_issue(issue, usr)

        for sol in solutions:
            sol = Solution(
                title=sol,
                creator=usr,
                issue=issue).safe_save()
    # fred isn't activated, no email address verified
    fred = User.create_user("fred", "testing", "fred@crowdlink.com")
    # velma doesn't have a real username
    #velma = User.create_user("", "testing", "velma@crowdlink.com")

    # shaggy is a generous donor, with several charges and donations to
    # crowdlink
    shaggy = User.create_user("shaggy", "testing", "shaggy@crowdlink.com")
    for _ in xrange(10):
        amount = choice([5, 15, 20, 30, 50])
        Transaction.create(stripe_card_token(), amount*100, shaggy)

    scooby = User.create_user("scooby", "testing", "scooby@crowdlink.com")
