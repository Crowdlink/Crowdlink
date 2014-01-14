from flask.ext.login import current_user, logout_user
from pprint import pprint
from copy import copy
from sqlalchemy import or_

from crowdlink.tests import BaseTest, login_required_ctx
from crowdlink.models import Issue, Project, Solution, Email, User, Thing

import datetime


class ProjectTests(BaseTest):
    """ Project internal API """

    @login_required_ctx('crowdlink')
    def test_check_taken(self):
        """ ensure registration works, and lowercases names """
        # TODO: XXX: Will need to be changed when case bug is fixed
        tests = [('crowdlink', True),
                 ('Crowdlink', False),
                 ('MYstery-inc', False)]
        for url_key, result in tests:
            assert Project.check_taken(url_key)['taken'] is result


class EmailTests(BaseTest):
    """ Email internal API """

    @login_required_ctx()
    def test_activate_email(self):
        addr = "this.test.unique@testingdsflkjgsdfg.com"
        email = Email(user=self.user,
                      address=addr,
                      primary=False).save()
        email.send_activation(force_send=False)
        self.db.session.commit()
        assert isinstance(email.activate_gen, datetime.datetime)

        Email.activate_email(email.address, email.activate_hash)
        self.db.session.commit()
        self.db.session.refresh(email)
        print(email.to_dict())
        assert email.activated is True
        assert email.activate_hash is None
        assert email.activate_gen is None

    def test_check_taken(self):
        """ ensure registration works, and lowercases names """
        # TODO: XXX: Will need to be changed when case bug is fixed
        tests = [('velma@crowdlink.io', True),
                 ('velmA@crowdlink.io', False),
                 ('dsfglkjdsfg@dflj.com', False),
                 ('velma@CROWDLINK.io', False)]
        for email, result in tests:
            assert Email.check_taken(email)['taken'] is result


class UserTests(BaseTest):
    def test_recover_user(self):
        # fake the sending of the recover email
        User.send_recover('velma', force_send=False)
        self.db.session.commit()
        user = User.query.filter_by(username='velma').one()
        assert user.recover_hash is not None
        assert user.recover_gen is not None

        # now actually run the recover function
        user.recover(user.recover_hash, 'new_password')
        self.db.session.commit()
        assert current_user == user

    def test_login(self):
        user = User.query.filter_by(username='velma').one()
        ret = User.login()
        # make sure message is uniform with no params, or wrong params...
        assert ret['success'] is False
        assert 'cred' in ret['message']
        ret = User.login(identifier='velma')
        assert ret['success'] is False
        assert 'cred' in ret['message']
        # regular cred works fine
        ret = User.login(identifier='velma', password='testing')
        assert current_user == user
        logout_user()
        # diff case username works!
        ret = User.login(identifier='VELMA', password='testing')
        assert current_user == user
        logout_user()
        # diff case password breaks
        ret = User.login(identifier='VELMA', password='Testing')
        assert not ret

    def test_register(self):
        """ ensure registration works, and lowercases names """
        user = User.create('Testing_one',
                           'testing',
                           'testing@crowdlink.io',
                           force_send=False)
        self.db.session.commit()
        self.db.session.refresh(user)
        print(user.to_dict())
        assert user.username == 'testing_one'
        assert user.password != 'testing'
        Email.query.filter_by(address='testing@crowdlink.io').one()

    def test_check_taken(self):
        """ ensure registration works, and lowercases names """
        tests = [('crowdlink', True),
                 ('CROWdlink', True),
                 ('dsfglkj', False)]
        for username, result in tests:
            assert User.check_taken(username)['taken'] is result
