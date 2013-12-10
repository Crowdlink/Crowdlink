from flask import session, current_app, flash
from flask.ext.login import current_user

from . import db, github
from .util import inherit_lst
from .acl import issue_acl, project_acl, solution_acl, user_acl, transaction_acl, earmark_acl

from flask.ext.sqlalchemy import (_BoundDeclarativeMeta, BaseQuery,
                                  _QueryProperty)
from sqlalchemy.ext.declarative import declared_attr, declarative_base
from sqlalchemy.dialects.postgresql import HSTORE
from sqlalchemy.types import TypeDecorator, TEXT
from sqlalchemy import event

from enum import Enum

import valideer as V

import sqlalchemy
import cryptacular.bcrypt
import re
import werkzeug
import json
import urllib
import hashlib
import datetime
import calendar

crypt = cryptacular.bcrypt.BCRYPTPasswordManager()


def validate_attr(self, attr, value):
    """ Allows calling a single validator by passing in a dotted notation for
    the object.  """
    attr = str(attr).split('.', 1)[1]
    validator = [v for i, v in enumerate(self._named_validators) if v[0] == attr][0][1]
    try:
        return validator.validate(value)
    except V.ValidationError as e:
        raise AttributeError(str(e) + " on attribute " + attr)
V.Object.validate_attr = validate_attr


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
    def get_acl(self, user=None):
        """ Generates an acl list for a specific user which defaults to the
        authed user """
        if not user:
            user = current_user
        roles = self.roles(user=user)
        allowed = set()
        for role in roles:
            allowed |= set(self.acl.get(role, []))

        return allowed

    def roles(self, user=None):
        """ This should be overriden to use logic for determining roles """
        if not user:
            user = current_user
        return []

    def can(self, action):
        """ Can the user perform the action needed? """
        current_app.logger.debug((action, self.user_acl))
        return action in self.user_acl

    @property
    def user_acl(self):
        """ a lazy loaded acl list for the current user """
        # Run an extra check to ensure we don't hand out an acl list for the
        # wrong user. Possibly un-neccesary, I'm paranoid
        if not hasattr(self, '_user_acl') or self._user_acl[0] != current_user:
            self._user_acl = (current_user, self.get_acl())
        return self._user_acl[1]

    def safe_save(self, **kwargs):
        """ Automatically adds object to the global session and saves with
        error catching """
        # add to the main session if not added
        if db.object_session(self) is None:
            db.session.add(self)

        try:
            db.session.commit(**kwargs)
        except Exception:
            db.session.rollback()
            current_app.logger.warn("Unkown error commiting to db",
                                    exc_info=True)
            return False
        return True

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
            elif isinstance(attr, datetime.datetime):
                attr = calendar.timegm(attr.utctimetuple()) * 1000
            # don't convert bool or int to str
            elif isinstance(attr, bool) or isinstance(attr, int) or attr is None:
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


# our parent table for issues, projects, solutions and users
thing_table = db.Table('thing',
                       metadata,
                       db.Column('id', db.Integer, primary_key=True))


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
        if value is not None:
            lst = []
            for dct in json.loads(value):
                cls = getattr(events, dct.get("_cls"))
                if cls:
                    lst.append(cls(**dct))
            return lst
        return []


class Vote(base):
    """ associative table for voting on things """
    voter_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), primary_key=True)
    voter = db.relationship('User', foreign_keys=[voter_id])

    votee_id = db.Column(
        db.Integer, db.ForeignKey("thing.id"), primary_key=True)


class VotableMixin(object):
    """ A Mixin providing data model utils for subscribing new users. Maintain
    uniqueness of user by hand through these checks """

    def set_vote(self, vote):
        # XXX: Really needs error catching
        if not vote:  # unvote
            Vote.query.filter_by(voter=current_user.get(),
                           votee_id=self.id).delete()
            current_app.logger.debug(
                ("Unvoting on {} as user "
                 "{}").format(self.__class__.__name__, current_user.username))
            return True
        else:  # vote
            current_app.logger.debug(
                ("Voting on {} as user "
                 "{}").format(self.__class__.__name__, current_user.username))
            vote = Vote(voter=current_user.get(), votee_id=self.id)
            try:
                db.session.add(vote)
                db.session.commit()
            except sqlalchemy.exc.IntegrityError:
                pass
            return True
        return "already_set"

    @property
    def vote_status(self):
        if not current_user.is_anonymous():
            return bool(Vote.query.filter_by(voter=current_user.get(),
                                             votee_id=self.id).first())


class Subscription(base):
    """ associative table for subscribing to things. Includes an HSTORE column
    for rules on subscription """
    rules = db.Column(HSTORE)
    subscriber_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), primary_key=True)
    subscriber = db.relationship('User', foreign_keys=subscriber_id)

    subscribee_id = db.Column(
        db.Integer, db.ForeignKey("thing.id"), primary_key=True)


class SubscribableMixin(object):
    """ A Mixin providing data model utils for subscribing new users. Maintain
    uniqueness of user by hand through these checks """

    def unsubscribe(self):
        Subscription.query.filter_by(
            subscriber=current_user.get(),
            subscribee_id=self.id).delete()
        current_app.logger.debug(
            ("Unsubscribing on {} as user "
             "{}").format(self.__class__.__name__, current_user.username))
        return True

    def subscribe(self):
        current_app.logger.debug(
            ("Subscribing on {} as user "
             "{}").format(self.__class__.__name__, current_user.username))
        sub = Subscription(subscriber=current_user.get(),
                     subscribee_id=self.id)
        try:
            db.session.add(sub)
            db.session.commit()
        except sqlalchemy.exc.IntegrityError:
            pass
        return True

    @property
    def subscribed(self):
        if not current_user.is_anonymous():
            return bool(Subscription.query.filter_by(
                subscriber=current_user.get(),
                subscribee_id=self.id).first())

    @property
    def subscribers(self):
        return Subscription.query.filter_by(subscribee_id=self.id)


project_table = db.Table('project', metadata,
    db.Column('id', db.Integer, primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.datetime.now),
    db.Column('maintainer_username', db.String, db.ForeignKey('user.username')),
    db.Column('url_key', db.String),
    db.Column('thing_id', db.Integer, db.ForeignKey('thing.id')),

    # description info
    db.Column('name', db.String(128)),
    db.Column('website', db.String(256)),
    db.Column('desc', db.String),
    db.Column('issue_count', db.Integer),  # XXX: Currently not implemented

    # voting
    db.Column('votes', db.Integer, default=0),

    # Event log
    db.Column('events', EventJSON),

    # Github Syncronization information
    db.Column('gh_repo_id', db.Integer, default=-1),
    db.Column('gh_repo_path', db.String),
    db.Column('gh_synced_at', db.DateTime),
    db.Column('gh_synced', db.Boolean, default=False),
    db.UniqueConstraint("url_key", "maintainer_username"))


class Project(base, SubscribableMixin, VotableMixin):
    """ This class is a composite of thing and project tables """
    id = db.column_property(thing_table.c.id, project_table.c.thing_id)
    __table__ = db.join(thing_table, project_table)
    project_id = project_table.c.id
    maintainer = db.relationship('User', foreign_keys='Project.maintainer_username')

    # Validation Profile
    # ======================================================================
    valid_profile = V.parse({
        "?created_at": "datetime",
        #"user": 'testing',
        "url_key": V.String(max_length=64),
        "name": V.String(max_length=128),
        "?website": V.String(max_length=256),
        "?desc": V.String(),
    }, required_properties=True)

    # Join profiles
    # ======================================================================
    standard_join = ['get_abs_url',
                     'maintainer',
                     'user_acl',
                     'created_at',
                     'maintainer_username',
                     'id',
                     '-vote_list',
                     '-events'
                     ]
    # used for displaying the project in noifications, etc
    disp_join = ['__dont_mongo',
                 'name',
                 'get_abs_url',
                 'maintainer_username']

    issue_page_join = ['__dont_mongo',
                       'name',
                       'maintainer_username',
                       'get_abs_url']
    page_join = inherit_lst(standard_join,
                            ['__dont_mongo',
                             'name',
                             'subscribed',
                             'vote_status',
                             {'obj': 'events'},
                             ]
                            )

    # Import the acl from acl file
    acl = project_acl

    def issues(self):
        return Issue.query.filter_by(project=self)

    def roles(self, user=None):
        """ Logic to determin what auth roles a user gets """
        if not user:
            user = current_user

        if self.maintainer == user:
            return ['maintainer']

        if user.is_anonymous():
            return ['anonymous']
        else:
            return ['user']

    @property
    def get_dur_url(self):
        return "/p/{id}".format(id=self.id)

    @property
    def get_abs_url(self):
        return "/{username}/{url_key}/".format(
            username=self.maintainer_username,
            url_key=self.url_key)

    def add_issue(self, issue, user):
        """ Add a new issue to this project """
        issue.create_key()
        issue.project = self
        issue.safe_save()

        # send a notification to all subscribers
        events.IssueNotif.generate(issue)

    def add_comment(self, body, user):
        # Send the actual comment to the issue event queue
        #c = Comment(user=user, body=body)
        #distribute_event(self, c, "comment", self_send=True)
        pass

    # Github Synchronization Logic
    # ========================================================================
    @property
    def gh_sync_meta(self):
        return self.gh_repo_id > 0

    def gh_sync(self, data):
        self.gh_repo_id = data['id']
        self.gh_repo_path = data['full_name']
        self.gh_synced_at = datetime.datetime.now()
        self.gh_synced = True
        current_app.logger.debug("Synchronized repository")

    def gh_desync(self, flatten=False):
        """ Used to disconnect a repository from github. By default will leave
        all data in place for re-syncing, but flatten will cause erasure """

        self.gh_synced = False
        # Remove indexes if we're flattening
        if flatten:
            self.gh_synced_at = None
            self.gh_repo_path = None
            self.gh_repo_id = -1
        self.safe_save()
        current_app.logger.debug("Desynchronized repository")


issue_table = db.Table('issue', metadata,
    db.Column('id', db.Integer, primary_key=True),
    # key pair, unique identifier
    db.Column('url_key', db.String, unique=True),

    db.Column('_status', db.Integer, default=1),
    db.Column('title', db.String(128)),
    db.Column('desc', db.Text),
    db.Column('creator_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('created_at', db.DateTime, default=datetime.datetime.now),
    db.Column('thing_id', db.Integer, db.ForeignKey('thing.id')),

    # voting
    db.Column('votes', db.Integer, default=0),

    # Event log
    db.Column('events', EventJSON),

    # our project relationship
    db.Column('project_url_key', db.String),
    db.Column('project_maintainer_username', db.String),
    db.ForeignKeyConstraint(
        ['project_url_key', 'project_maintainer_username'],
        ['project.url_key', 'project.maintainer_username']),
    db.UniqueConstraint(
        "url_key",
        "project_maintainer_username",
        "project_url_key"))


class Issue(base, SubscribableMixin, VotableMixin):
    statuses = Enum('Completed', 'Discussion', 'Selected', 'Other')


    id = db.column_property(thing_table.c.id, issue_table.c.thing_id)
    __table__ = db.join(thing_table, issue_table)
    issue_id = issue_table.c.id
    project = db.relationship(
        'Project',
        foreign_keys='[Issue.project_url_key, Issue.project_maintainer_username]')
    creator = db.relationship('User', foreign_keys='Issue.creator_id')

    acl = issue_acl
    standard_join = ['get_abs_url',
                     'title',
                     'vote_status',
                     'status',
                     'subscribed',
                     'user_acl',
                     'created_at',
                     'id',
                     ]
    page_join = inherit_lst(standard_join,
                            ['get_project_abs_url',
                             {'obj': 'project',
                              'join_prof': 'issue_page_join'},
                             'statuses']
                            )

    # used for displaying the project in noifications, etc
    brief_join = ['__dont_mongo',
                  'title',
                  'get_abs_url']
    disp_join = ['__dont_mongo',
                 'title',
                 'get_abs_url',
                 {'obj': 'project',
                  'join_prof': 'disp_join'}]

    def solutions(self):
        return Solution.query.filter_by(issue=self)

    def roles(self, user=None):
        """ Logic to determin what roles a person gets """
        if not user:
            user = current_user

        roles = []

        if self.project.maintainer == user:
            roles.append('maintainer')

        if self.creator == user or 'maintainer' in roles:
            roles.append('creator')

        if user.is_anonymous:
            roles.append('anonymous')
        else:
            roles.append('user')

        return roles

    @property
    def get_dur_url(self):
        return "/i/{id}".format(id=self.id)

    @property
    def get_abs_url(self):
        return "/{username}/{purl_key}/{url_key}".format(
            purl_key=self.project_url_key,
            username=self.project_maintainer_username,
            url_key=self.url_key)

    @property
    def get_project_abs_url(self):
        return "/{username}/{url_key}/".format(
            username=self.project_maintainer_username,
            url_key=self.project_url_key)

    @property
    def status(self):
        return self.statuses[self._status]

    def set_status(self, value):
        """ Let the caller know if it was already set """
        if self._status == int(value):
            return False
        else:
            self._status = True
            return True

    def create_key(self):
        if self.title:
            self.url_key = re.sub(
                '[^0-9a-zA-Z]', '-', self.title[:100]).lower()

    def add_comment(self, user, body):
        # Send the actual comment to the Issue event queue
        #c = Comment(user=user.id, body=body)
        #c.distribute(self)
        pass

    def gh_desync(self, flatten=False):
        """ Used to disconnect an Issue from github. Really just a trickle down
        call from de-syncing the project, but nicer to keep the logic in
        here"""
        self.gh_synced = False
        # Remove indexes if we're flattening
        if flatten:
            self.gh_issue_num = None
            self.gh_labels = []
        self.safe_save()


solution_table = db.Table('solution', metadata,
    db.Column('id', db.Integer, primary_key=True),
    db.Column('url_key', db.String, unique=True),

    db.Column('title', db.String(128)),
    db.Column('desc', db.Text),
    db.Column('creator_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('created_at', db.DateTime, default=datetime.datetime.now),
    db.Column('thing_id', db.Integer, db.ForeignKey('thing.id')),

    # voting
    db.Column('votes', db.Integer, default=0),

    # Event log
    db.Column('events', EventJSON),

    # our project and issue relationship
    db.Column('project_url_key', db.String),
    db.Column('project_maintainer_username', db.String),
    db.Column('issue_url_key', db.String),
    db.ForeignKeyConstraint(
        ['project_url_key', 'project_maintainer_username'],
        ['project.url_key', 'project.maintainer_username']),
    db.ForeignKeyConstraint(
        ['project_url_key', 'project_maintainer_username', 'issue_url_key'],
        ['issue.project_url_key', 'issue.project_maintainer_username', 'issue.url_key']))


class Solution(base, SubscribableMixin, VotableMixin):
    """ A composite of the solution table and the thing table.

    Solutions are attributes of Issues that can be voted on, commented on etc
    """

    id = db.column_property(thing_table.c.id, solution_table.c.thing_id)
    __table__ = db.join(thing_table, solution_table)
    solution_id = solution_table.c.id
    project = db.relationship(
        'Project',
        foreign_keys='[Solution.project_url_key, Solution.project_maintainer_username]')
    issue = db.relationship(
        'Issue',
        foreign_keys='[Solution.issue_url_key, Solution.project_url_key, Solution.project_maintainer_username]')
    creator = db.relationship('User', foreign_keys='Solution.creator_id')

    acl = solution_acl
    standard_join = ['get_abs_url',
                     'title',
                     'subscribed',
                     'user_acl',
                     'created_at',
                     '-vote_list',
                     'id'
                     ]
    page_join = inherit_lst(standard_join,
                            [{'obj': 'issue',
                              'join_prof': 'page_join'},
                             'vote_status'
                             ]
                            )

    # used for displaying the project in noifications, etc
    brief_join = ['__dont_mongo',
                  'title',
                  'get_abs_url']

    def roles(self, user=None):
        """ Logic to determin what roles a person gets """
        if not user:
            user = current_user

        roles = []

        if self.project.maintainer == user:
            roles.append('maintainer')

        if self.creator == user or 'maintainer' in roles:
            roles.append('creator')

        if user.is_anonymous:
            roles.append('anonymous')
        else:
            roles.append('user')

        return roles

    @property
    def get_dur_url(self):
        return "/s/{id}".format(id=self.id)

    @property
    def get_abs_url(self):
        return "/{id}/{url_key}".format(
            id=self.id,
            url_key=self.url_key)

    @property
    def status(self):
        return self.statuses[self._status]

    def set_status(self, value):
        """ Let the caller know if it was already set """
        if self._status == int(value):
            return False
        else:
            self._status = True
            return True

    def create_key(self):
        if self.title:
            self.url_key = re.sub(
                '[^0-9a-zA-Z]', '-', self.title[:100]).lower()

    def add_comment(self, user, body):
        # Send the actual comment to the Issue event queue
        #c = Comment(user=user.id, body=body)
        #c.distribute(self)
        pass

    # Github Synchronization Logic
    # ========================================================================
    def gh_desync(self, flatten=False):
        """ Used to disconnect an Issue from github. Really just a
        trickle down call from de-syncing the project, but nicer to keep the
        logic in here"""
        self.gh_synced = False
        # Remove indexes if we're flattening
        if flatten:
            self.gh_issue_num = None
            self.gh_labels = []
        self.safe_save()


class Transaction(base):
    StatusVals = Enum('Pending', 'Cleared')
    _status = db.Column(db.Integer, default=StatusVals.Pending.index)

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Integer)
    livemode = db.Column(db.Boolean)
    stripe_id = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now())
    stripe_created_at = db.Column(db.DateTime)
    last_four = db.Column(db.Integer)
    user = db.relationship('User')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    standard_join = ['status',
                     'StatusVals',
                     'created_at',
                     '-stripe_created_at']

    acl = transaction_acl

    def roles(self, user=None):
        """ Logic to determin what auth roles a user gets """
        if not user:
            user = current_user

        if self.user_id == getattr(user, 'id', None):
            return ['owner']

        if user.is_anonymous():
            return ['anonymous']
        else:
            return ['user']

    @property
    def status(self):
        return self.StatusVals[self._status]


class Earmark(base):
    StatusVals = Enum('Pending', 'Assigned', 'Cleared')
    _status = db.Column(db.Integer, default=StatusVals.Pending.index)

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now())
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    sender = db.relationship('User', foreign_keys=[sender_id])
    reciever_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    reciever = db.relationship('User', foreign_keys=[reciever_id])
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'))
    transaction = db.relationship('Transaction')

    standard_join = ['status',
                     'StatusVals',
                     'created_at',
                     '-stripe_created_at']

    acl = earmark_acl

    def roles(self, user=None):
        """ Logic to determin what auth roles a user gets """
        if not user:
            user = current_user

        if self.reciever_id == getattr(user, 'id', None):
            return ['reciever']

        if self.sender_id == getattr(user, 'id', None):
            return ['sender']

        if user.is_anonymous():
            return ['anonymous']
        else:
            return ['user']

    @property
    def status(self):
        return self.StatusVals[self._status]

    @property
    def matured(self):
        return (datetime.datetime.now() - self.created_at).day >= (amount/100)


class Email(base):
    standard_join = []

    user = db.relationship('User', backref=db.backref('emails'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    address = db.Column(db.String, primary_key=True)
    verified = db.Column(db.Boolean, default=False)
    primary = db.Column(db.Boolean, default=True)


user_table = db.Table('user', metadata,
    # _id
    db.Column('id', db.Integer, primary_key=True),
    db.Column('username', db.String(32), unique=True),
    db.Column('thing_id', db.Integer, db.ForeignKey('thing.id')),

    # User information
    db.Column('created_at', db.DateTime, default=datetime.datetime.now),
    db.Column('_password', db.String),

    # Event information
    db.Column('public_events', EventJSON),
    db.Column('events', EventJSON),

    db.Column('gh_token', db.String),

    # Github sync
    gh_token = db.Column(db.String))


class User(base, SubscribableMixin):
    id = db.column_property(thing_table.c.id, user_table.c.thing_id)
    __table__ = db.join(thing_table, user_table)
    user_id = user_table.c.id

    standard_join = ['id',
                     'gh_linked',
                     'id',
                     'created_at',
                     'user_acl',
                     'get_abs_url',
                     '-_password',
                     '-events',
                     '-public_events',
                     ]
    home_join = inherit_lst(standard_join,
                            [{'obj': 'events',
                              'join_prof': 'standard_join'},
                             {'obj': 'projects',
                              'join_prof': 'disp_join'}])

    page_join = inherit_lst(standard_join,
                            [{'obj': 'public_events',
                              'join_prof': 'disp_join'}])

    settings_join = inherit_lst(standard_join,
                                {'obj': 'primary_email'})

    # used for displaying the project in noifications, etc
    disp_join = ['__dont_mongo',
                 'username',
                 'get_abs_url']

    acl = user_acl

    def roles(self, user=None):
        """ Logic to determin what auth roles a user gets """
        if not user:
            user = current_user

        if self.id == getattr(user, 'id', None):
            return ['owner']

        if user.is_anonymous():
            return ['anonymous']
        else:
            return ['user']

    @property
    def get_dur_url(self):
        return "/u/{id}".format(id=self.id)

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, val):
        self._password = unicode(crypt.encode(val))

    def check_password(self, password):
        return crypt.check(self._password, password)

    @property
    def primary_email(self):
        for email in self.emails:
            if email.primary:
                return email

    @property
    def avatar_lg(self):
        # Set your variables here
        default = "http://www.example.com/default.jpg"
        size = 180

        # construct the url
        gravatar_url = "http://www.gravatar.com/avatar/"
        gravatar_url += hashlib.md5(self.primary_email.lower()).hexdigest()
        gravatar_url += "?" + urllib.urlencode({'d': default, 's': str(size)})

    def get_abs_url(self):
        return "/{username}".format(
            username=unicode(self.username).encode('utf-8'))

    @property
    def projects(self):
        return Project.query.filter_by(maintainer=self)

    def save(self):
        self.username = self.username.lower()
        super(User, self).save()

    # Github Synchronization Logic
    # ========================================================================
    @property
    def gh_linked(self):
        return bool(self.gh_token)

    @property
    def gh(self):
        if 'github_user' not in session:
            session['github_user'] = github.get('user').data
        return session['github_user']

    def gh_repos(self):
        """ Generate a complete list of repositories """
        try:
            return github.get('user/repos').data
        except ValueError:
            self.gh_deauth()

    def gh_deauth(self, flatten=False):
        """ De-authenticates a user and redirects them to their account
        settings with a flash """
        flash("Your GitHub Authentication token was missing when expected, "
              "please re-authenticate.")
        self.gh_token = ''
        for project in self.get_projects():
            project.gh_desync(flatten=flatten)

    def gh_repos_syncable(self):
        """ Generate a list only of repositories that can be synced """
        for repo in self.gh_repos():
            if repo['permissions']['admin']:
                yield repo

    def gh_repo(self, path):
        """ Get a single repositories information from the gh_path """
        return github.get('repos/{0}'.format(path)).data

    # User creation logic
    # ========================================================================
    @classmethod
    def create_user(cls, username, password, email_address):
        user = cls(username=username)
        user.password = password
        user.safe_save()
        Email(address=email_address, user=user).safe_save()

        return user

    @classmethod
    def create_user_github(cls, access_token):
        user = cls(gh_token=access_token).safe_save()
        Email(address=user.gh['email'], user=user).safe_save()
        if not user.safe_save():
            return False
        return user

    # Authentication callbacks
    # ========================================================================
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return unicode(self.id)

    def __str__(self):
        return str(self.username)

    # Convenience functions
    # ========================================================================
    def __repr__(self):
        return '<User %r>' % (self.username)

    def __eq__(self, other):
        """ This returns the actual user object compaison when it's a proxy
        object.  Very useful since we do this for auth checks all the time """
        if isinstance(other, werkzeug.local.LocalProxy):
            return self == other._get_current_object()
        else:
            return self is other

    def get(self):
        return self

    def __get__(self, one, two):
        current_app.logger.debug("{} : {}".format(one, two))
        return self


from . import events as events
