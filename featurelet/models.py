from flask import url_for, session, g, current_app, flash

from . import db, github

import cryptacular.bcrypt
import datetime
import mongoengine
import re
import markdown2
import werkzeug
import json
import bson
import urllib
import hashlib

crypt = cryptacular.bcrypt.BCRYPTPasswordManager()

class SubscribableMixin(object):
    """ A Mixin providing data model utils for subscribing new users. Maintain
    uniqueness of user by hand through these checks """

    def unsubscribe(self, username):
        i = 0
        # locates the index of the user by hand. I'm sure there's some clever
        # lamda to do this
        for sub in self.subscribers:
            if sub.user.username == username:
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
            if sub.user.username == g.user.username:
                return True
        return False

class CommonMixin(object):
    """ mixin for all documents in database. provides some nice utils"""
    def safe_save(self, **kwargs):
        try:
            self.save(**kwargs)
        except Exception:
            catch_error_graceful(form)
            return False
        else:
            return True
        return True

    def jsonize(self, raw=False, **kwargs):
        for key, val in kwargs.items():
            try:
                attr = getattr(self, key)
                if isinstance(attr, db.Document):
                    attr = str(attr.id)
                elif isinstance(attr, bool):
                    pass
                elif callable(attr):
                    try:
                        attr = attr()
                    except TypeError:
                        pass
                else:
                    attr = str(attr)
            except AttributeError:
                pass
            else:
                kwargs[key] = attr
        if raw:
            return kwargs
        else:
            return json.dumps(kwargs)


    meta = {'allow_inheritance': True}

class Email(db.EmbeddedDocument):
    address = db.StringField(max_length=1023, required=True, unique=True)
    verified = db.BooleanField(default=False)
    primary = db.BooleanField(default=True)


class Comment(db.EmbeddedDocument):
    body = db.StringField(min_length=10)
    user = db.ReferenceField('User', required=True)
    time = db.DateTimeField()

    @property
    def md_body(self):
        return markdown2.markdown(self.body)


class Improvement(db.Document, SubscribableMixin, CommonMixin):
    id = db.ObjectIdField()
    # key pair, unique identifier
    url_key = db.StringField(unique=True)
    project = db.ReferenceField('Project')

    brief = db.StringField(max_length=512, min_length=3)
    description = db.StringField(min_length=15)
    creator = db.ReferenceField('User')
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)

    # github synchronization
    gh_synced = db.BooleanField(default=False)
    gh_issue_num = db.IntField()
    gh_labels = db.ListField(db.StringField())

    # voting
    vote_list = db.ListField(db.ReferenceField('User'))
    votes = db.IntField(default=0)

    # event dist
    events = db.ListField(db.GenericEmbeddedDocumentField())
    subscribers = db.ListField(db.EmbeddedDocumentField('ImpSubscriber'))
    meta = {'indexes': [{'fields': ['url_key', 'project'], 'unique': True},
                        {'fields': {'brief': 'text'}}
                        ]}

    standard_join = {'get_abs_url': 1, 'vote_status': 1, 'project': 1}

    def get_abs_url(self):
        return url_for('main.view_improvement',
                       purl_key=self.project.url_key,
                       user=self.project.maintainer.username,
                       url_key=self.url_key)

    def can_edit_imp(self, user):
        return user == self.creator or self.project.can_edit_imp(user)


    def gh_desync(self, flatten=False):
        """ Used to disconnect an improvement from github. Really just a
        trickle down call from de-syncing the project, but nicer to keep the
        logic in here"""
        self.gh_synced = 0
        # Remove indexes if we're flattening
        if flatten:
            self.gh_issue_num = None
            self.gh_labels = []
        try:
            self.save()
        except Exception:
            catch_error_graceful()

    @property
    def md(self):
        return markdown2.markdown(self.description)

    def vote(self, user):
        return Improvement.objects(project=self.project,
                            url_key=self.url_key,
                            vote_list__ne=user.username).\
                    update_one(add_to_set__vote_list=user.username, inc__votes=1)

    def unvote(self, user):
        return Improvement.objects(
            project=self.project,
            url_key=self.url_key,
            vote_list__in=[user.username, ]).\
                update_one(pull__vote_list=user.username, dec__votes=1)


    @property
    def vote_status(self):
        return g.user in self.vote_list

    def create_key(self):
        self.url_key = re.sub('[^0-9a-zA-Z]', '-', self.brief[:100]).lower()

    def add_comment(self, user, body):
        # Send the actual comment to the improvement event queue
        c = Comment(user=user.username, body=body)
        c.distribute(self)

    #def to_json(self):
    #    """ Define how a straight json serialization is generated """
    #    return jsonize(raw=1, url_key=1, project=1, get_abs_url=1, brief=1)
Improvement._get_collection().ensure_index([('brief', 'text')])


class Project(db.Document, SubscribableMixin, CommonMixin):
    id = db.ObjectIdField()
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)
    maintainer = db.ReferenceField('User')
    url_key = db.StringField(min_length=3, max_length=64)

    # description info
    name = db.StringField(max_length=64, min_length=3)
    improvement_count = db.IntField(default=1)  # XXX: Currently not implemented
    website = db.StringField(max_length=2048)
    source_url = db.StringField(max_length=2048)

    # Event log
    subscribers = db.ListField(db.EmbeddedDocumentField('ProjectSubscriber'))
    events = db.ListField(db.GenericEmbeddedDocumentField())

    # Github Syncronization information
    gh_repo_id = db.IntField(default=-1)
    gh_repo_path = db.StringField()
    gh_synced_at = db.DateTimeField()
    gh_synced = db.BooleanField(default=False)

    meta = {'indexes': [{'fields': ['url_key', 'maintainer'], 'unique': True}]}

    @property
    def gh_synced(self):
        return self.gh_repo_id > 0

    def gh_sync(self, data):
        self.gh_repo_id = data['id']
        self.gh_repo_path = data['full_name']
        self.gh_synced = datetime.datetime.now()

    def gh_desync(self, flatten=False):
        """ Used to disconnect a repository from github. By default will leave
        all data in place for re-syncing, but flatten will cause erasure """
        for imp in self.get_improvements():
            imp.gh_desync(flatten=flatten)

        self.gh_synced = False
        # Remove indexes if we're flattening
        if flatten:
            self.gh_synced_at = None
            self.gh_repo_path = None
            self.gh_repo_id = None
        self.safe_save()


    def can_edit_settings(self, user):
        return self.maintainer == user

    def can_edit_imp(self, user):
        return self.maintainer == user

    def can_sync(self, user):
        return self.maintainer == user

    def get_abs_url(self):
        return url_for('main.view_project',
                       username=self.maintainer.username,
                       url_key=self.url_key)

    def get_improvements(self, json=False, join=None):
        vals = Improvement.objects(project=self)
        if json:
            return get_json_joined(vals, join=None)
        return vals

    def add_improvement(self, imp, user):
        imp.create_key()
        imp.project = self
        try:
            imp.save()
        except mongoengine.errors.OperationError:
            return False

        # send a notification to all subscribers that the notification is left
        inotif = ImprovementNotif(user=user.username, imp=imp)
        inotif.distribute()

    def add_comment(self, body, user):
        # Send the actual comment to the improvement event queue
        c = Comment(user=user.username,
                    body=body)
        distribute_event(self, c, "comment", self_send=True)


class ImpSubscriber(db.EmbeddedDocument):
    user = db.ReferenceField('User')
    comment_notif = db.BooleanField(default=True)
    vote = db.BooleanField(default=False)
    status = db.BooleanField(default=True)  # status change event
    donate = db.BooleanField(default=True)


class ProjectSubscriber(db.EmbeddedDocument):
    user = db.ReferenceField('User')
    comment_notif = db.BooleanField(default=True)
    improvement = db.BooleanField(default=True)


class UserSubscriber(db.EmbeddedDocument):
    user = db.ReferenceField('User')
    comment = db.BooleanField(default=True)
    vote = db.BooleanField(default=False)
    improvement = db.BooleanField(default=True)
    project = db.BooleanField(default=True)


class User(db.Document, SubscribableMixin, CommonMixin):
    # _id
    username = db.StringField(max_length=32, min_length=3, primary_key=True)

    # User information
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)
    _password = db.StringField(max_length=128, min_length=5, required=True)
    emails = db.ListField(db.EmbeddedDocumentField('Email'))

    # Event information
    subscribers = db.ListField(db.EmbeddedDocumentField(UserSubscriber))
    public_events = db.ListField(db.GenericEmbeddedDocumentField())
    events = db.ListField(db.GenericEmbeddedDocumentField())

    # Github sync
    gh_token = db.StringField()

    meta = {'indexes': [{'fields': ['gh_token'], 'unique': True, 'sparse': True}]}

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, val):
        self._password = unicode(crypt.encode(val))

    def check_password(self, password):
        return crypt.check(self._password, password)

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

    def get_abs_url(self):
        return url_for('main.user', username=unicode(self.username).encode('utf-8'))

    def get_projects(self):
        return Project.objects(maintainer=self)

    def save(self):
        self.username = self.username.lower()
        super(User, self).save()

    # Authentication callbacks
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return unicode(self.username)

    def __str__(self):
        return self.username

    # Convenience functions
    def __repr__(self):
        return '<User %r>' % (self.username)

    def __eq__(self, other):
        """ This returns the actual user object compaison when it's a proxy object.
        Very useful since we do this for auth checks all the time """
        if isinstance(other, werkzeug.local.LocalProxy):
            return self == other._get_current_object()
        else:
            return super(User, self).__eq__(other)


from .events import (ImprovementNotif, CommentNotif, Comment)
from .lib import (catch_error_graceful, get_json_joined)
