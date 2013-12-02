from flask import url_for, session, g, current_app, flash

from . import db, github
from .exc import AccessDenied
from .util import flatten_dict, inherit_lst
from .acl import issue_acl, project_acl, solution_acl

from sqlalchemy.types import TypeDecorator, VARCHAR
from sqlalchemy.dialects.postgresql import HSTORE
from sqlalchemy.ext.declarative import declared_attr

from enum import Enum

import cryptacular.bcrypt
import re
import werkzeug
import json
import bson
import urllib
import hashlib
import datetime
import calendar

crypt = cryptacular.bcrypt.BCRYPTPasswordManager()

class JSONEncodedDict(TypeDecorator):
    """Represents an immutable structure as a json-encoded string.

    Usage::

        JSONEncodedDict(255)

    """

    impl = VARCHAR

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)

        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value

class VotableMixin(object):
    """ A Mixin providing data model utils for subscribing new users. Maintain
    uniqueness of user by hand through these checks """


    def set_vote(self, vote):
        """ save isn't needed, this operation must be atomic """
        stat = self.vote_status
        idval = g.user.id
        if stat and not vote:
            return bool(self.__class__.objects(
                id=self.id,
                vote_list__in=[idval, ]).\
                    update_one(pull__vote_list=idval, dec__votes=1))
        elif not stat and vote:
            return bool(self.__class__.objects(id=self.id,
                            vote_list__ne=idval).\
                    update_one(add_to_set__vote_list=idval, inc__votes=1))

        return "already_set"

    @property
    def vote_status(self):
        return g.user in self.vote_list



class SubscribableMixin(object):
    """ A Mixin providing data model utils for subscribing new users. Maintain
    uniqueness of user by hand through these checks """


    def unsubscribe(self, user):
        i = 0
        # locates the index of the user by hand. I'm sure there's some clever
        # lamda to do this
        for sub in self.subscribers:
            if sub.user == user:
                break
            i += 1
        else:
            return False  # Return false if list exhausted, failure
        # I feel uneasy about defaulting to remove i, but hopefully...
        del self.subscribers[i]

    def subscribe(self, sub_obj):
        # ensure that the user key is unique
        for sub in self.subscribers:
            if sub.user == sub_obj.user:
                return False  # err, shouldn't have been present
        self.subscribers.append(sub_obj)


    @property
    def subscribed(self):
        # search the list of subscribers looking for the current user
        for sub in self.subscribers:
            if sub.user == g.user:
                return True
        return False

"""
class IssueSubscriber(db.EmbeddedDocument):
    user = db.ReferenceField('User')
    comment_notif = db.BooleanField(default=True)
    vote = db.BooleanField(default=False)
    status = db.BooleanField(default=True)  # status change event
    donate = db.BooleanField(default=True)


class SolutionSubscriber(db.EmbeddedDocument):
    user = db.ReferenceField('User')
    comment_notif = db.BooleanField(default=True)
    vote = db.BooleanField(default=False)
    status = db.BooleanField(default=True)  # status change event


class ProjectSubscriber(db.EmbeddedDocument):
    user = db.ReferenceField('User')
    comment_notif = db.BooleanField(default=True)
    issue = db.BooleanField(default=True)


class UserSubscriber(db.EmbeddedDocument):
    user = db.ReferenceField('User')
    comment = db.BooleanField(default=True)
    vote = db.BooleanField(default=False)
    issue = db.BooleanField(default=True)
    project = db.BooleanField(default=True)
"""


class CommonMixin(object):
    """ mixin for all documents in database. provides some nice utils"""
    safe_set = True
    standard_join = []
    acl = {}

    def get_acl(self, user=None):
        """ Generates an acl list for a specific user which defaults to the
        authed user """
        if not user:
            user = g.user
        roles = self.roles(user=user)
        allowed = set()
        for role in roles:
            allowed |= set(self.acl.get(role, []))

        return allowed

    def roles(user=None):
        """ This should be overriden to use logic for determining roles """
        if not user:
            user = g.user
        return []

    def can(self, action):
        """ Can the user perform the action needed? """
        current_app.logger.debug((action, self.user_acl))
        return action in self.user_acl

    def unsafe_set(self, attr, setter):
        """ Sets the attribute without a security check """
        return super(CommonMixin, self).__setattr__(value)

    @property
    def user_acl(self):
        """ a lazy loaded acl list for the current user """
        # Run an extra check to ensure we don't hand out an acl list for the
        # wrong user. Possibly un-neccesary, I'm paranoid
        if not hasattr(self, '_user_acl') or self._user_acl[0] != g.user:
            self._user_acl = (g.user, self.get_acl())
        return self._user_acl[1]

    def safe_save(self, **kwargs):
        """ Catches a bunch of common mongodb errors when saving and handles
        them appropriately. A convenient wrapper around catch_error_graceful.
        """
        form = kwargs.pop('form', None)
        flash = kwargs.pop('flash', False)
        try:
            self.save(**kwargs)
        except Exception:
            catch_error_graceful(
                form=form,
                out_flash=flash
            )
            return False
        else:
            return True
        return True

    def jsonize(self, args, raw=False):
        """ Used to join attributes or functions to an objects json representation.
        For passing back object state via the api
        """
        dct = {}
        for key in args:
            attr = getattr(self, key, 1)
            if isinstance(attr, db.Model):
                attr = str(attr.id)
            if isinstance(attr, Enum):
                attr = dict({str(x): x.index for x in attr})
            elif isinstance(attr, datetime.datetime):
                attr = calendar.timegm(attr.utctimetuple()) * 1000
            elif isinstance(attr, bool): # don't convert bool to str
                pass
            elif isinstance(attr, set): # don't convert bool to str
                attr = {x: True for x in attr}
            elif callable(attr):
                attr = attr()
            else:
                attr = str(attr)
            dct[key] = attr

        if raw:
            return dct
        else:
            return json.dumps(dct)


    meta = {'allow_inheritance': True}

"""
class Comment(db.EmbeddedDocument):
    body = db.StringField(min_length=10)
    user = db.ReferenceField('User', required=True)
    time = db.DateTimeField()

    @property
    def md_body(self):
        return markdown2.markdown(self.body)
"""


class Solution(db.Model, SubscribableMixin, VotableMixin, CommonMixin):

    id = db.Column(db.Integer, primary_key=True)
    # key pair, unique identifier
    url_key = db.Column(db.String, unique=True)
    issue = db.relationship('Issue')
    project = db.relationship('Project')

    title = db.Column(db.String(128))
    desc = db.Column(db.Text)
    creator = db.relationship('User')
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)

    # voting
    votes = db.Column(db.Integer, default=0)

    # Event log
    events = db.Column(JSONEncodedDict)

    meta = {'indexes': [{'fields': ['url_key', 'issue'], 'unique': True}]}
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
            user = g.user

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

    # Closevalue masking for render
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
            self.url_key = re.sub('[^0-9a-zA-Z]', '-', self.title[:100]).lower()

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
        try:
            self.save()
        except Exception:
            catch_error_graceful()

class Issue(db.Model, SubscribableMixin, VotableMixin, CommonMixin):

    statuses = Enum('Completed', 'Discussion', 'Selected', 'Other')

    id = db.Column(db.Integer, primary_key=True)
    # key pair, unique identifier
    url_key = db.Column(db.String, unique=True)
    project = db.relationship('Project')

    _status = db.Column(db.Integer, default=statuses.Discussion.index)
    title = db.Column(db.String(128))
    desc = db.Column(db.Text)
    creator = db.relationship('User')
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)

    # voting
    votes = db.Column(db.Integer, default=0)

    # Event log
    events = db.Column(JSONEncodedDict)

    meta = {'indexes': [{'fields': ['url_key', 'project'], 'unique': True}]}
    acl = issue_acl
    standard_join = ['get_abs_url',
                     'title',
                     'vote_status',
                     'status',
                     'subscribed',
                     'user_acl',
                     'created_at',
                     '-vote_list',
                     '-subscribers',
                     'id',
                     ]
    page_join = inherit_lst(standard_join,
                             [{'obj': 'project',
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
        return Solution.objects(issue=self)

    def roles(self, user=None):
        """ Logic to determin what roles a person gets """
        if not user:
            user = g.user

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

    # Closevalue masking for render
    def get_abs_url(self):
        return "/{username}/{purl_key}/{url_key}".format(
            purl_key=self.project.url_key,
            username=self.project.maintainer.username,
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
            self.url_key = re.sub('[^0-9a-zA-Z]', '-', self.title[:100]).lower()

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
        try:
            self.save()
        except Exception:
            catch_error_graceful()


class Project(db.Model, SubscribableMixin, VotableMixin, CommonMixin):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    maintainer = db.relationship('User')
    username = db.Column(db.String)
    url_key = db.Column(db.String)

    # description info
    name = db.Column(db.String)
    website = db.Column(db.String)
    desc = db.Column(db.String)
    issue_count = db.Column(db.Integer)  # XXX: Currently not implemented

    # voting
    votes = db.Column(db.Integer, default=0)

    # Event log
    events = db.Column(JSONEncodedDict)

    # Github Syncronization information
    gh_repo_id = db.Column(db.Integer, default=-1)
    gh_repo_path = db.Column(db.String)
    gh_synced_at = db.Column(db.DateTime)
    gh_synced = db.Column(db.Boolean, default=False)

    # Join profiles
    standard_join = ['get_abs_url',
                     'maintainer',
                     'user_acl',
                     'created_at',
                     'username',
                     'id',
                     '-vote_list',
                     '-events'
                    ]
    # used for displaying the project in noifications, etc
    disp_join = ['__dont_mongo',
                 'name',
                 'get_abs_url',
                 'username']
    issue_page_join = ['__dont_mongo', 'name', 'username', 'get_abs_url']
    page_join = inherit_lst(standard_join,
                             ['__dont_mongo',
                              'name',
                              'subscribed',
                              'vote_status',
                              {'obj': 'maintainer',
                               'join_prof': "disp_join"},
                              {'obj': 'events'},
                              ]
)
    acl = project_acl
    meta = {'indexes': [{'fields': ['url_key', 'maintainer'], 'unique': True}]}

    def issues(self):
        return Issue.objects(project=self)

    def roles(self, user=None):
        """ Logic to determin what auth roles a user gets """
        if not user:
            user = g.user

        if self.maintainer == user:
            return ['maintainer']

        if user.is_anonymous():
            return ['anonymous']
        else:
            return ['user']

    @property
    def get_abs_url(self):
        return "/{username}/{url_key}/".format(
                       username=self.username,
                       url_key=self.url_key)

    def add_issue(self, issue, user):
        """ Add a new issue to this project """
        issue.create_key()
        issue.project = self
        try:
            issue.save()
        except mongoengine.errors.OperationError:
            return False

        # send a notification to all subscribers
        #inotif = IssueNotif(user=user.id, issue=issue)
        #inotif.distribute()

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


class Transaction(db.Model, CommonMixin):
    StatusVals = Enum('Pending', 'Cleared')
    _status = db.Column(db.Integer, default=StatusVals.Pending.index)

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Numeric(precision=2))
    livemode = db.Column(db.Boolean)
    stripe_id = db.Column(db.String)
    created = db.Column(db.DateTime)
    last_four = db.Column(db.Integer)
    user = db.relationship('User')

    standard_join = ['status']
    meta = {
        'ordering': ['-created']
    }
    # Closevalue masking for render
    @property
    def status(self):
        return self.StatusVals[self._status]


"""
class Email(db.EmbeddedDocument, CommonMixin):
    standard_join = []

    address = db.StringField(max_length=1023, required=True, unique=True)
    verified = db.BooleanField(default=False)
    primary = db.BooleanField(default=True)
"""

class SubscriptionBase(object):
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    @declared_attr
    def subscriber(cls):
        return db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    # the distribution rules for this subscription
    rules = db.Column(HSTORE)

class IssueSubscription(db.Model, SubscriptionBase):
    subscribee = db.Column(db.Integer, db.ForeignKey("issue.id"), primary_key=True)

class SolutionSubscription(db.Model, SubscriptionBase):
    subscribee = db.Column(db.Integer, db.ForeignKey("solution.id"), primary_key=True)

class UserSubscription(db.Model, SubscriptionBase):
    subscribee = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)

class ProjectSubscription(db.Model, SubscriptionBase):
    subscribee = db.Column(db.Integer, db.ForeignKey("project.id"), primary_key=True)

class User(db.Model, SubscribableMixin, CommonMixin):
    # _id
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True)

    # User information
    created_at = db.Column(db.DateTime, default=datetime.datetime.now)
    _password = db.Column(db.String)
    #emails = db.Column(db.EmbeddedDocumentField('Email'))

    # Event information
    public_events = db.Column(JSONEncodedDict)
    events = db.Column(JSONEncodedDict)

    # Github sync
    gh_token = db.Column(db.String)

    meta = {'indexes': [{'fields': ['gh_token'], 'unique': True, 'sparse': True}]}
    standard_join = ['gh_linked',
                     'id',
                     'subscribed',
                     'created_at',
                     '-_password',
                     {'obj': 'primary_email'}
                    ]
    home_join = inherit_lst(standard_join,
                            [{'obj': 'events'},
                             {'obj': 'projects',
                              'join_prof': 'disp_join'}])


    # used for displaying the project in noifications, etc
    disp_join = ['__dont_mongo',
                 'username',
                 'get_abs_url']

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
        gravatar_url = "http://www.gravatar.com/avatar/" + hashlib.md5(self.primary_email.lower()).hexdigest() + "?"
        gravatar_url += urllib.urlencode({'d':default, 's':str(size)})

    def get_abs_url(self):
        return "/{username}".format(username=unicode(self.username).encode('utf-8'))

    @property
    def projects(self):
        return Project.objects(maintainer=self)

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
        flash("Your GitHub Authentication token was missing when expected, please re-authenticate.")
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
        try:
            email = Email(address=email_address)
            user = cls(emails=[email], username=username)
            user.password = password
            user.save()
        except Exception:
            catch_error_graceful()

        return user

    @classmethod
    def create_user_github(cls, access_token):
        user = cls(gh_token=access_token)
        try:
            email = Email(address=user.gh['email'])
            user.save()
        except mongoengine.errors.OperationError:
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
        """ This returns the actual user object compaison when it's a proxy object.
        Very useful since we do this for auth checks all the time """
        if isinstance(other, werkzeug.local.LocalProxy):
            return self == other._get_current_object()
        else:
            return super(User, self).__eq__(other)

    def get(self):
        return self


#from .events import (IssueNotif, CommentNotif, Comment)
from .lib import (catch_error_graceful, get_json_joined)
