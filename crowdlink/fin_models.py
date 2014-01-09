from flask import current_app
from flask.ext.login import current_user
from datetime import datetime
from sqlalchemy.schema import CheckConstraint
from enum import Enum
from decimal import Decimal, setcontext, BasicContext

from . import db
from .acl import acl
from .model_lib import base, PrivateMixin, StatusMixin
from .exc import FundingException

import stripe
import math
import itertools

class Source(base):
    """ Represents a common base table for Sources for financial transactions.
    """
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

    def clear(self, event_data=None):
        """ Pushes pending funds on through to the recipeint. Doesn't commit
        because it's intended to be called by the other methods """
        db.session.refresh(self.user, lockmode='update')
        self.user.available_balance += self.amount
        self.user.current_balance += self.amount
        self.cleared = True
        # record the event in the log
        log = self.log.create(
            action='clear',
            item=self,
            data=event_data)
        db.session.add(log)

    def withdraw(self, amount, target=None):
        data = {'amount': int(amount)}
        if target:
            data.update(dict(target=target.id,
                             target_type=target.__class__.__name__))
        log = self.log.create(
            action='withdraw',
            item=self,
            data=data
        )
        db.session.add(log)
        self.remaining -= amount

    def __str__(self):
        return "<Source; id: {}; type: {}; amount: {}; remaining: {}; created_at: {}>".format(
                self.id,
                self.type,
                self.amount,
                self.remaining,
                self.created_at)

    __repr__ = __str__


class Transaction(base):
    id = db.Column(db.Integer, primary_key=True)
    source = db.relationship('Source')
    source_id = db.Column(db.Integer, db.ForeignKey('source.id'), nullable=False)
    sink = db.relationship('Sink')
    sink_id = db.Column(db.Integer, db.ForeignKey('sink.id'), nullable=False)
    amount = db.Column(db.Integer, CheckConstraint('amount>0'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Charge(Source, PrivateMixin, base):
    """ 1:1 with the Stripe charge object. Represnets a source for transactions
    """
    StatusVals = Enum('Pending', 'Cleared')
    _status = db.Column(db.Integer,
                        default=StatusVals.Pending.index,
                        nullable=False)

    id = db.Column(db.Integer, db.ForeignKey('source.id'), primary_key=True)
    livemode = db.Column(db.Boolean, nullable=False)
    stripe_id = db.Column(db.String, unique=True, nullable=False)
    stripe_created_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_four = db.Column(db.Integer)
    stripe_fee = db.Column(db.Integer,
                           CheckConstraint('stripe_fee>0'),
                           nullable=False)
    user = db.relationship('User')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    __mapper_args__ = {'polymorphic_identity': 'Charge'}
    standard_join = ['status',
                     'StatusVals',
                     'created_at',
                     '-stripe_created_at']

    acl = acl['charge']

    @property
    def status(self):
        return self.StatusVals[self._status]

    def get_stripe_charge(self):
        stripe.api_key = current_app.config['stripe_secret_key']
        return stripe.Charge.retrieve(self.stripe_id)

    @classmethod
    def create(cls, token, amount, user=current_user, event_data=None):
        card = token['id']
        livemode = token['livemode']
        stripe.api_key = current_app.config['stripe_secret_key']

        # calculate stripes fee and remove it. Wish they included it in their
        # API...
        setcontext(BasicContext)
        fee = int((Decimal(amount) *
                  Decimal(current_app.config['stripe_transfer_perc'])) + 30)
        charge = cls(
            livemode=livemode,
            user=user,
            stripe_id="",
            stripe_fee=fee,
            stripe_created_at=datetime.utcnow(),
            amount=amount - fee,
            remaining=amount - fee,
        )
        db.session.add(charge)
        db.session.flush()  # flush so we can use in stripe request

        retval = stripe.Charge.create(
            metadata={'username': user.username,
                      'userid': user.id,
                      'charge_id': charge.id},
            currency="usd",
            amount=amount,
            card=card)

        # update obj to set stripe values
        charge.stripe_id = retval['id']
        charge.stripe_created_at = datetime.fromtimestamp(retval['created'])
        charge.last_four = retval['card']['last4']

        if retval['paid']:
            charge._status = Charge.StatusVals.Cleared.index
            charge.clear()
        else:
            charge._status = Charge.StatusVals.Pending.index

        # record the event in the log
        log = cls.log.create(
            action='create',
            item=charge,
            data=event_data)
        db.session.add(log)

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

    def fund(self, amount, types):
        # acquire a list of possible sources, in sorted order
        sources = []
        for typ in types:
            sources += (typ.query.
                filter(typ.cleared == True).      # that cleared
                filter(typ.user == self.user).    # owned by current user
                filter(typ.remaining > 0).    # remaining balance
                order_by(typ.created_at).     # finally, order by the date
                with_lockmode('update').all())      # lock dat boi

        current_app.logger.debug(str(sources))

        # process logic for pulling funds from required sources
        for source in sources:
            if amount == 0:  # we're done, no more need be examined
                break

            if source.remaining >= amount:
                source.remaining -= amount
                tran = Transaction(amount=amount,
                                   source=source,
                                   sink=self)
                amount = 0
            else:
                tran = Transaction(amount=source.remaining,
                                   source=source,
                                   sink=self)
                amount -= source.remaining
                source.remaining = 0
            db.session.add(tran)

        # if they still need to allocate money to fund it and we're out of
        # sources
        if amount > 0:
            db.session.rollback()
            raise FundingException


class Transfer(Sink, PrivateMixin, base):
    """ An object mirroring a stripe transfer """
    id = db.Column(db.Integer, db.ForeignKey('sink.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status_val = db.Column(db.String, nullable=False)
    stripe_id = db.Column(db.String, unique=True, nullable=False)
    stripe_created_at = db.Column(db.DateTime, nullable=False)
    livemode = db.Column(db.Boolean, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', foreign_keys=[user_id])
    __mapper_args__ = {'polymorphic_identity': 'Transfer'}

    standard_join = ['status',
                     'StatusVals',
                     '_status',
                     'created_at',
                     'amount',
                     '-stripe_created_at']

    acl = acl['transfer']

    @property
    def status(self):
        return self.StatusVals[self._status]

    @classmethod
    def create(cls, amount, recipient, user=current_user):
        minimum = current_app.config['minimum_transfer']
        # make sure it's an int, stripe complains about floats
        amount = int(amount)

        if (recipient.user != user or  # Make sure it's going to them
           amount > user.available_marks or  # Ensure they have enough marks
           amount > user.available_balance or
           amount < minimum):  # ensure the marks are available
            current_app.logger.warn(
                "Create Transfer was called with invalid pre-conditions"
                "\nRecp Userid: {}\nAvailable Marks: {}\nAvailable Balance: {}"
                "\nAmount: {}"
                .format(recipient.user_id,
                        user.available_marks,
                        user.available_balance,
                        amount))
            raise AttributeError


        db.session.rollback()  # for the nervous person
        # lock the user, this action takes money out of their account
        db.session.refresh(user, lockmode='update')

        retval = stripe.Transfer.create(
            currency="usd",
            recipient=recipient.stripe_id,
            amount=amount,
            metadata={'username': user.username,
                      'userid': user.id}
        )

        # create a new recipient in our db to reflect stripe
        trans = cls(
            amount=amount,
            livemode=retval['livemode'],
            stripe_id=retval['id'],
            stripe_created_at=datetime.fromtimestamp(retval['date']),
            user=user,
            status_val=retval['status']
        )

        # fund the transfer with Marks
        trans.fund(amount, [Mark])

        user.available_balance -= amount
        user.current_balance -= amount

        db.session.add(trans)
        db.session.commit()

        return trans

    def clear(self, event_data=None):
        log = self.log.create(
            action='clear',
            item=self,
            data=event_data)
        db.session.add(log)
        self.cleared = True


class Dispute(base, PrivateMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', foreign_keys=[user_id])
    thing_id = db.Column(db.Integer, db.ForeignKey('thing.id'))
    thing = db.relationship('Thing', backref='disputes')
    content = db.Column(db.String)

    standard_join = ['id',
                     'content',
                     {'obj': 'user', 'join_prof': 'disp_join'},
                     {'obj': 'thing', 'join_prof': 'disp_join'}]

    @classmethod
    def create(cls, thing, content, user=current_user):
        db.session.rollback()

        if thing.type in ['Project', 'Solution']:
            current_app.logger.warn(
                "Someone tried to report a Thing that was of unallowed type"
                "\nThing ID: {}\nUser ID: {}"
                .format(thing.id,
                        user.id))
            raise AttributeError

        # if they're reporting an issue
        report = cls(thing=thing,
                     content=content,
                     user=user)

        # freeze any earmarks that are in place if they're disputing an Issue
        if thing.type == "Issue":
            db.session.flush()
            user.earmarks.filter(Earmark.thing == thing
                    ).one().dispute(event_data={'report_id': report.id})


class Earmark(Sink, base):
    """ Represents a users intent to give money to another member. """
    # status information as it relates to the attached thing
    status = db.Column(db.Enum('Created', 'Ready', 'Assigned', 'Disputed',
                               name="earmark_status"),
                       default='Created')

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

    acl = acl['earmark']

    def mature(self, event_data=None, event_blob=None):
        """ Sets the mature toggle on the Earmark, making it available for
        clearing.  Whether it clears or not is still dependent on other
        factors, including disputes, chargebacks (causing freezing),
        non-complete issue, etc """
        log = self.log.create(
            item=self,
            action='mature',
            data=event_data,
            blob=event_blob)
        db.session.add(log)
        self.matured = True

    def assign(self, user_tuple, event_data=None, event_blob=None):
        """ Accepts a list of tuples of form (user_object, percentage).
        Creates new Mark objects and links them to the earmark objects.
        Setup to be committed by caller for assigning all earmarks at once. """
        # checks for consistency
        if self.cleared or \
           len(self.marks) > 0 or \
           (self.thing.type == 'Issue' and self.thing.status != 'Completed'):
            current_app.logger.warn(
                "Assign Earmark was called with invalid pre-conditions"
                "Cleared: {}\nMark Count: {}\nThing Type: {}\nThing Status: {}"
                .format(self.cleared,
                        len(self.marks),
                        self.thing.type,
                        self.thing.status))

            # this is a big mistake, raise an exception
            raise AttributeError

        log = self.log.create(
            action='assign',
            item=self,
            data=event_data,
            blob=event_blob
        )
        db.session.add(log)

        # sort our list of users so the action is repeatable
        user_tuple.sort(key=lambda x: x[0].id)
        marks = []
        for user, perc in user_tuple:
            marks.append([
                perc,
                # floored to avoid floating point rounding problems
                math.floor((perc / 100.0) * self.amount),
                user])
        # loop through an increment the amount given round robin until we've
        # allocated all remaining cents from the amount
        i = itertools.cycle(marks)
        while sum([mark[1] for mark in marks]) < self.amount:
            u = i.next()
            u[1] += 1

        for perc, amount, user in marks:
            mark = Mark.create(self, perc, amount, user)
            db.session.add(mark)

        # change the status to assigned
        self.status = 'Assigned'

    def dispute(self, event_data=None):
        """ Called when the Issue/Project it's attached to is being reported
        in some way. Effectively freezes the Earmark. """
        self.frozen = True
        self.disputed = True
        # make an event for it
        log = self.log.create(
            action='dispute',
            item=self,
            data=event_data
        )
        db.session.add(log)


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

    def clear(self, event_data=None, event_blob=None):
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

            current_app.logger.warn(
                "Clear Earmark was called with invalid pre-conditions"
                "\nCleared: {}\nUser Balance: {}\nAmount: {}\nThing Status: {}"
                "\nThing Type: {}\nFrozen: {}\nDisputed: {}\n"
                .format(self.cleared,
                        self.matured,
                        self.user.current_balance,
                        self.amount,
                        self.thing.type,
                        self.thing.status,
                        self.frozen,
                        self.disputed))
            # this is a big mistake, raise an exception
            raise AttributeError

        # lock the user object, decrement their current balance
        db.session.refresh(self.user, lockmode='update')
        self.user.current_balance -= self.amount

        # make a clear event for it
        log = self.log.create(
            action='clear',
            item=self,
            data=event_data,
            blob=event_blob
        )
        db.session.add(log)

        # fund the clearing with a common function
        self.fund(self.amount, [Mark, Charge])
        self.cleared = True
        # clear all the marks on this object now that it's funded
        for mark in self.marks:
            mark.clear()

        # boom!
        db.session.commit()

    def roles(self, user=current_user):
        """ Logic to determin what auth roles a user gets """
        user_id = getattr(user, 'id', None)

        for mark in self.marks:
            if mark.user_id == user_id:
                return ['mark_reciever']

        if self.user_id == user_id:
            return ['sender']

        return []

    @classmethod
    def create(cls, thing, amount, event_data=None, event_blob=None,
               user=current_user):
        if event_data is None:
            event_data = {}

        if thing.type not in ['Issue', 'Solution', 'Project']:
            current_app.logger.warn(
                "Someone tried to Earmark the wrong type of object"
                "\nType: {}\nObjID: {}"
                .format(thing.type,
                        thing.id))
            raise AttributeError

        # decrement their available balance along with creation of the object
        db.session.refresh(user, lockmode='update')
        amount = int(amount)
        minimum = current_app.config['minimum_earmark']
        if amount < minimum:
            raise ValueError(
                "Amount {} is too low to create earmark. Min is {}"
                .format(amount, minimum))
        if amount > user.available_balance:
            raise FundingException

        db.session.rollback()
        setcontext(BasicContext)
        fee = Decimal(amount) * Decimal(current_app.config['transfer_fee'])
        mark = Earmark(
            amount=int(amount) - fee,
            fee=fee,
            user=user,
            thing=thing,
        )
        # make a create event for it
        event_data.update({'amount': str(int(amount))})
        log = EarmarkLog.create(
            action='create',
            item=mark,
            data=event_data,
            blob=event_blob
        )
        user.available_balance -= amount
        db.session.add(mark)
        db.session.add(log)
        db.session.commit()
        return mark

    def __str__(self):
        return ("<Earmark; id: {}; amount: {}; created_at: {}; creator: {}; "
                "mature: {}; disputed: {}; frozen: {}>"
                .format(
                    self.id,
                    self.amount,
                    self.created_at,
                    self.user_id,
                    self.matured,
                    self.disputed,
                    self.frozen))

    __repr__ = __str__

class Mark(Source, PrivateMixin, base):
    """ A portion of an earmark that is declared to an individual user. Is used
    as a fund source, but also acts as the end of the line for an earmark
    transaction. """

    id = db.Column(db.Integer, db.ForeignKey('source.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref='marks')
    earmark_id = db.Column(db.Integer, db.ForeignKey('earmark.id'))
    earmark = db.relationship('Earmark', backref='marks')
    # what percentage of the earmark was it?
    perc = db.Column(db.Integer, CheckConstraint('perc>0'), nullable=False)
    __mapper_args__ = {'polymorphic_identity': 'Mark'}
    __table_args__ = (db.UniqueConstraint("earmark_id", "user_id"),)

    @classmethod
    def create(cls, earmark, perc, amount, user=current_user):
        """ Creates a new Mark object, but does not commit it to the database
        """

        mark = cls(amount=amount,
                   remaining=amount,
                   perc=perc,
                   earmark=earmark,
                   user=user)

        # make a create event for it
        log = MarkLog.create(
            action='create',
            item=mark,
            data={'amount': int(amount),
                  'perc': perc}
        )
        db.session.add(log)

        return mark

    def __str__(self):
        return "<Mark; id: {}; amount: {}; remaining: {}; created_at: {}; earmark: {}>".format(
                self.id,
                self.amount,
                self.remaining,
                self.created_at,
                self.earmark_id)

    __repr__ = __str__


class Recipient(PrivateMixin, base):
    id = db.Column(db.Integer, primary_key=True)
    stripe_id = db.Column(db.String, unique=True)
    name = db.Column(db.String, nullable=False)
    verified = db.Column(db.Boolean, nullable=False)
    livemode = db.Column(db.Boolean, nullable=False)
    last_four = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    stripe_created_at = db.Column(db.DateTime, nullable=False)
    user = db.relationship('User', backref='recipients')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    standard_join = ['created_at',
                     'last_four',
                     'verified',
                     'name',
                     'created_at',
                     '-stripe_created_at']

    acl = acl['recipient']

    @classmethod
    def create(cls, token, name, corporation, tax_id=None, user=current_user):
        account = token['id']
        livemode = token['livemode']
        typ = 'corporation' if corporation else 'individual'

        # create a new recipient in our db to reflect stripe
        recp = Recipient(
            livemode=livemode,
            user=user,
            name=' ',
            verified=False,
            stripe_created_at=datetime.utcnow(),
        )
        db.session.add(recp)
        db.session.flush()

        vals = dict(
            bank_account=account,
            name=name,
            type=typ,
            metadata={'username': current_user.username,
                      'userid': current_user.id,
                      'recipient_id': recp.id}
        )
        # avoid injecting an empty string for tax_id, stripe doesn't like
        if tax_id:
            vals['tax_id'] = tax_id
        retval = stripe.Recipient.create(**vals)

        recp.stripe_id = retval['id'],
        recp.stripe_created_at = datetime.fromtimestamp(retval['created']),
        recp.last_four = retval['active_account']['last4'],
        recp.verified = retval['active_account']['verified'],
        recp.name = retval['name']

        db.session.commit()

        return recp

# Must be imported here to avoid import loops
from .log_models import (EarmarkLog, ChargeLog, MarkLog, TransferLog,
                         RecipientLog)
Recipient.log = RecipientLog
Charge.log = ChargeLog
Transfer.log = TransferLog
Earmark.log = EarmarkLog
Mark.log = MarkLog
