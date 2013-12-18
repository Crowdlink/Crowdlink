from flask import session, current_app, flash
from flask.ext.login import current_user
from datetime import datetime

from . import db, github
from .util import inherit_lst
from .acl import issue_acl, project_acl, solution_acl, user_acl

from flask.ext.sqlalchemy import (_BoundDeclarativeMeta, BaseQuery,
                                  _QueryProperty)
from sqlalchemy.ext.declarative import declarative_base
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
import calendar

crypt = cryptacular.bcrypt.BCRYPTPasswordManager()


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
        current_app.logger.debug((self.roles(), action, self.user_acl))
        return action in self.user_acl

    @property
    def user_acl(self):
        """ a lazy loaded acl list for the current user """
        # Run an extra check to ensure we don't hand out an acl list for the
        # wrong user. Possibly un-neccesary, I'm paranoid
        if not hasattr(self, '_user_acl') or self._user_acl[0] != current_user:
            self._user_acl = (current_user, self.get_acl())
        return self._user_acl[1]

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


class PrivateMixin(object):
    """ Common methods for objects that are private """
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


# setup our base mapper and database metadata
metadata = db.MetaData()
base = declarative_base(cls=BaseMapper,
                        metaclass=_BoundDeclarativeMeta,
                        metadata=metadata,
                        name='Model')
base.query = _QueryProperty(db)
db.Model = base


# our parent table for issues, projects, solutions and users
class Thing(base):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String)
    __mapper_args__ = {
        'polymorphic_identity': 'Thing',
        'polymorphic_on': type
    }

    def clear_earmarks(self):
        """ """
        for earmark in self.earmarks:
            earmark.clear()


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
    votee = db.relationship('Thing')


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
            vote.save(sqlalchemy.exc.IntegrityError)
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
    subscribee = db.relationship('Thing')


class SubscribableMixin(object):
    """ A Mixin providing data model utils for subscribing new users. Maintain
    uniqueness of user by hand through these checks """

    def unsubscribe(self, user=None):
        if user is None:
            user = current_user
        Subscription.query.filter_by(
            subscriber=user.get(),
            subscribee_id=self.id).delete()
        # remove all events that originate from the source they're
        # unsubscribing
        user.events = [e for e in user.events if not e.originates(self.id)]

        current_app.logger.debug(
            ("Unsubscribing on {} as user "
             "{}").format(self.__class__.__name__, user.username))
        return True

    def subscribe(self, user=None):
        if user is None:
            user = current_user

        current_app.logger.debug(
            ("Subscribing on {} as user "
             "{}").format(self.__class__.__name__, user.username))
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

    @property
    def subscribed(self, user=None):
        if user is None:
            user = current_user
        if not user.is_anonymous():
            return bool(Subscription.query.filter_by(
                subscriber=user.get(),
                subscribee_id=self.id).first())

    @property
    def subscribers(self):
        return Subscription.query.filter_by(subscribee_id=self.id)


class Project(Thing, SubscribableMixin, VotableMixin):
    """ This class is a composite of thing and project tables """
    id = db.Column(db.Integer, db.ForeignKey('thing.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    maintainer_username = db.Column(db.String, db.ForeignKey('user.username'))
    maintainer = db.relationship('User')
    url_key = db.Column(db.String)

    # description info
    name = db.Column(db.String(128))
    website = db.Column(db.String(256))
    desc = db.Column(db.String)
    issue_count = db.Column(db.Integer)  # XXX: Currently not implemented

    # voting
    votes = db.Column(db.Integer, default=0)

    # Event log
    public_events = db.Column(EventJSON)

    # Github Syncronization information
    gh_repo_id = db.Column(db.Integer, default=-1)
    gh_repo_path = db.Column(db.String)
    gh_synced_at = db.Column(db.DateTime)
    gh_synced = db.Column(db.Boolean, default=False)
    maintainer = db.relationship('User',
                                 foreign_keys='Project.maintainer_username')
    __table_args__ = (
        db.UniqueConstraint("url_key", "maintainer_username"),
    )
    __mapper_args__ = {'polymorphic_identity': 'Project'}

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
                     '-public_events'
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
                             {'obj': 'public_events'},
                             ]
                            )

    # Import the acl from acl file
    acl = project_acl

    def issues(self):
        return Issue.query.filter_by(project=self)

    def roles(self, user=None):
        """ Logic to determin what auth roles a user gets """
        if user is None:
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
        issue.save()

        # send a notification to all subscribers
        events.IssueNotif.generate(issue)

    def add_comment(self, body, user):
        # Send the actual comment to the issue event queue
        #c = Comment(user=user, body=body)
        pass

    # Github Synchronization Logic
    # ========================================================================
    @property
    def gh_sync_meta(self):
        return self.gh_repo_id > 0

    def gh_sync(self, data):
        self.gh_repo_id = data['id']
        self.gh_repo_path = data['full_name']
        self.gh_synced_at = datetime.utcnow()
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
        self.save()
        current_app.logger.debug("Desynchronized repository")


class Issue(StatusMixin, Thing, SubscribableMixin, VotableMixin):
    id = db.Column(db.Integer, db.ForeignKey('thing.id'), primary_key=True)

    StatusVals = Enum('Completed', 'Discussion', 'Selected', 'Other')
    _status = db.Column(db.Integer, default=StatusVals.Discussion.index)
    title = db.Column(db.String(128))
    desc = db.Column(db.Text)
    creator = db.relationship('User')
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # voting
    votes = db.Column(db.Integer, default=0)

    # Event log
    public_events = db.Column(EventJSON)

    # our project relationship and keys
    url_key = db.Column(db.String, unique=True)
    project = db.relationship('Project')
    project_url_key = db.Column(db.String)
    project_maintainer_username = db.Column(db.String)
    __table_args__ = (
        db.ForeignKeyConstraint(
            [project_url_key, project_maintainer_username],
            [Project.url_key, Project.maintainer_username]),
        db.UniqueConstraint("url_key",
                            "project_maintainer_username",
                            "project_url_key"),
        {})
    project = db.relationship(
        'Project',
        foreign_keys='[Issue.project_url_key, Issue.project_maintainer_username]')
    creator = db.relationship('User', foreign_keys='Issue.creator_id')
    __mapper_args__ = {'polymorphic_identity': 'Issue'}

    acl = issue_acl
    standard_join = ['get_abs_url',
                     'title',
                     'vote_status',
                     'status',
                     'subscribed',
                     'user_acl',
                     'created_at',
                     'id',
                     '-public_events',
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
        self.save()


class Solution(Thing, SubscribableMixin, VotableMixin):
    """ A composite of the solution table and the thing table.

    Solutions are attributes of Issues that can be voted on, commented on etc
    """

    id = db.Column(db.Integer, db.ForeignKey('thing.id'), primary_key=True)
    title = db.Column(db.String(128))
    desc = db.Column(db.Text)
    creator = db.relationship('User')
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # voting
    votes = db.Column(db.Integer, default=0)

    # Event log
    public_events = db.Column(EventJSON)

    # our project relationship and all keys
    url_key = db.Column(db.String, unique=True)
    project = db.relationship('Project')
    project_url_key = db.Column(db.String)
    project_maintainer_username = db.Column(db.String)
    issue = db.relationship('Issue')
    issue_url_key = db.Column(db.String)
    __table_args__ = (
        db.ForeignKeyConstraint(
            [project_url_key, project_maintainer_username],
            [Project.url_key, Project.maintainer_username]),
        db.ForeignKeyConstraint(
            [project_url_key, project_maintainer_username, issue_url_key],
            [Issue.project_url_key, Issue.project_maintainer_username, Issue.url_key]),
        {})

    project = db.relationship(
        'Project',
        foreign_keys='[Solution.project_url_key, Solution.project_maintainer_username]')
    issue = db.relationship(
        'Issue',
        foreign_keys='[Solution.issue_url_key, Solution.project_url_key, Solution.project_maintainer_username]')
    creator = db.relationship('User', foreign_keys='Solution.creator_id')
    __mapper_args__ = {'polymorphic_identity': 'Solution'}

    acl = solution_acl
    standard_join = ['get_abs_url',
                     'title',
                     'subscribed',
                     'user_acl',
                     'created_at',
                     '-public_events',
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
        self.save()


class Email(base):
    standard_join = []

    user = db.relationship('User', backref=db.backref('emails'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    address = db.Column(db.String, primary_key=True)
    verified = db.Column(db.Boolean, default=False)
    primary = db.Column(db.Boolean, default=True)

    @classmethod
    def activate_email(self, email):
        Email.query.filter_by(address=email).update({'verified': True})


class User(Thing, SubscribableMixin):
    id = db.Column(db.Integer, db.ForeignKey('thing.id'), primary_key=True)
    username = db.Column(db.String(32), unique=True)
    admin = db.Column(db.Boolean, default=False)

    # User information
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    _password = db.Column(db.String)
    gh_token = db.Column(db.String, unique=True)

    # Event information
    public_events = db.Column(EventJSON)
    events = db.Column(EventJSON)
    __mapper_args__ = {'polymorphic_identity': 'User'}

    # financial placeholders

    # total unpaid
    current_balance = db.Column(db.Integer, default=0)
    # total available for earmarks
    available_balance = db.Column(db.Integer, default=0)

    standard_join = ['id',
                     'gh_linked',
                     'id',
                     'created_at',
                     'user_acl',
                     'get_abs_url',
                     '-_password',
                     '-public_events',
                     '-events',
                     ]
    home_join = inherit_lst(standard_join,
                            [{'obj': 'events'},
                             {'obj': 'projects',
                              'join_prof': 'disp_join'}])

    page_join = inherit_lst(standard_join,
                            [{'obj': 'public_events'}])

    settings_join = inherit_lst(standard_join,
                                {'obj': 'primary_email'})

    # used for displaying the project in noifications, etc
    disp_join = ['__dont_mongo',
                 'username',
                 'get_abs_url']

    acl = user_acl

    @property
    def available_marks(self):
        return sum([m.remaining for m in Mark.query.filter(user == user and cleared is True)])
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
        user.save()
        Email(address=email_address, user=user).save()

        return user

    @classmethod
    def create_user_github(cls, access_token):
        user = cls(gh_token=access_token).save()
        Email(address=user.gh['email'], user=user).save()
        if not user.save():
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

    # Convenience functions
    # ========================================================================
    def __eq__(self, other):
        """ This returns the actual user object compaison when it's a proxy
        object.  Very useful since we do this for auth checks all the time """
        if isinstance(other, werkzeug.local.LocalProxy):
            return self == other._get_current_object()
        else:
            return self is other

    def get(self):
        return self


from . import events as events
