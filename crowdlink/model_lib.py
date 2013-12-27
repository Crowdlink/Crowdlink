from flask import current_app
from flask.ext.login import current_user
from datetime import datetime
from flask.ext.sqlalchemy import (_BoundDeclarativeMeta, BaseQuery,
                                  _QueryProperty)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import HSTORE
from sqlalchemy.types import TypeDecorator, TEXT
from sqlalchemy import event
from enum import Enum

from . import db


import sqlalchemy
import json
import calendar


class BaseMapper(object):
    """ The base model instance for all model. Provides lots of useful
    utilities in addition to access control logic and serialization helpers """

    # Allows us to run query on the class directly, instead of through a
    # session
    query_class = BaseQuery
    query = None

    def __new__(cls, *args, **kwargs):
        """ If a valideer validation class is set then validation triggers are
        set on the object """

        # if there's validation on this object
        valid = getattr(cls, 'valid_profile', None)
        if valid:
            for name, validator in valid._named_validators:
                func = lambda target, value, oldvalue, initiator: \
                    valid.validate_attr(initiator, value)
                event.listen(getattr(cls, name),
                             'set',
                             func,
                             name)

        return super(BaseMapper, cls).__new__(cls, *args, **kwargs)

    # Access Control Methods
    # =========================================================================
    def roles(self, user=current_user):
        """ This should be overriden to use logic for determining roles on an
        instance of the class """
        return []

    def can(self, action):
        """ Can the user perform the action needed on this object instance? """
        current_app.logger.debug((action, self.user_acl))
        return action in self.user_acl

    @classmethod
    def can_cls(cls, action):
        """ Can the user perform the action needed on this class (non inst
        specific)? """
        roles = current_user.global_roles()
        acl = cls._role_mix(roles)
        current_app.logger.debug((roles, acl, action))
        return action in acl

    @classmethod
    def _role_mix(cls, roles):
        allowed = set()
        for role in roles:
            allowed |= cls.acl.get(role, set())
        return allowed

    @property
    def user_acl(self, user=current_user):
        """ a lazy loaded acl list for the current user """
        # Run an extra check to ensure we don't hand out an acl list for the
        # wrong user. Possibly un-neccesary, I'm paranoid
        roles = []
        inst_roles = self.roles(user=user)
        if isinstance(inst_roles, list):  # allow either str or list
            roles += inst_roles
        elif inst_roles != None:
            roles.append(inst_roles)
        roles += current_user.global_roles()
        return self._role_mix(roles)

    def save(self, *exc_catch):
        """ Automatically adds object to global session and catches exception
        types silently that are given as args. """
        if db.object_session(self) is None:
            db.session.add(self)

        try:
            db.session.commit()
        except Exception as e:
            # if they didn't want to catch this, then raise it
            if type(e) not in exc_catch:
                raise
            else:
                db.session.rollback()
        return self

    def to_dict(model):
        """ converts a sqlalchemy model to a dictionary """
        # first we get the names of all the columns on your model
        columns = [c.key for c in sqlalchemy.orm.class_mapper(model.__class__).columns]
        # then we return their values in a dict
        return dict((c, getattr(model, c)) for c in columns)

    def jsonize(self, args, raw=False):
        """ Used to join attributes or functions to an objects json
        representation.  For passing back object state via the api """
        dct = {}
        for key in args:
            attr = getattr(self, key)
            # If it's being joined this way, just use the id
            if isinstance(attr, BaseMapper):
                try:
                    attr = str(attr.id)
                except AttributeError:
                    current_app.logger.warn(
                        ("{} object join doesn't have an id on obj "
                         "{}").format(str(attr), self.__class__.__name__))
            # convert an enum to a dict for easy parsing
            if isinstance(attr, Enum):
                attr = dict({str(x): x.index for x in attr})
            # convert datetime to seconds since epoch, much more universal
            elif isinstance(attr, datetime):
                attr = calendar.timegm(attr.utctimetuple()) * 1000
            # don't convert bool or int to str
            elif (isinstance(attr, bool) or
                  isinstance(attr, int) or
                  attr is None or
                  isinstance(attr, list)):
                pass
            # convert set (user_acl list) to a dictionary for easy conditionals
            elif isinstance(attr, set):
                attr = {x: True for x in attr}
            # try to fetch callables properly
            elif callable(attr):
                try:
                    attr = attr()
                except TypeError:
                    current_app.logger.warn(
                        ("{} callable requires argument on obj "
                         "{}").format(str(attr), self.__class__.__name__))
            else:
                attr = str(attr)
            dct[key] = attr

        if raw:
            return dct
        else:
            return json.dumps(dct)


# setup our base mapper and database metadata
metadata = db.MetaData()
base = declarative_base(cls=BaseMapper,
                        metaclass=_BoundDeclarativeMeta,
                        metadata=metadata,
                        name='Model')
base.query = _QueryProperty(db)
db.Model = base


class Report(base):
    """ associative table for voting on things """
    reporter_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), primary_key=True)
    reporter = db.relationship('User', foreign_keys=[reporter_id])

    reportee_id = db.Column(
        db.Integer, db.ForeignKey("thing.id"), primary_key=True)
    reportee = db.relationship('Thing')

    reason = db.Column(db.String(255))


class Vote(base):
    """ associative table for voting on things """
    voter_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), primary_key=True)
    voter = db.relationship('User', foreign_keys=[voter_id])

    votee_id = db.Column(
        db.Integer, db.ForeignKey("thing.id"), primary_key=True)
    votee = db.relationship('Thing')


class Subscription(base):
    """ associative table for subscribing to things. Includes an HSTORE column
    for rules on subscription """
    rules = db.Column(HSTORE)
    subscriber_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), primary_key=True)
    subscriber = db.relationship('User', foreign_keys=subscriber_id)

    subscribee_id = db.Column(
        db.Integer, db.ForeignKey("thing.id"), primary_key=True)
    subscribee = db.relationship('Thing')


class SubscribableMixin(object):
    """ A Mixin providing data model utils for subscribing new users. Maintain
    uniqueness of user by hand through these checks """

    @property
    def subscribed(self, user=current_user):
        if not user.is_anonymous():
            return bool(Subscription.query.filter_by(
                subscriber=user.get(),
                subscribee_id=self.id).first())

    @subscribed.setter
    def subscribed(self, val):
        self.set_subscribed(val)

    def set_subscribed(self, val, user=current_user):
        if val:
            current_app.logger.debug(
                "Subscribing on {} as user {}"
                .format(self.__class__.__name__, user.username))
            sub = Subscription(subscriber=user.get(),
                               subscribee_id=self.id)
            # since they're subscribing, add the last ten events from the
            # source to their events
            i = 0
            for event in self.public_events:
                # only deliver 10
                if i == 10:
                    break
                if event.sendable(user):
                    user.events = user.events + [event]
                    i += 1

            # sort the list
            user.events = sorted(user.events, key=lambda x: x.time)

            # save the new subscription object along with the modified events in
            # one go. events won't get added if already subscribed...
            sub.save(sqlalchemy.exc.IntegrityError)
            return True
        else:
            Subscription.query.filter_by(
                subscriber=user.get(),
                subscribee_id=self.id).delete()
            # remove all events that originate from the source they're
            # unsubscribing
            user.events = [e for e in user.events if not e.originates(self.id)]

            current_app.logger.debug(
                "Unsubscribing on {} as user {}"
                .format(self.__class__.__name__, user.username))
            return True

    @property
    def subscribers(self):
        return Subscription.query.filter_by(subscribee_id=self.id)


class ReportableMixin(object):
    """ Allows user local getters and setters for reporting things """

    @property
    def report_status(self):
        if not current_user.is_anonymous():
            report = Report.query.filter_by(reporter=current_user.get(),
                                            reportee=self).first()
            if report:
                return report.reason
            else:
                return False
        else:
            return None

    @report_status.setter
    def report_status(self, reason):
        self.set_report_status(reason)

    def set_report_status(self, reason, user=current_user):
        # XXX: TODO: Really needs error catching
        if not reason:  # unreport
            Report.query.filter_by(reporter=current_user.get(),
                                   reportee=self).delete()
            current_app.logger.debug(
                ("Unreporting on {} as user "
                 "{}").format(self.__class__.__name__, current_user.username))
            return True
        else:  # report them, update reason if needed
            current_app.logger.debug(
                ("Voting on {} as user "
                 "{}").format(self.__class__.__name__, current_user.username))
            report = Report(reporter_id=current_user.get().id,
                            reportee_id=self.id,
                            reason=reason)
            db.session.merge(report)
            return True


class VotableMixin(object):
    """ A Mixin providing data model utils for subscribing new users. Maintain
    uniqueness of user by hand through these checks """

    @property
    def vote_status(self):
        if not current_user.is_anonymous():
            return bool(Vote.query.filter_by(voter=current_user.get(),
                                             votee=self).first())

    @vote_status.setter
    def vote_status(self, vote):
        self.set_vote_status(vote)

    def set_vote_status(self, vote, user=current_user):
        # XXX: TODO: Really needs error catching
        if not vote:  # unvote
            Vote.query.filter_by(voter=current_user.get(),
                                 votee=self).delete()
            current_app.logger.debug(
                ("Unvoting on {} as user "
                 "{}").format(self.__class__.__name__, current_user.username))
            return True
        else:  # vote
            current_app.logger.debug(
                ("Voting on {} as user "
                 "{}").format(self.__class__.__name__, current_user.username))
            vote = Vote(voter=current_user.get(), votee_id=self.id)
            vote.save(sqlalchemy.exc.IntegrityError)
            return True


class HSTOREStringify(TypeDecorator):
    impl = HSTORE
    def process_bind_param(self, value, dialect):
        if value:
            return {key: str(val) for key, val in value.items()}
        else:
            return None

    def process_result_value(self, value, dialect):
        return value


class JSONEncodedDict(TypeDecorator):
    impl = TEXT
    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


class EventJSON(TypeDecorator):
    """ Wraps a list of Event objects into a JSON encoded list """

    impl = TEXT

    def process_bind_param(self, value, dialect):
        if value is not None:
            lst = []
            for obj in value:
                lst.append(obj.to_dict())
            return json.dumps(lst)
        return "[]"

    def process_result_value(self, value, dialect):
        from . import events as events
        if value is not None:
            lst = []
            for dct in json.loads(value):
                cls = getattr(events, dct.get("_cls"))
                if cls:
                    lst.append(cls(**dct))
            return lst
        return []


class PrivateMixin(object):
    """ Common methods for objects that are private """
    def roles(self, user=current_user):
        """ Logic to determin what auth roles a user gets """
        if self.user_id == getattr(user, 'id', None):
            return ['owner']

        if user.is_anonymous():
            return ['anonymous']
        else:
            return ['user']


class StatusMixin(object):
    @property
    def status(self):
        return str(self.StatusVals[self._status])

    @status.setter
    def status(self, value):
        """ Let the caller know if it was already set """
        idx = getattr(self.StatusVals, value).index
        if self._status == idx:
            return False
        else:
            self._status = idx
            return True
