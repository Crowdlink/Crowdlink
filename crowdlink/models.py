from flask import session, current_app, flash
from flask.ext.login import current_user
from datetime import datetime, timedelta
from enum import Enum

from . import db, github, crypt
from .model_lib import (base, SubscribableMixin, VotableMixin, EventJSON,
                        StatusMixin, PrivateMixin, ReportableMixin)
from .fin_models import Mark, Earmark
from .util import inherit_lst
from .acl import acl

import valideer as V
import re
import werkzeug
import urllib
import hashlib
import os


# our parent table for issues, projects, solutions and users
class Thing(base):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String)
    __mapper_args__ = {
        'polymorphic_identity': 'Thing',
        'polymorphic_on': type
    }

    @property
    def dispute_percentage(self):
        return (self.earmarks.count() /
                self.earmarks.filter(disputed=True).count())


class Project(Thing, SubscribableMixin, VotableMixin, ReportableMixin):
    """ This class is a composite of thing and project tables """
    id = db.Column(db.Integer, db.ForeignKey('thing.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    maintainer_username = db.Column(db.String, db.ForeignKey('user.username'))
    url_key = db.Column(db.String)

    # description info
    name = db.Column(db.String(128))
    website = db.Column(db.String(256))
    desc = db.Column(db.String)
    issue_count = db.Column(db.Integer)  # XXX: Currently not implemented

    # voting
    votes = db.Column(db.Integer, default=0)

    # Event log
    public_events = db.Column(EventJSON, default=list)

    # Github Syncronization information
    gh_repo_id = db.Column(db.Integer, default=-1)
    gh_repo_path = db.Column(db.String)
    gh_synced_at = db.Column(db.DateTime)
    gh_synced = db.Column(db.Boolean, default=False)
    maintainer = db.relationship('User',
                                 foreign_keys='Project.maintainer_username',
                                 backref='projects')
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
                     'report_status',
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
                             {'obj': 'issues', 'join_prof': 'disp_join'},
                             ]
                            )

    # Import the acl from acl file
    acl = acl['project']

    def roles(self, user=current_user):
        if self.maintainer == user:
            return ['maintainer']
        return []

    @property
    def get_dur_url(self):
        return "/p/{id}".format(id=self.id)

    @property
    def get_abs_url(self):
        return "/{username}/{url_key}/".format(
            username=self.maintainer_username,
            url_key=self.url_key)

    @classmethod
    def create(cls, name, url_key, website="", desc="", user=current_user):
        project = cls(name=name,
                      url_key=url_key,
                      website=website,
                      desc=desc,
                      maintainer=user)

        db.session.add(project)

        # TODO: XXX: Needs an event to be distributed here
        return project

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


class Issue(
        StatusMixin, Thing, SubscribableMixin, VotableMixin, ReportableMixin):
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
    public_events = db.Column(EventJSON, default=list)

    # our project relationship and keys
    url_key = db.Column(db.String, unique=True)
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
        foreign_keys='[Issue.project_url_key, Issue.project_maintainer_username]',
        backref='issues')
    creator = db.relationship('User', foreign_keys='Issue.creator_id')

    comments = db.relationship(
        'Comment',
        order_by='Comment.created_at',
        primaryjoin='Comment.thing_id == Thing.id and Comment.banned == False and Comment.hidden == False')

    hidden_comments = db.relationship(
        'Comment',
        order_by='Comment.created_at',
        primaryjoin='Comment.thing_id == Thing.id and Comment.banned == False')

    __mapper_args__ = {'polymorphic_identity': 'Issue'}

    acl = acl['issue']
    standard_join = ['get_abs_url',
                     'title',
                     'vote_status',
                     'report_status',
                     'status',
                     'subscribed',
                     'user_acl',
                     'created_at',
                     'id',
                     '-public_events',
                     ]
    page_join = inherit_lst(standard_join,
                            ['get_project_abs_url',
                             {'obj': 'project', 'join_prof': 'issue_page_join'},
                             {'obj': 'solutions', 'join_prof': 'standard_join'},
                             {'obj': 'comments', 'join_prof': 'standard_join'},
                             'StatusVals']
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

    def roles(self, user=current_user):
        roles = Issue.p_roles(project=self.project, user=user)
        if self.creator == user:
            roles.append('creator')
        return roles

    @classmethod
    def p_roles(cls, project=None, user=current_user):
        return cls._inherit_roles(project=project, user=user)

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

    @classmethod
    def create(cls, title, project, desc="", user=current_user):
        """ Add a new issue to this project """
        issue = cls(title=title,
                    desc=desc,
                    project=project,
                    creator=user.get())
        issue.create_key()
        db.session.add(issue)

        # send a notification to all subscribers
        events.IssueNotif.generate(issue)

        return issue


class Solution(
        Thing, SubscribableMixin, VotableMixin, StatusMixin, ReportableMixin):
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
    public_events = db.Column(EventJSON, default=list)

    # our project relationship and all keys
    url_key = db.Column(db.String, unique=True)
    project_url_key = db.Column(db.String)
    project_maintainer_username = db.Column(db.String)
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
        foreign_keys='[Solution.issue_url_key, Solution.project_url_key, Solution.project_maintainer_username]',
        backref='solutions')
    creator = db.relationship('User', foreign_keys='Solution.creator_id')
    __mapper_args__ = {'polymorphic_identity': 'Solution'}

    acl = acl['solution']
    standard_join = ['get_abs_url',
                     'title',
                     'report_status',
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
    disp_join = ['__dont_mongo',
                 'title',
                 'get_abs_url']

    def roles(self, user=current_user):
        roles = Solution.p_roles(issue=self.issue)
        if self.creator == user or 'maintainer':
            roles.append('creator')
        return roles

    @classmethod
    def p_roles(cls, issue=None, user=current_user):
        return cls._inherit_roles(issue=issue, user=user)

    @property
    def get_dur_url(self):
        return "/s/{id}".format(id=self.id)

    @property
    def get_abs_url(self):
        return "/{username}/{purl_key}/{iurl_key}/{url_key}".format(
            username=self.project_maintainer_username,
            purl_key=self.project_url_key,
            iurl_key=self.issue_url_key,
            url_key=self.url_key)

    def create_key(self):
        if self.title:
            self.url_key = re.sub(
                '[^0-9a-zA-Z]', '-', self.title[:100]).lower()

    @classmethod
    def create(cls, title, issue, desc="", user=current_user):
        """ Add a new issue to this project """
        sol = cls(title=title,
                  desc=desc,
                  issue=issue,
                  creator=user.get())
        sol.create_key()
        db.session.add(sol)

        # send a notification to all subscribers
        #events.IssueNotif.generate(issue)
        # TODO: Add event for solution creation

        return sol


class Comment(base):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', foreign_keys=[user_id])
    message = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    thing_id = db.Column(db.Integer, db.ForeignKey('thing.id'), nullable=False)
    thing = db.relationship('Thing')
    hidden = db.Column(db.Boolean, default=False)
    banned = db.Column(db.Boolean, default=False)

    acl = acl['comment']

    @classmethod
    def p_roles(cls, thing=None, user=current_user):
        return cls._inherit_roles(thing=thing, user=user)

    def roles(self, user=current_user):
        roles = Comment.p_roles(thing=self.thing)
        if user == self.user:
            roles += ['creator']
        return roles

    standard_join = [{'obj': 'user', 'join_prof': 'disp_join'},
                     'message',
                     'created_at']

    @classmethod
    def create(self, message, thing, user=current_user):
        comment = Comment(message=message,
                          thing=thing,
                          user=user)
        db.session.add(comment)
        # TODO: XXX: Add event for comment creation here
        return comment


class Email(base):
    standard_join = []

    user = db.relationship('User', backref=db.backref('emails'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    address = db.Column(db.String, primary_key=True)
    verified = db.Column(db.Boolean, default=False, nullable=False)
    primary = db.Column(db.Boolean, nullable=False)
    activate_hash = db.Column(db.String)
    hash_gen = db.Column(db.DateTime)

    @classmethod
    def activate_email(self, email, activate_hash="", force=False):
        if force:
            return bool(Email.query
                        .filter_by(address=email)
                        .update({'verified': True}))
        else:
            day_ago = datetime.utcnow() - timedelta(days=1)
            return bool(Email.query
                        .filter_by(address=email, activate_hash=activate_hash)
                        .filter(Email.hash_gen > day_ago)
                        .update({'verified': True, 'hash_gen': None, 'activate_hash': None}))

    @classmethod
    def create(cls, address, user):
        inst = cls(address=address,
                   user=user)

        db.session.add(inst)

    def send_activation(self):
        """ Regenerates activation hashes and time markers and commits the
        change.  If the commit action is successful, an email will be sent to
        the user """
        self.activate_hash = hashlib.sha256(os.urandom(10)).hexdigest()
        self.hash_gen = datetime.utcnow()

        db.session.commit()

        return send_email(
            self.address,
            'confirm',
            activate_hash=self.activate_hash,
            user_id=self.user_id)


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


class User(Thing, SubscribableMixin, ReportableMixin):
    id = db.Column(db.Integer, db.ForeignKey('thing.id'), primary_key=True)
    username = db.Column(db.String(32), unique=True)
    admin = db.Column(db.Boolean, default=False)

    # User information
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    _password = db.Column(db.String)
    gh_token = db.Column(db.String, unique=True)

    # Event information
    public_events = db.Column(EventJSON, default=list)
    events = db.Column(EventJSON, default=list)
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
                     'roles',
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
                                [{'obj': 'primary_email'}])

    # used for displaying the project in noifications, etc
    disp_join = ['__dont_mongo',
                 'username',
                 'get_abs_url']

    acl = acl['user']

    @property
    def available_marks(self):
        return sum([m.remaining for m in Mark.query.filter(
            Mark.user == self and Mark.cleared is True)])

    def roles(self, user=current_user):
        if self.id == getattr(user, 'id', None):
            return ['owner']
        return []

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

    def save(self):
        self.username = self.username.lower()
        super(User, self).save()

    def global_roles(self):
        """ Determines global roles for the user. """
        if self.admin:
            return ['admin']
        if self.username is None:
            return ['usernameless']
        if not self.primary_email.verified:
            return ['noactive_user']
        return ['user']

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
    def create(cls, username, password, email_address):
        user = cls(username=username)
        user.password = password
        db.session.add(user)
        email = Email(address=email_address, user=user, primary=True)
        db.session.add(email)
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
            return self.id == other._get_current_object().id
        else:
            return self.id is other.id

    def get(self):
        return self

from . import events as events
from .lib import send_email
