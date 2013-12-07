import crowdlink
import json

from crowdlink.tests import BaseTest, login_required
from pprint import pprint


class APITests(BaseTest):
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

    def test_project_400(self):
        self.assert400(self.json_get('/api/project', {}))

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
        assert self.json_post(
            '/api/user/check', {'value': 'crowdlink'}).json['taken']
        assert self.json_post(
            '/api/user/check', {'value': 'this_doens'}).json['taken'] is False
        self.assert400(self.json_post('/api/user/check', {}))

    def test_check_email(self):
        assert self.json_post(
            '/api/email/check',
            {'value': 'support@crowdlink.com'}).json['taken']
        assert self.json_post(
            '/api/email/check',
            {'value': 'dflgj@dsflkjg.com'}).json['taken'] is False
        self.assert400(self.json_post('/api/email/check', {}))

    @login_required
    def test_check_purl_key(self):
        assert self.json_post(
            '/api/purl_key/check',
            {'value': 'crowdlink'}).json['taken']
        assert self.json_post(
            '/api/purl_key/check',
            {'value': 'dsflgjsdf;lgjksdfg;lk'}).json['taken'] is False
        self.assert400(self.json_post('/api/purl_key/check', {}))

    # Test all the form checks
    # =========================================================================

    def test_login(self):
        self.login('crowdlink', 'testing')
        self.logout()
