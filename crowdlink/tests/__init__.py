import crowdlink
import json
import os
import six

from pprint import pprint
from unittest import TestCase
from flask.ext.login import login_user, current_user
from crowdlink import root
from crowdlink.models import User, Email, Comment, Solution, Project, Issue


class ThinTest(TestCase):
    """ Represents a set of tests that only need the database iniailized, but
    no fixture data """

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()

    def post(self, uri, status_code, params=None, has_data=True, headers=None,
             success=True, typ='post'):
        if headers is None:
            headers = {}
        response = getattr(self.client, typ)(
            uri,
            data=json.dumps(params),
            headers=headers,
            content_type='application/json')
        print(response.status_code)
        print(response.data)
        j = json.loads(response.data.decode('utf8'))
        pprint(j)
        assert response.status_code == status_code
        if has_data:
            assert response.data
        if success and status_code == 200:
            assert j['success']
        else:
            assert not j['success']
        return j

    def patch(self, uri, status_code, **kwargs):
        return self.post(uri, status_code, typ='patch', **kwargs)

    def put(self, uri, status_code, **kwargs):
        return self.post(uri, status_code, typ='put', **kwargs)

    def delete(self, uri, status_code, **kwargs):
        return self.post(uri, status_code, typ='delete', **kwargs)

    def get(self, uri, status_code, params=None, has_data=True, success=True,
            headers=None):
        if params:
            for p in params:
                if isinstance(params[p], dict) or isinstance(params[p], list):
                    params[p] = json.dumps(params[p])
        if headers is None:
            headers = {}
        response = self.client.get(uri, query_string=params, headers=headers)
        print(response.status_code)
        print(response.data)
        if has_data:
            assert response.data
        j = json.loads(response.data.decode('utf8'))
        pprint(j)
        assert response.status_code == status_code
        if success and status_code == 200:
            assert j['success']
        else:
            assert not j['success']
        return j

    def setUp(self):
        app = crowdlink.create_app()
        app.config['TESTING'] = True
        # Remove flasks stderr handler, replace with stdout so nose can
        # capture properly
        del app.logger.handlers[0]
        try:
            config_vars = json.load(open(root + '/testing.json'))
            public = list(six.iteritems(config_vars['public']))
            private = list(six.iteritems(config_vars['private']))
            config_vars = dict(private + public)
            for key, val in config_vars.items():
                app.config[key] = val
        except IOError:
            app.logger.warning("Unable to import testing.json, not using "
                               "testing overrides", exc_info=True)
        with app.app_context():
            self.db = crowdlink.db
            self.setup_db()

        self.app = app
        self._ctx = self.app.test_request_context()
        self._ctx.push()
        self.client = self.app.test_client()

    def setup_db(self):
        self.db.drop_all()
        self.db.create_all()

    def new_user(self, username='velma', active=True, login=False, login_ctx=False):
        # create a user for testing
        usr = User.create(username, "testing", username + '@crowdlink.io')
        self.db.session.commit()
        # activate the user if requested
        if active:
            Email.activate_email(username + '@crowdlink.io', force=True)

        # now log them in via api call, or direct call if requested
        if login:
            self.login(username=username)
        if login_ctx:
            self.login_ctx(username=username)
        return usr

    def login(self, username='velma'):
        user = self.db.session.query(User).filter_by(username=username).one()
        login_user(user)

    def login_ctx(self, username='velma', password='testing'):
        data = {
            'identifier': username,
            'password': password,
            '__action': 'login',
            '__cls': True
        }
        ret = self.patch('/api/user', 200, params=data)
        pprint(ret)
        return ret

    def provision_issue(self, project, user=None):
        if user is None:
            user = project.owner
        new_issue = Issue.create(
            user=user,
            title='testing title..',
            desc='Awesome testing description',
            project=project).save()
        self.db.session.commit()
        return new_issue

    def provision_project(self, name='Crowdlink', url_key='crowdlink',
                          user=current_user):
        proj = Project(
            owner=user,
            name=name,
            website='http://google.com/',
            url_key=url_key,
            desc='Awesome desc').save()
        self.db.session.commit()
        return proj

    def provision_solution(self, issue, user=None):
        if user is None:
            user = issue.creator
        sol = Solution.create(
            title='dfgljksdflkj',
            user=user,
            issue=issue,
            desc='sdflgjsldfkjgsdfg').save()
        self.db.session.commit()
        return sol

    def provision_comment(self, thing, user=current_user):
        comm = Comment.create(
            thing=thing,
            user=user,
            message='dsfgljksdfgljksdfgljk').save()
        self.db.session.commit()
        return comm

    def provision_many(self, user=current_user):
        project = self.provision_project(user=user)
        issue = self.provision_issue(project)
        solution = self.provision_solution(issue)
        self.provision_comment(solution, user=user)

    def logout(self):
        ret = self.get('/api/logout', 200)
        assert ret['access_denied']
        return ret
