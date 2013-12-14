from flask import session, current_app, flash
from flask.ext.login import current_user

from . import db, github
from .util import inherit_lst
from .acl import (issue_acl, project_acl, solution_acl, user_acl,
                  transaction_acl, earmark_acl, recipient_acl, transfer_acl)
from .models import base, BaseMapper, PrivateMixin

from flask.ext.sqlalchemy import (_BoundDeclarativeMeta, BaseQuery,
                                  _QueryProperty)
from sqlalchemy.dialects.postgresql import HSTORE, ARRAY
from sqlalchemy.types import TypeDecorator, TEXT
from sqlalchemy import event

from enum import Enum

import valideer as V
import stripe
import sqlalchemy
import urllib
import datetime


class Earmark(base):
    """ Represents a users intent to give money to another member. """
    StatusVals = Enum('Created', 'Ready', 'Assigned', 'Disputed', 'Frozen')
    _status = db.Column(db.Integer, default=StatusVals.Created.index)
    matured = db.Column(db.Boolean, default=False)
    cleared = db.Column(db.Boolean, default=False)

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Integer)
    fee = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # Person who sent the money
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    sender = db.relationship('User', foreign_keys=[sender_id])
    # The object the earmark is assigned to
    thing_id = db.Column(db.Integer, db.ForeignKey('thing.id'))
    thing = db.relationship('Thing', backref='earmarks')

    standard_join = ['status',
                     'StatusVals',
                     'created_at',
                     '-stripe_created_at']

    acl = earmark_acl

    def clear(self):
        """ Removes the funds from the sender and delivers them to destination
        users """
        if self.matured and not self.cleared:
            # lock the user object, decrement their current balance
            db.session.refresh(self.sender, lockmode='update')
            self.sender.current_balance -= self.amount
            self.cleared = True
            # now give the money to the recipients
            db.session.commit()
        else:
            raise AttributeError

    def roles(self, user=None):
        """ Logic to determin what auth roles a user gets """
        if not user:
            user = current_user

        # XXX : To be implemented
        #if self.reciever_id == getattr(user, 'id', None):
        #    return ['reciever']

        if self.sender_id == getattr(user, 'id', None):
            return ['sender']

        if user.is_anonymous():
            return ['anonymous']
        else:
            return ['user']

    @classmethod
    def create(cls, thing_id, amount, user=None):
        fee = round(amount*current_app.config['TRANSFER_FEE'])
        mark = Earmark(
            amount=amount-fee,
            fee=fee,
            sender=user,
            thing_id=thing_id,
        )
        # decrement their available balance along with creation of the object
        db.session.refresh(user, lockmode='update')
        user.available_balance -= amount
        db.session.add(mark)
        db.session.commit()
        return mark

    @property
    def status(self):
        return self.StatusVals[self._status]


class Recipient(PrivateMixin, base):
    id = db.Column(db.Integer, primary_key=True)
    stripe_id = db.Column(db.String, unique=True)
    name = db.Column(db.String)
    verified = db.Column(db.Boolean)
    livemode = db.Column(db.Boolean)
    last_four = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    stripe_created_at = db.Column(db.DateTime)
    user = db.relationship('User')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    standard_join = ['created_at',
                     'last_four',
                     'verified',
                     'name',
                     'created_at',
                     '-stripe_created_at']

    acl = recipient_acl

    @property
    def status(self):
        return self.StatusVals[self._status]


class Transfer(PrivateMixin, base):
    """ An object mirroring a stripe transfer """

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    stripe_id = db.Column(db.String, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', foreign_keys=[user_id])
    StatusVals = Enum('Pending', 'Cleared')
    _status = db.Column(db.Integer, default=StatusVals.Pending.index)

    standard_join = ['status',
                     'StatusVals',
                     '_status',
                     'created_at',
                     'amount',
                     '-stripe_created_at']

    acl = transfer_acl

    @property
    def status(self):
        return self.StatusVals[self._status]


class Transaction(PrivateMixin, base):
    StatusVals = Enum('Pending', 'Cleared')
    _status = db.Column(db.Integer, default=StatusVals.Pending.index)

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Integer)
    remaining = db.Column(db.Integer)
    livemode = db.Column(db.Boolean)
    stripe_id = db.Column(db.String, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    stripe_created_at = db.Column(db.DateTime)
    last_four = db.Column(db.Integer)
    user = db.relationship('User')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    standard_join = ['status',
                     'StatusVals',
                     'created_at',
                     '-stripe_created_at']

    acl = transaction_acl

    @property
    def status(self):
        return self.StatusVals[self._status]

    def get_stripe_charge(self):
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        return stripe.Charge.retrieve(self.stripe_id)

    @classmethod
    def create(cls, token, amount, user=None):
        card = token['id']
        livemode = token['livemode']

        retval = stripe.Charge.create(
            amount=amount,
            currency="usd",
            card=card)

        if retval['paid']:
            status = Transaction.StatusVals.Cleared.index
        else:
            status = Transaction.StatusVals.Pending.index

        trans = cls(
            amount=amount,
            remaining=amount,
            livemode=livemode,
            stripe_id=retval['id'],
            stripe_created_at=datetime.datetime.fromtimestamp(retval['created']),
            user=user,
            _status=status,
            last_four=retval['card']['last4']
        ).save()

        return trans
