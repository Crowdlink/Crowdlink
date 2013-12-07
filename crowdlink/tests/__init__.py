import decorator
import crowdlink
import json

from pprint import pprint
from flask.ext.testing import TestCase
from crowdlink.util import provision

@decorator.decorator
def login_required(func, self, username='crowdlink', password='testing'):
    self.user = self.login(username, password)['user']
    func(self)
    self.logout()

class BaseTest(TestCase):
    def json_post(self, url, data):
        return self.client.post(
            url, data=json.dumps(data), content_type='application/json')

    def json_get(self, url, data):
        return self.client.get(
            url, query_string=data, content_type='application/json')

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
        pprint(ret)
        assert ret['success']
        return ret

    def logout(self):
        ret = self.client.get('/api/logout', follow_redirects=True)
        assert ret.json['access_denied']
        return ret.json

