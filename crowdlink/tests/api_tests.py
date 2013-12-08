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
        res = self.json_get('/api/project', data=qs).json
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

    def test_project_cant_edit(self):
        """ ensure non-priv can't edit project """
        qs = {'id': 1,
              'url_key': 'crowdlink2'}
        res = self.json_put('/api/project', data=qs)
        self.assert403(res)

    def test_project_cant_create(self):
        """ ensure non-priv can't create project """
        qs = {'url_key': 'crowdlink2'}
        res = self.json_post('/api/project', data=qs)
        self.assert403(res)

    # User api
    # =========================================================================
    def test_user(self):
        """ Test anonymous standard join get """
        qs = {'username': 'crowdlink'}
        res = self.client.get('/api/user',
                              query_string=qs).json
        pprint(res)
        user = res['user']
        assert res['success']
        assert 'gh_linked' in user
        assert type(user['id']) == int
        assert type(user['user_acl']) == dict
        assert user['get_abs_url'].startswith('/')

    def test_user_400(self):
        self.assert400(self.json_get('/api/user', {}))

    def test_explicit_user_denied(self):
        """ ensure that anonymous users can't access user data"""
        qs = {'id': 1,
              'join_prof': 'settings_join'}
        res = self.client.get('/api/user', query_string=qs)
        pprint(res.json)
        assert res.json['success'] is False
        self.assert403(res)

    def test_explicit_user(self):
        """ simple explicit id definition for user lookup """
        qs = {'id': 1,
              'join_prof': 'page_join'}
        res = self.client.get('/api/user', query_string=qs).json
        pprint(res)
        user = res['user']
        assert res['success']
        assert res['user']['username']
        assert type(user['events']) == list

    @login_required
    def test_user_page(self):
        """ page_join user test """
        qs = {'join_prof': 'page_join'}
        res = self.client.get('/api/user', query_string=qs).json
        pprint(res)
        user = res['user']
        assert res['success']
        assert type(user['public_events']) == list

    @login_required
    def test_user_home(self):
        """ home_join user test """
        qs = {'join_prof': 'home_join'}
        res = self.client.get('/api/user', query_string=qs).json
        pprint(res)
        user = res['user']
        assert res['success']
        assert type(user['events']) == list

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

    def test_login(self):
        self.login('crowdlink', 'testing')
        self.logout()
