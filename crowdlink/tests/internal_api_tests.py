from crowdlink.tests import BaseTest, login_required_ctx
from crowdlink.models import Issue, Project, Solution, Email, User, Thing
from crowdlink.fin_models import Earmark
import crowdlink.log_models as log_models
from pprint import pprint

import datetime
from copy import copy


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
        hash, date = email.send_activation(force=False)
        assert isinstance(date, datetime.datetime)

        Email.activate_email(addr, hash)
        self.db.session.commit()
        self.db.session.refresh(email)
        print email.to_dict()
        assert email.verified is True
        assert email.activate_hash is None
        assert email.hash_gen is None
