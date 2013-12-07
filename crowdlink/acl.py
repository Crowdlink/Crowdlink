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
     )
).keys
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
solution_maintainer = P(solution_anon, solution_user,
                        ('edit', ['url_key',
                                  'title',
                                  'desc']
                         )).keys

solution_acl = {'maintainer': solution_maintainer,
                'anonymous': solution_anon,
                'user': solution_user}
