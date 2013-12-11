import decorator
import crowdlink
import json

from pprint import pprint
from flask.ext.testing import TestCase
from flask.ext.login import login_user, logout_user
from crowdlink.util import provision
from crowdlink.models import User

@decorator.decorator
def login_required(func, self, username='crowdlink', password='testing'):
    self.user = self.login(username, password)['user']
    try:
        func(self)
    except AssertionError:
        self.db.session.rollback()
        self.logout()
        raise
    self.logout()

@decorator.decorator
def login_required_ctx(func, self, username='crowdlink'):
    self.user = self.db.session.query(User).filter_by(username=username).first()
    login_user(self.user)
    try:
        func(self)
    except AssertionError:
        self.db.session.rollback()
        logout_user()
        raise
    logout_user()


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
            self.db.drop_all()
            self.db.create_all()
            provision()
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

