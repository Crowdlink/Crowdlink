from flask.ext.login import current_user, logout_user
from pprint import pprint

from crowdlink.tests import BaseTest, ThinTest
from crowdlink.models import Issue, Project, Solution, Email, User, Thing
from crowdlink.mail import TestEmail

import datetime


class ProjectTests(ThinTest):
    """ Project internal API """

    def test_check_taken(self):
        """ check taken project_url_keys works as expected """
        # TODO: XXX: Will need to be changed when case bug is fixed
        user = self.new_user(login=True)
        self.provision_project(user=user, url_key='mystery-inc')
        self.provision_project(user=user)
        tests = [('crowdlink', True),
                 ('Crowdlink', False),
                 ('MYstery-inc', False)]
        for url_key, result in tests:
            assert Project.check_taken(url_key)['taken'] is result


class EmailTests(ThinTest):
    """ Email internal API """
    def test_email_send(self):
        self.new_user(login=True)
        assert TestEmail().send(self.app.config['email_test_address'],
                                force_send=False)

    def test_activate_email(self):
        user = self.new_user(login=True)
        addr = "this.test.unique@testingdsflkjgsdfg.com"
        email = Email(user=user,
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
        self.new_user()
        tests = [('velma@crowdlink.io', True),
                 ('velmA@crowdlink.io', False),
                 ('dsfglkjdsfg@dflj.com', False),
                 ('velma@CROWDLINK.io', False)]
        for email, result in tests:
            assert Email.check_taken(email)['taken'] is result


class UserTests(ThinTest):
    def test_recover_user(self):
        # fake the sending of the recover email
        user = self.new_user()
        User.send_recover(user.username, force_send=False)
        self.db.session.commit()
        assert user.recover_hash is not None
        assert user.recover_gen is not None

        # now actually run the recover function
        user.recover(user.recover_hash, 'new_password')
        self.db.session.commit()
        # ensure we got logged in
        assert current_user == user

    def test_login(self):
        user = self.new_user()
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
        self.new_user(username='crowdlink')
        tests = [('crowdlink', True),
                 ('CROWdlink', True),
                 ('dsfglkj', False)]
        for username, result in tests:
            assert User.check_taken(username)['taken'] is result
