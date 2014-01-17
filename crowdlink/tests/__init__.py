import decorator
import crowdlink
import json
import os
import six

from pprint import pprint
from flask.ext.testing import TestCase
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
        self.user = self.db.session.query(User).filter_by(username=username).one()
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

    def json_post(self, url, data):
        return self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json')

    def json_get(self, url, data):
        return self.client.get(
            url,
            query_string=data,
            content_type='application/json')

    def json_put(self, url, data):
        return self.client.put(
            url,
            data=json.dumps(data),
            content_type='application/json')

    def json_patch(self, url, data):
        return self.client.open(
            url,
            method='PATCH',
            data=json.dumps(data),
            content_type='application/json')

    def create_app(self):
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
        return app

    def setup_db(self):
        self.db.drop_all()
        self.db.create_all()


class BaseTest(ThinTest):
    def setup_db(self):
        username = os.environ.get('WERCKER_POSTGRESQL_USERNAME', 'crowdlink')
        database = os.environ.get('WERCKER_POSTGRESQL_DATABASE', 'crowdlink')
        url = os.environ.get('WERCKER_POSTGRESQL_URL')
        if url:
            host = url.split('@')[1].split(':')[0]
        else:
            host = 'localhost'
        if 'WERCKER_POSTGRESQL_PASSWORD' in os.environ:
            os.environ['PGPASSWORD'] = os.environ['WERCKER_POSTGRESQL_PASSWORD']
        os.system("psql -U {username} -h {host} {database} -f "
                  "{root}/assets/test_provision.sql > /dev/null 2>&1"
                  .format(root=root,
                          username=username,
                          database=database,
                          host=host))

    def login(self, username, password):
        data = {
            'identifier': username,
            'password': password,
            '__action': 'login',
            '__cls': True
        }
        ret = self.json_patch('/api/user', data=data).json
        pprint(ret)
        assert ret['success']
        return ret

    def logout(self):
        ret = self.client.get('/api/logout', follow_redirects=True)
        assert ret.json['access_denied']
        return ret.json
