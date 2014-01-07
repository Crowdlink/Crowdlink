from flask.ext.login import current_user
from pprint import pprint
from copy import copy

from crowdlink.tests import BaseTest, login_required_ctx
from crowdlink.models import Issue, Project, Solution, Email, User, Thing
from crowdlink.fin_models import Earmark
import crowdlink.log_models as log_models

import datetime


class EarmarkTests(BaseTest):
    """ Earmark internal API """
    def last_log(self, typ):
        typ = getattr(log_models, typ.title() + 'Log')
        return typ.query.order_by(typ.id.desc()).first()

    @login_required_ctx('scrappy')
    def test_earmark_creation_failure(self):
        """ will it stop us from creating an earmark on the wrong object """
        lst = [User, Thing]
        for obj in lst:
            obj_inst = self.db.session.query(obj).first()
            with self.assertRaises(AttributeError):
                Earmark.create(obj_inst, 100)

    @login_required_ctx('scrappy')
    def test_earmark_creation(self):
        """ can we create an earmark"""
        lst = [Issue, Project, Solution]
        for obj in lst:
            obj_inst = self.db.session.query(obj).first()
            prev = copy(self.user.available_balance)
            mark = Earmark.create(obj_inst, 100)
            self.db.session.refresh(mark)
            self.db.session.refresh(self.user)
            assert isinstance(mark.thing, obj)
            assert mark.amount != 100
            assert mark.fee >= 1
            assert not mark.frozen
            assert not mark.disputed
            assert not mark.closed
            assert not mark.matured
            assert self.user.available_balance == prev - 100
            ll = self.last_log('Earmark')
            assert ll.item_id == mark.id
            assert ll.actor_id == self.user.id
            assert ll.action == 'create'


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
        print email.to_dict()
        assert email.activated is True
        assert email.activate_hash is None
        assert email.activate_gen is None


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
        assert ret['success'] is False
        assert 'cred' in ret['message']
        ret = User.login(identifier='velma')
        assert ret['success'] is False
        assert 'cred' in ret['message']
        ret = User.login(identifier='velma', password='testing')
        assert current_user == user
