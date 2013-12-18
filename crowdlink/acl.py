from .util import flatten


class P(object):
    keys = []

    def __init__(self, *args):
        self.keys = []
        for arg in args:
            if isinstance(arg, P):
                self.keys += arg.keys
            elif isinstance(arg, tuple):
                self.keys += flatten(arg)
            elif isinstance(arg, list):
                self.keys += arg
            else:
                self.keys.append(arg)


# Issues
issue_anon = P(
    ('view', ['standard_join',
              'page_join',
              'brief_join',
              'disp_join']
     )
).keys
issue_user = P(issue_anon,
               ('action', ['vote',
                'add_solution',
                'watch']
                )).keys
issue_maintainer = P(issue_anon, issue_user,
                     ('edit', ['url_key',
                               '_status',
                               'title',
                               'desc']
                      )).keys
issue_creator = issue_maintainer

issue_acl = {'maintainer': issue_maintainer,
             'anonymous': issue_anon,
             'user': issue_user,
             'creator': issue_creator}

# Project
project_anon = P(
    ('view', ['standard_join',
              'page_join',
              'issue_page_join',
              'disp_join']
     )).keys
project_user = P(project_anon,
                 ('action', ['vote',
                             'add_issue',
                             'watch']
                  )).keys
project_maintainer = P(project_anon, project_user,
                       ('edit', ['name',
                                 'website']
                        )).keys

project_acl = {'maintainer': project_maintainer,
               'anonymous': project_anon,
               'user': project_user}

# Solution
solution_anon = P(
    ('view', ['standard_join',
              'page_join',
              'disp_join']
     )).keys
solution_user = P(solution_anon,
                  ('action', ['vote',
                              'watch']
                   )).keys
solution_maintainer = P(solution_anon,
                        solution_user,
                        ('edit', ['url_key',
                                  'title',
                                  'desc']
                         )).keys

solution_acl = {'maintainer': solution_maintainer,
                'anonymous': solution_anon,
                'user': solution_user}

# User
user_anon = P(
    ('view', ['standard_join',
              'page_join',
              'disp_join']
     )).keys
user_user = P(user_anon,
              ('action', ['vote',
                          'watch']
               )).keys
user_owner = P(user_anon,
               user_user,
               ('edit', ['url_key',
                         'title',
                         'desc']
                ),
               ('view', ['home_join']
                )).keys

user_acl = {'owner': user_owner,
            'anonymous': user_anon,
            'user': user_user}

# Charge
charge_anon = []
charge_user = []
charge_owner = P(charge_anon,
                 charge_user,
                 ('view', ['standard_join']),
                 ('action', ['add_earmark'])
                 ).keys

charge_acl = {'owner': charge_owner,
              'anonymous': charge_anon,
              'user': charge_user}

# Transfer
transfer_anon = []
transfer_user = []
transfer_owner = P(transfer_anon,
                   transfer_user,
                   ('view', ['standard_join']),
                   ).keys

transfer_acl = {'owner': transfer_owner,
                'anonymous': transfer_anon,
                'user': transfer_user}

# Recipient
recipient_anon = []
recipient_user = []
recipient_owner = P(recipient_anon,
                    recipient_user,
                    ('view', ['standard_join']),
                    ).keys

recipient_acl = {'owner': recipient_owner,
                 'anonymous': recipient_anon,
                 'user': recipient_user}


# Earmark
earmark_anon = []
earmark_user = []
earmark_sender = P(earmark_anon,
                   earmark_user,
                   ('edit', ['amount']
                    ),
                   ('view', ['standard_join']
                    )).keys
earmark_reciever = P(earmark_anon,
                     earmark_user,
                     ('view', ['standard_join']
                      )).keys

earmark_acl = {'reciever': earmark_reciever,
               'sender': earmark_sender,
               'anonymous': earmark_anon,
               'user': earmark_user}


# Mark
mark_anon = []
mark_user = []
mark_sender = P(mark_anon,
                mark_user,
                ('edit', ['amount']
                 ),
                ('view', ['standard_join']
                 )).keys
mark_reciever = P(mark_anon,
                  mark_user,
                  ('view', ['standard_join']
                   )).keys

mark_acl = {'owner': mark_sender,
            'anonymous': mark_anon,
            'user': mark_user}
