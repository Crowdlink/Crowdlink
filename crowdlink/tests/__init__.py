import decorator
import crowdlink
import json
import logging
import sys
import os

from pprint import pprint
from flask.ext.testing import TestCase
from flask.ext.login import login_user, logout_user
from crowdlink.util import provision
from crowdlink import root
from crowdlink.models import User


def login_required(username='crowdlink', password='testing'):
    """ Decorator that logs in the user under a request context as well as a
    testing cleint """
    def login_required(func, self, *args, **kwargs):
        self.user = self.db.session.query(User).filter_by(username=username).one()
        self.login(username, password)['user']
        login_user(self.user)
        try:
            func(self)
        except AssertionError as e:
            self.db.session.rollback()
            self.logout()
            raise
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
        try:
            f(self)
        except AssertionError:
            self.db.session.rollback()
            logout_user()
            raise
        logout_user()

    return decorator.decorator(login_required_ctx)


class BaseTest(TestCase):
    def json_post(self, url, data):
        return self.client.post(
            url, data=json.dumps(data), content_type='application/json')

    def json_get(self, url, data):
        return self.client.get(
            url, query_string=data, content_type='application/json')

    def json_put(self, url, data):
        return self.client.put(
            url, data=json.dumps(data), content_type='application/json')

    def create_app(self):
        app = crowdlink.create_app()
        app.config['TESTING'] = True
        app.config.from_pyfile('../testing.cfg')
        # Remove flasks stderr handler, replace with stdout so nose can
        # capture properly
        del app.logger.handlers[0]
        with app.app_context():
            self.db = crowdlink.db
            #self.db.drop_all()
            #self.db.create_all()
            #provision()
            os.system("psql -U crowdlink -h localhost crowdlink_testing -f " + root + "/assets/test_provision.sql > /dev/null 2>&1")
        return app

    def login(self, username, password):
        data = {
            'username': username,
            'password': password
        }
        ret = self.json_post('/api/login', data=data).json
        assert ret['success']
        return ret

    def logout(self):
        ret = self.client.get('/api/logout', follow_redirects=True)
        assert ret.json['access_denied']
        return ret.json

