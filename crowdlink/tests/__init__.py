import decorator
import crowdlink
import json
import os
import six

from pprint import pprint
from unittest import TestCase
from flask.ext.login import login_user, logout_user
from crowdlink import root
from crowdlink.models import User


def login_required(username='crowdlink', password='testing'):
    """ Decorator that logs in the user under a request context as well as a
    testing cleint """
    def login_required(func, self, *args, **kwargs):
        self.user = self.db.session.query(User).filter_by(username=username).one()
        self.login(username, password)['objects'][0]
        login_user(self.user)
        func(self)
        self.logout()
        logout_user()

    return decorator.decorator(login_required)


def login_required_ctx(username='crowdlink', password='testing'):
    """ Decorator for loggin in the user under a request context. Helpful for
    testing """
    def login_required_ctx(f, *args, **kwargs):
        self = args[0]
        self.user = (self.db.session.query(User).
                     filter_by(username=username).one())
        login_user(self.user)
        f(self)
        logout_user()

    return decorator.decorator(login_required_ctx)


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


class BaseTest(ThinTest):
    def setup_db(self):
        os.system("psql -U crowdlink -h localhost crowdlink_testing -f "
                  "{0}/assets/test_provision.sql > /dev/null 2>&1"
                  .format(root))

    def login(self, username, password):
        data = {
            'identifier': username,
            'password': password,
            '__action': 'login',
            '__cls': True
        }
        ret = self.patch('/api/user', 200, params=data)
        pprint(ret)
        return ret

    def logout(self):
        ret = self.get('/api/logout', 200)
        assert ret['access_denied']
        return ret
