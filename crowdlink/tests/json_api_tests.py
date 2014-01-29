import crowdlink
import json

from crowdlink.tests import ThinTest
from crowdlink.models import Issue, Project, Solution, User, Comment

from pprint import pprint
from lever import jsonize
from flask.ext.login import current_user


class TestMixinsJSONAPI(ThinTest):
    def test_voting(self):
        """ can i vote on an issue/project/solution? """
        user = self.new_user(login_ctx=True)
        self.provision_many(user=user)
        lst = [(Issue, 'issue'),
               (Project, 'project'),
               (Solution, 'solution')]
        for cls, key in lst:
            obj = self.db.session.query(cls).first()
            for val in [True, True, False, False]:
                self.put('/api/' + key, 200, params={'id': obj.id, 'vote_status': val})

    def test_voting_fail(self):
        """ can i vote on an user/comment? """
        user = self.new_user(login_ctx=True)
        self.provision_many(user=user)
        lst = [(User, 'user'),
               (Comment, 'comment')]
        for cls, key in lst:
            obj = self.db.session.query(cls).first()
            for val in [True, False]:
                self.put('/api/' + key, 403, params={'id': obj.id, 'vote_status': val})

    def test_subscribe(self):
        """ can i subscribe to an issue/project/user/solution? """
        user = self.new_user(login_ctx=True)
        self.provision_many(user=user)
        lst = [(Issue, 'issue'),
               (Project, 'project'),
               (Solution, 'solution'),
               (User, 'user')]
        for cls, key in lst:
            obj = self.db.session.query(cls).first()
            for val in [True, True, False, False]:
                self.put('/api/' + key, 200, params={'id': obj.id, 'subscribed': val})

    def test_subscribe_fail(self):
        """ can i not subscribe to a comment? """
        user = self.new_user(login_ctx=True)
        self.provision_many(user=user)
        lst = [(Comment, 'comment')]
        for cls, key in lst:
            obj = self.db.session.query(cls).first()
            for val in [True, False]:
                self.put('/api/' + key, 403, params={'id': obj.id, 'subscribed': val})

    def test_report(self):
        """ can i report an issue/project/user/solution/comment? """
        user = self.new_user(login_ctx=True)
        self.provision_many(user=user)
        lst = [(Issue, 'issue'),
               (Project, 'project'),
               (Solution, 'solution'),
               (Comment, 'comment'),
               (User, 'user')]
        for cls, key in lst:
            obj = self.db.session.query(cls).first()
            for val in ['Spam', 'Testing', False, True, 12]:
                self.put('/api/' + key, 200, params={'id': obj.id, 'report_status': val})

class TestAnonymousPermissions(ThinTest):
    def test_create_user(self):
        """ can i create a new user with the API? """
        data = {'username': 'doesnt_exist',
                'password': 'testing',
                'email_address': 'testing@something.com'}
        self.post('/api/user', 200, params=data)

    def change_attr_fails(self):
        """ Test changing attributes we shouldn't be able to as an anonymous
        user. Runs through and tries to change every column name on each listed
        model and ensures we get a 403 """
        lst = [(Issue, 'issue'),
               (Project, 'project'),
               (Solution, 'solution'),
               (Comment, 'comment'),
               (User, 'user')]
        for cls, url_key in lst:
            obj = self.db.session.query(cls).first()
            values = jsonize(obj, obj.to_dict().keys(), raw=True)
            for key, val in values.items():
                if key == 'id' or 'event' in key:
                    continue
                self.put('/api/' + url_key, 403, params={'id': obj.id, key: val})

    def test_change_attr_anon_failed(self):
        """ try to change as anonymous """
        user = self.new_user()
        self.provision_many(user=user)
        self.change_attr_fails()

    def test_change_attr_not_owner_fails(self):
        """ regular users who don't own the objects can't change things, make
        sure this is true """
        fred = self.new_user(active=True, username='fred')
        self.provision_many(user=fred)
        self.new_user(login_ctx=True)
        self.change_attr_fails()

    def test_change_attr_user_no_active_fails(self):
        """ try to change things as unactivated user """
        fred = self.new_user(active=True, username='fred')
        self.provision_many(user=fred)
        self.new_user(login_ctx=True, active=False)
        self.change_attr_fails()
