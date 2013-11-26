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
                'watch']
    )
).keys
issue_maintainer = P(issue_anon, issue_user,
    ('edit', ['url_key',
              '_status',
              'title',
              'desc']
    )
).keys
issue_creator = issue_maintainer

issue_acl = {'maintainer': issue_maintainer,
             'anonymous': issue_anon,
             'user': issue_user}

# Project
project_anon = P(
    ('view', ['standard_join',
              'page_join',
              'disp_join']
    )
).keys
project_user = P(project_anon,
    ('action', ['vote',
                'watch']
    )
).keys
project_maintainer = P(project_anon, project_user,
    ('edit', ['name',
              'website']
    )
).keys

project_acl = {'maintainer': project_maintainer,
               'anonymous': project_anon,
               'user': project_user}
