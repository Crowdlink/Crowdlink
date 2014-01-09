from flask.ext.login import current_user, logout_user
from pprint import pprint
from copy import copy
from sqlalchemy import or_

from crowdlink.tests import BaseTest, login_required_ctx, stripe_bank_token_real
from crowdlink.models import Issue, Project, Solution, Email, User, Thing
from crowdlink.fin_models import (Earmark, Recipient, Transfer, Mark)
import crowdlink.log_models as log_models

import datetime


class FinTest(BaseTest):
    event_extra = dict(event_blob={'test': {'this': 'works'}},
                       event_data={'test': 'this'})

    def last_log(self, typ):
        typ = getattr(log_models, typ.title() + 'Log')
        return typ.query.order_by(typ.id.desc()).first()

    def assert_log(self, ll):
        assert ll.data['test'] == 'this'
        assert ll.blob['test']['this'] == 'works'
        assert ll.actor_id == self.user.id


class EarmarkTests(FinTest):
    """ Earmark internal API """

    def get_uncleared(self):
        """ grab an earmark that is completely ready for being cleared
        status wise """
        marks = Earmark.query.filter_by(user=self.user,
                                        matured=True,
                                        frozen=False,
                                        disputed=False,
                                        closed=False,
                                        cleared=False,
                                        status='Assigned')
        # A sloppy fix to finding a completed issue mark...
        proper_mark = None
        for mark in marks:
            print mark
            if mark.thing.status == 'Completed':
                proper_mark = mark
                break
        assert proper_mark is not None
        return proper_mark

    def get_unassigned(self):
        return Earmark.query.filter_by(user=self.user,
                                       matured=True,
                                       frozen=False,
                                       disputed=False,
                                       closed=False,
                                       cleared=False,
                                       status='Created').first()

    @login_required_ctx('scrappy')
    def test_earmark_creation_failure(self):
        """ will it stop us from creating an earmark on the wrong object """
        lst = [User, Thing]
        for obj in lst:
            obj_inst = self.db.session.query(obj).first()
            with self.assertRaises(AttributeError):
                Earmark.create(obj_inst, 100)

    @login_required_ctx('shaggy')
    def test_earmark_maturation(self):
        """ does maturing an unmature earmark work properly? """
        mark = Earmark.query.filter_by(user=self.user, matured=False).first()
        mark.mature(**self.event_extra)
        self.db.session.commit()
        self.db.session.refresh(mark)
        assert mark.matured is True
        ll = self.last_log('Earmark')
        assert ll.item_id == mark.id
        assert ll.action == 'mature'
        self.assert_log(ll)

    @login_required_ctx('scrappy')
    def test_earmark_creation(self):
        """ can we create an earmark"""
        lst = [Issue, Project, Solution]
        for obj in lst:
            obj_inst = self.db.session.query(obj).first()
            prev = copy(self.user.available_balance)
            mark = Earmark.create(obj_inst, 100, **self.event_extra)
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
            assert ll.action == 'create'
            self.assert_log(ll)

    @login_required_ctx('shaggy')
    def test_earmark_assignment(self):
        """ assignment works properly? """
        users = User.query.filter(or_(User.username == 'scrappy',
                                      User.username == 'scooby')).all()
        mark = self.get_unassigned()
        mark.assign([(users[0], 50), (users[1], 50)], **self.event_extra)
        self.db.session.commit()
        self.db.session.refresh(mark)
        ll = self.last_log('Earmark')
        assert ll.item_id == mark.id
        assert ll.action == 'assign'
        self.assert_log(ll)

    @login_required_ctx('shaggy')
    def test_earmark_clearing(self):
        """ clearing work properly? create marks, etc """
        mark = self.get_uncleared()
        mark.clear(**self.event_extra)
        self.db.session.commit()
        self.db.session.refresh(mark)
        assert mark.cleared is True
        assert not mark.frozen
        assert not mark.disputed
        assert not mark.closed
        assert mark.matured
        ll = self.last_log('Earmark')
        assert ll.item_id == mark.id
        assert ll.action == 'clear'
        self.assert_log(ll)


class MarkTests(FinTest):
    @login_required_ctx('scooby')
    def test_mark_clear(self):
        """ can we clear a Mark """
        mark = Mark.query.filter_by(user=self.user, cleared=False).first()
        prev_avail = self.user.available_balance
        prev_total = self.user.current_balance
        prev_marks = self.user.available_marks
        print ("Prev Marks: {}\nPrev Total: {}\nPrev Avail: {}"
               .format(prev_marks, prev_total, prev_avail))
        assert mark
        mark.clear()
        self.db.session.commit()
        self.db.session.refresh(self.user)
        assert self.user.available_balance == (prev_avail + mark.amount)
        assert self.user.current_balance == (prev_total + mark.amount)
        assert self.user.available_marks == (prev_marks + mark.amount)
        ll = self.last_log('Mark')
        assert ll.item_id == mark.id
        assert ll.actor_id == self.user.id
        assert ll.action == 'clear'


class RecipientTests(BaseTest):
    @login_required_ctx('scrappy')
    def test_recipient_create(self):
        recp = Recipient.create(stripe_bank_token_real(),
                                "Scrappy Do",
                                False,
                                tax_id="000000000")
        self.db.session.refresh(recp)
        assert recp.livemode is False
        assert recp.verified is False
        assert recp.name == "Scrappy Do"
        assert isinstance(recp.last_four, int)
        assert recp.user == current_user
        assert isinstance(recp.stripe_created_at, datetime.datetime)


class TransferTests(BaseTest):
    @login_required_ctx('scooby')
    def test_transfer_create(self):
        tran = Transfer.create(self.user.available_marks,
                               self.user.recipients[0])
        self.db.session.refresh(tran)
        assert tran.livemode is False
        assert tran.user == current_user
        assert isinstance(tran.stripe_created_at, datetime.datetime)
        assert isinstance(tran.created_at, datetime.datetime)


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
        print user.to_dict()
        assert user.username == 'testing_one'
        assert user.password != 'testing'
        Email.query.filter_by(address='testing@crowdlink.io').one()
