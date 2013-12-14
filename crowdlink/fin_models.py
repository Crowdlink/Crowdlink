from flask import current_app
from flask.ext.login import current_user
from datetime import datetime
from sqlalchemy.schema import CheckConstraint
from enum import Enum

from . import db
from .acl import charge_acl, earmark_acl, recipient_acl, transfer_acl
from .models import base, PrivateMixin, StatusMixin
from .exc import FundingException

import stripe
import math
import itertools


class Source(base):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String, nullable=False)
    amount = db.Column(db.Integer, CheckConstraint('amount>0'), nullable=False)
    remaining = db.Column(db.Integer, nullable=False)
    cleared = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __mapper_args__ = {
        'polymorphic_identity': 'Source',
        'polymorphic_on': type
    }

    def clear(self):
        """ Pushes pending funds on through to the recipeint. Doesn't commit
        because it's intended to be called by the other methods """
        db.session.refresh(self.user, lockmode='update')
        self.user.available_balance += self.amount
        self.user.current_balance += self.amount
        self.cleared = True


class Charge(Source, PrivateMixin, base):
    StatusVals = Enum('Pending', 'Cleared')
    _status = db.Column(db.Integer,
                        default=StatusVals.Pending.index,
                        nullable=False)

    id = db.Column(db.Integer, db.ForeignKey('source.id'), primary_key=True)
    livemode = db.Column(db.Boolean, nullable=False)
    stripe_id = db.Column(db.String, unique=True, nullable=False)
    stripe_created_at = db.Column(db.DateTime, nullable=False)
    last_four = db.Column(db.Integer)
    user = db.relationship('User')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    __mapper_args__ = {'polymorphic_identity': 'Charge'}
    standard_join = ['status',
                     'StatusVals',
                     'created_at',
                     '-stripe_created_at']

    acl = charge_acl

    @property
    def status(self):
        return self.StatusVals[self._status]

    def get_stripe_charge(self):
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        return stripe.Charge.retrieve(self.stripe_id)

    @classmethod
    def create(cls, token, amount, user=None):
        if user is None:
            user = current_user

        card = token['id']
        livemode = token['livemode']

        retval = stripe.Charge.create(
            metadata={'username': user.username,
                      'userid': user.id},
            amount=amount,
            currency="usd",
            card=card)

        charge = cls(
            amount=amount,
            remaining=amount,
            livemode=livemode,
            stripe_id=retval['id'],
            stripe_created_at=datetime.fromtimestamp(retval['created']),
            user=user,
            last_four=retval['card']['last4']
        )

        if retval['paid']:
            charge._status = Charge.StatusVals.Cleared.index
            charge.clear()
        else:
            charge._status = Charge.StatusVals.Pending.index

        db.session.add(charge)
        db.session.commit()

        return charge


class Sink(base):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String, nullable=False)
    amount = db.Column(db.Integer, CheckConstraint('amount>0'), nullable=False)
    __mapper_args__ = {
        'polymorphic_identity': 'Sink',
        'polymorphic_on': type
    }


class Transfer(Sink, PrivateMixin, base):
    """ An object mirroring a stripe transfer """

    id = db.Column(db.Integer, db.ForeignKey('sink.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    stripe_id = db.Column(db.String, unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', foreign_keys=[user_id])
    __mapper_args__ = {'polymorphic_identity': 'Transfer'}

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

    @classmethod
    def create(cls, amount, recipient, user=None):
        if user is None:
            user = current_user

        # get a total amount of cleared marks available to fund this transfer
        total = sum([m.remaining for m in Mark.query.filter_by(user=user, cleared=True)])
        # run some safety checks
        if recipient.user != user or \
           total < amount:
            raise AttributeError

        db.session.rollback()  # for the nervous person
        # lock the user, this action takes money out of their account
        db.session.refresh(user, lockmode='update')
        retval = stripe.Transfer.create(
            bank_account=recipient['stripe_id'],
            amount=recipient['stripe_id'],
            metadata={'username': user.username,
                      'userid': user.id}
        )

        # create a new recipient in our db to reflect stripe
        trans = cls(
            livemode=retval['livemode'],
            stripe_id=retval['id'],
            stripe_created_at=datetime.fromtimestamp(retval['created']),
            user=user,
            last_four=retval['active_account']['last4'],
            verified=retval['active_account']['verified'],
            name=retval['name']
        )

        # process logic for pulling funds from required sources
        deduct_total = amount
        while deduct_total > 0:
            src = (Mark.query.
                   filter(Mark.remaining > 0).      # with a remaining balance
                   filter_by(cleared=True).         # that have cleared
                   order_by(Mark.created_at).       # order by the date
                   with_lockmode('update').first()) # lock the row from updates

            if src is None:  # if we're out of funding period
                db.session.rollback()
                raise FundingException

            if src.remaining >= deduct_total:
                src.remaining -= deduct_total
                deduct_total = 0
            else:
                deduct_total -= src.remaining
                src.remaining = 0

        user.available_balance -= amount
        user.current_balance -= amount

        db.session.add(trans)
        db.session.commit()

        return trans

    def clear(self):
        db.session.rollback()  # for the nervous person
        self.cleared = True
        self.user.current_balance -= self.amount
        db.session.commit()


class Earmark(StatusMixin, Sink, base):
    """ Represents a users intent to give money to another member. """
    # status information as it relates to the attached thing
    StatusVals = Enum('Created', 'Ready', 'Assigned', 'Disputed')
    _status = db.Column(db.Integer, default=StatusVals.Created.index)

    # financial status information, clear separation of the two was desired
    matured = db.Column(db.Boolean, default=False, nullable=False)
    cleared = db.Column(db.Boolean, default=False, nullable=False)
    disputed = db.Column(db.Boolean, default=False, nullable=False)
    frozen = db.Column(db.Boolean, default=False, nullable=False)
    closed = db.Column(db.Boolean, default=False, nullable=False)

    id = db.Column(db.Integer, db.ForeignKey('sink.id'), primary_key=True)
    amount = db.Column(db.Integer, CheckConstraint('amount>0'), nullable=False)
    # the fee we've extracted on this transaction
    fee = db.Column(db.Integer, CheckConstraint('fee>0'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    # Person who sent the money
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', foreign_keys=[user_id])
    # The object the earmark is assigned to
    thing_id = db.Column(db.Integer, db.ForeignKey('thing.id'), nullable=False)
    thing = db.relationship('Thing', backref='earmarks')

    __mapper_args__ = {'polymorphic_identity': 'Earmark'}

    standard_join = ['status',
                     'StatusVals',
                     'created_at',
                     '-stripe_created_at']

    acl = earmark_acl

    def assign(self, user_tuple):
        """ Accepts a list of tuples of form (user_object, percentage).
        Creates new Mark objects and links them to the earmark objects.
        Setup to be committed by caller for assigning all earmarks at once. """
        # checks for consistency
        if self.cleared or \
           len(self.marks) > 0 or \
           (self.thing.type == 'Issue' and self.thing.status != 'Completed'):
            current_app.logger.debug(
                "Cleared: {}\nMark Count: {}\nThing Type: {}\nThing Status: {}"
                .format(self.cleared,
                        len(self.marks),
                        self.thing.type,
                        self.thing.status))

            # this is a big mistake, raise an exception
            raise AttributeError

        # sort our list of users so the action is repeatable
        user_tuple.sort(key=lambda x: x[0].id)
        marks = []
        for user, perc in user_tuple:
            marks.append(Mark.create(
                self,
                perc,
                # floored to avoid floating point rounding problems
                math.floor((perc / 100) * self.amount),
                user))
        # loop through an increment the amount given round robin until we've
        # allocated all remaining cents from the amount
        i = itertools.cycle(marks)
        while sum([mark.amount for mark in marks]) < self.amount:
            u = i.next()
            u.amount += 1
            u.remaining += 1

        for mark in marks:
            db.session.add(mark)

        # change the status to assigned
        self.status = 'Assigned'

    def close(self):
        """ Closes an earmark. This occures when a user cancels, the earmark
        expires when frozen, or is manually closed by admins for some reason.

        Returns all funds to the sender and sets the closed status.
        """
        pass

    def yank(self):
        """ An uncommon procedure that attempts to pull the funds out of the
        recievers accounts if possible, after an earmark has completely cleared
        """
        pass

    def clear(self):
        """ Removes the funds from the sender and delivers them to destination
        users. """
        db.session.rollback()  # for the nervous person
        # checks for consistency
        if not self.matured or \
           self.cleared or \
           self.disputed or \
           self.frozen or \
           self.user.current_balance < self.amount or \
           (self.thing.type == 'Issue' and self.thing.status != 'Completed'):

            # this is a big mistake, raise an exception
            raise AttributeError

        # lock the user object, decrement their current balance
        db.session.refresh(self.user, lockmode='update')
        self.user.current_balance -= self.amount

        # the amount needing to be allocated
        deduct_total = self.amount
        # process logic for pulling funds from required sources
        typ = Mark  # start pulling from Marks
        while deduct_total > 0:
            src = (typ.query.
                   with_lockmode('update').      # lock dat boi
                   filter(typ.remaining > 0).    # remaining balance
                   filter_by(cleared=True).      # that cleared
                   filter_by(user=self.user).  # owned by current user
                   order_by(typ.created_at).     # finally, order by the date
                   first())                      # lock the row from updates

            # if we're out of Marks, switch to Charges
            if typ is Mark and src is None:
                typ = Charge
                print "continue"
                continue
            if typ is Charge and src is None:  # if we're out of funding period
                db.session.rollback()
                raise FundingException

            if src.remaining >= deduct_total:
                src.remaining -= deduct_total
                deduct_total = 0
            else:
                deduct_total -= src.remaining
                src.remaining = 0

        self.cleared = True
        for mark in self.marks:
            mark.clear()
        # now give the money to the recipients and update all statuses
        db.session.commit()

    def roles(self, user=None):
        """ Logic to determin what auth roles a user gets """
        if not user:
            user = current_user

        user_id = getattr(user, 'id', None)

        for mark in self.marks:
            if mark.user_id == user_id:
                return ['reciever']

        if self.user_id == getattr(user, 'id', None):
            return ['sender']

        if user.is_anonymous():
            return ['anonymous']
        else:
            return ['user']

    @classmethod
    def create(cls, thing, amount, user=None):
        if user is None:
            user = current_user

        if amount < 50:
            raise ValueError('Amount is too low to create earmark')

        fee = round(amount * current_app.config['TRANSFER_FEE'])
        mark = Earmark(
            amount=amount-fee,
            fee=fee,
            user=user,
            thing=thing,
        )
        # decrement their available balance along with creation of the object
        db.session.refresh(user, lockmode='update')
        user.available_balance -= amount
        db.session.add(mark)
        db.session.commit()
        return mark


class Mark(Source, PrivateMixin, base):
    """ A portion of an earmark that is declared to an individual user. Is used
    as a fund source, but also acts as the end of the line for an earmark
    transaction. """
    id = db.Column(db.Integer, db.ForeignKey('source.id'), primary_key=True)
    user_id = db.Column(db.Integer,
                        db.ForeignKey('user.id'),
                        primary_key=True)
    user = db.relationship('User')
    earmark_id = db.Column(db.Integer,
                           db.ForeignKey('earmark.id'),
                           primary_key=True)
    earmark = db.relationship('Earmark', backref='marks')
    # what percentage of the earmark was it?
    perc = db.Column(db.Integer, CheckConstraint('perc>0'), nullable=False)
    __mapper_args__ = {'polymorphic_identity': 'Mark'}

    @classmethod
    def create(cls, earmark, perc, amount, user=None):
        """ Creates a new Mark object, but does not commit it to the database
        """
        if user is None:
            user = current_user

        return cls(
            amount=amount,
            remaining=amount,
            perc=perc,
            earmark=earmark,
            user=user)


class Recipient(PrivateMixin, base):
    id = db.Column(db.Integer, primary_key=True)
    stripe_id = db.Column(db.String, unique=True)
    name = db.Column(db.String, nullable=False)
    verified = db.Column(db.Boolean, nullable=False)
    livemode = db.Column(db.Boolean, nullable=False)
    last_four = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    stripe_created_at = db.Column(db.DateTime, nullable=False)
    user = db.relationship('User')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    standard_join = ['created_at',
                     'last_four',
                     'verified',
                     'name',
                     'created_at',
                     '-stripe_created_at']

    acl = recipient_acl

    def clear(self):
        """ Pushes pending funds on through to the recipeint. Doesn't commit
        because it's intended to be called by the earmark clear method """
        pass

    @property
    def status(self):
        return self.StatusVals[self._status]

    @classmethod
    def create(cls, token, name, corporation, tax_id=None, user=None):
        if user is None:
            user = current_user

        account = token['id']
        livemode = token['livemode']
        typ = 'corporation' if corporation else 'individual'

        vals = dict(
            bank_account=account,
            name=name,
            type=typ,
            metadata={'username': current_user.username,
                      'userid': current_user.id}
        )
        # avoid injecting an empty string for tax_id, stripe doesn't like
        if tax_id:
            vals['tax_id'] = tax_id
        retval = stripe.Recipient.create(**vals)

        # create a new recipient in our db to reflect stripe
        recp = Recipient(
            livemode=livemode,
            stripe_id=retval['id'],
            stripe_created_at=datetime.fromtimestamp(retval['created']),
            user=user,
            last_four=retval['active_account']['last4'],
            verified=retval['active_account']['verified'],
            name=retval['name']
        ).save()

        return recp
