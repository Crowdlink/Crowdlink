import os
import crowdlink
import unittest
import json
import tempfile
import decorator
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
        # Remove flasks stderr handler, replace with stdout so nose can
        # capture properly
        del app.logger.handlers[0]
        with app.app_context():
            self.db = crowdlink.db
            self.db.drop_all()
            self.db.create_all()
            provision()
        return app

    @decorator.decorator
    def login_required(func, username='crowdlink', password='testing'):
        def magic(self):
            self.login(username, password)
            self.func()
            self.logout()
        return magic

    def json_post(self, url, data):
        return self.client.post(url, data=json.dumps(data), content_type='application/json')

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

    def test_home(self):
        rv = self.client.get('/')

    def test_user(self):
        res = self.client.get('/api/user?username=crowdlink').json
        assert res['username'] == 'crowdlink'
        assert '_password' not in res
        assert 'password' not in res

    # Project api views
    # =========================================================================
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
        """ page_join project test """
        qs = {'username': 'crowdlink',
              'url_key': 'crowdlink',
              'join_prof': 'page_join'}
        res = self.client.get('/api/project',
                              query_string=qs).json
        assert type(res['events']) == list


    # Test all the form checks
    # =========================================================================
    def test_check_user(self):
        assert self.json_post('/api/user/check', {'value': 'crowdlink'}).json['taken']
        assert self.json_post('/api/user/check', {'value': 'this_doens'}).json['taken'] == False
        self.assert400(self.json_post('/api/user/check', {}))

    def test_check_email(self):
        assert self.json_post('/api/email/check',
                              {'value': 'support@crowdlink.com'}).json['taken']
        assert self.json_post('/api/email/check',
                              {'value': 'dflgj@dsflkjg.com'}).json['taken'] == False
        self.assert400(self.json_post('/api/email/check', {}))

    @login_required
    def test_check_purl_key(self):
        assert self.json_post('/api/purl_key/check',
                              {'value': 'crowdlink'}).json['taken']
        assert self.json_post('/api/purl_key/check',
                              {'value': 'dsflgjsdf;lgjksdfg;lk'}).json['taken'] == False
        self.assert400(self.json_post('/api/purl_key/check', {}))

    def test_login(self):
        self.login('crowdlink', 'testing')
        self.logout()
