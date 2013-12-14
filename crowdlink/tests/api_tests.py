import crowdlink
import json

from crowdlink.tests import BaseTest, login_required, login_required_ctx
from crowdlink.models import Issue, Project, Solution, User
from crowdlink.fin_models import Charge

from pprint import pprint
from flask.ext.login import current_user


class APITests(BaseTest):
    @login_required
    def test_voting(self):
        """ can i vote on an issue/project/solution? """
        lst = [(Issue, 'issue'),
               (Project, 'project'),
               (Solution, 'solution')]
        for cls, key in lst:
            print "Voting for " + key
            obj = self.db.session.query(cls).first()
            res = self.json_put('/api/' + key,
                                {'id': obj.id,
                                'vote_status': True}).json
            assert res['success']
            res = self.json_put('/api/' + key,
                                {'id': obj.id,
                                'vote_status': True}).json
            assert res['success']
            res = self.json_put('/api/' + key,
                                {'id': obj.id,
                                'vote_status': False}).json
            assert res['success']
            res = self.json_put('/api/' + key,
                                {'id': obj.id,
                                'vote_status': False}).json
            assert res['success']

    @login_required
    def test_subscribe(self):
        """ can i subscribe to an issue/project/user/solution? """
        lst = [(Issue, 'issue'),
               (Project, 'project'),
               (Solution, 'solution'),
               (User, 'user')]
        for cls, key in lst:
            print "Subscribing for " + key
            obj = self.db.session.query(cls).first()
            res = self.json_put('/api/' + key,
                                {'id': obj.id,
                                'subscribed': True}).json
            assert res['success']
            res = self.json_put('/api/' + key,
                                {'id': obj.id,
                                'subscribed': True}).json
            assert res['success']
            res = self.json_put('/api/' + key,
                                {'id': obj.id,
                                'subscribed': False}).json
            assert res['success']
            res = self.json_put('/api/' + key,
                                {'id': obj.id,
                                'subscribed': False}).json
            assert res['success']

    # Issue api views
    # =========================================================================
    def test_issue(self):
        """ test access by id or composite keys """
        first_issue = self.db.session.query(Issue).first()
        qs = {'id': first_issue.id, 'join_prof': 'standard_join'}
        res = self.json_get('/api/issue', data=qs).json
        pprint(res)
        issue = res['issue']
        assert 'desc' in issue
        assert 'title' in issue
        assert issue['vote_status'] is None  # attribute for anonymous
        assert res['success']

        # now login
        self.login('crowdlink', 'testing')
        qs = {'id': first_issue.id, 'join_prof': 'standard_join'}
        res = self.json_get('/api/issue', data=qs).json
        pprint(res)
        assert res['issue']['vote_status'] is False  # difference from above

    def test_issue_400(self):
        self.assert400(self.json_get('/api/issue', {}))

    def test_issue_404(self):
        self.assert404(self.json_get('/api/issue',
                                     {'id': 12,
                                      'join_prof': 'standard_join'}))

    def test_issue_403(self):
        issue = self.db.session.query(Issue).first()
        self.assert403(self.json_put('/api/issue',
                                     {'id': issue.id,
                                      'url_key': 'crap'}))

    # Project api views
    # =========================================================================
    def test_project(self):
        qs = {'username': 'crowdlink',
              'url_key': 'crowdlink',
              'join_prof': 'standard_join'}
        res = self.json_get('/api/project', qs).json
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
        res = self.json_get('/api/project', qs).json
        assert type(res['public_events']) == list

    def test_project_cant_edit(self):
        """ ensure non-priv can't edit project """
        first_project = self.db.session.query(Project).first()
        qs = {'id': first_project.id,
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
        res = self.json_get('/api/user', qs).json
        pprint(res)
        user = res['user']
        assert res['success']
        assert 'gh_linked' in user
        assert type(user['id']) == int
        assert user['username'] == 'crowdlink'
        assert type(user['user_acl']) == dict
        assert '_password' not in user
        assert 'password' not in user
        assert user['get_abs_url'].startswith('/')

    def test_user_400(self):
        self.assert400(self.json_get('/api/user', {}))

    def test_explicit_user_denied(self):
        """ ensure that anonymous users can't access user data"""
        qs = {'id': 1,
              'join_prof': 'settings_join'}
        res = self.json_get('/api/user', qs)
        pprint(res.json)
        assert res.json['success'] is False
        self.assert403(res)

    def test_explicit_user(self):
        """ simple explicit id definition for user lookup """
        data = {'id': 1,
              'join_prof': 'page_join'}
        res = self.json_get('/api/user', data).json
        pprint(res)
        user = res['user']
        assert res['success']
        assert user['username'] == 'crowdlink'
        assert '_password' not in user
        assert 'password' not in user
        assert user['username']
        assert type(user['public_events']) == list

    @login_required
    def test_user_page(self):
        """ page_join user test """
        qs = {'join_prof': 'page_join'}
        res = self.json_get('/api/user', qs).json
        pprint(res)
        user = res['user']
        assert res['success']
        assert type(user['public_events']) == list

    @login_required
    def test_user_home(self):
        """ home_join user test """
        qs = {'join_prof': 'home_join'}
        res = self.json_get('/api/user', qs).json
        pprint(res)
        user = res['user']
        assert res['success']
        assert type(user['events']) == list

    # Earmark api
    # =========================================================================
    @login_required
    def test_earmark_create(self):
        """ test creation """
        current_user.available_balance = 10000
        current_user.save()
        # create a mock Charge
        new_charge = Charge(amount=10000,
                           remaining=10000,
                           livemode=False,
                           last_four=1234,
                           user_id=self.user.id).safe_save()
        first_issue = self.db.session.query(Issue).first()
        qs = {'amount': 1000, 'id': first_issue.id}
        res = self.json_post('/api/earmark', qs).json
        assert res['success']
        assert isinstance(res['earmark']['amount'], int)
        assert res['earmark']['id'] > 0
        assert res['earmark']['thing_id'] > 0
        pprint(res)

        # get the earmark we just inserted
        qs = {'id': res['earmark']['id']}
        res2 = self.json_get('/api/earmark', qs).json
        assert res2['earmarks'][0]['id'] == res['earmark']['id']
        assert res2['earmarks'][0]['thing_id'] == res['earmark']['thing_id']
        assert isinstance(res2['earmarks'][0]['amount'], int)
        assert res2['success']
        pprint(res2)

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
