import os
import crowdlink
import unittest
import json
import tempfile
import logging
import sys

from pprint import pprint
from crowdlink.util import provision
from flask.ext.testing import TestCase

class APITests(TestCase):

    def create_app(self):
        app = crowdlink.create_app()
        app.config['TESTING'] = True
        app.config.from_pyfile('../testing.cfg')
        app.logger.addHandler(logging.StreamHandler(sys.stdout))
        # Remove flasks stderr handler, replace with stdout so nose can
        # capture properly
        del app.logger.handlers[0]
        with app.app_context():
            self.db = crowdlink.db
            self.db.drop_all()
            self.db.create_all()
            provision()
        return app

    def json_post(self, url, data):
        return self.client.post(url, data=json.dumps(data), content_type='application/json')

    def login(self, username, password):
        data = {
            'username': username,
            'password': password
        }
        ret = self.json_post('/api/login', data=data)
        pprint(ret.json)
        assert ret.json['success']
        return ret.json

    def logout(self):
        ret = self.client.get('/api/logout', follow_redirects=True)
        assert ret.json['access_denied']
        return ret.json

    def test_home(self):
        rv = self.client.get('/')

    def test_user(self):
        res = self.client.get('/api/user?username=crowdlink').json
        assert res['username'] == 'crowdlink'
        assert '_password' not in res
        assert 'password' not in res

    def test_project(self):
        qs = {'username': 'crowdlink',
              'url_key': 'crowdlink',
              'join_prof': 'standard_join'}
        res = self.client.get('/api/project',
                              query_string=qs).json
        pprint(res)
        assert type(res['created_at']) == int
        assert type(res['id']) == int
        assert type(res['user_acl']) == dict
        assert res['get_abs_url'].startswith('/')
        assert 'desc' in res
        assert 'name' in res
        assert 'website' in res
        assert res['success']

    def test_project_page(self):
        qs = {'username': 'crowdlink',
              'url_key': 'crowdlink',
              'join_prof': 'page_join'}
        res = self.client.get('/api/project',
                              query_string=qs).json
        assert type(res['events']) == list

    def test_login(self):
        self.login('crowdlink', 'testing')
        self.logout()
