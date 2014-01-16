from flask import session, current_app
from flask.ext.login import current_user, login_user
from datetime import datetime, timedelta
try:
    from urlparse import urljoin
    from urllib import urlencode
except ImportError:
    from urllib.parse import urljoin, urlencode

from . import db, crypt, github
from .model_lib import (base, SubscribableMixin, VotableMixin, EventJSON,
                        ReportableMixin, JSONEncodedDict)
from .util import inherit_lst
from .acl import acl
from .oauth import (oauth_retrieve, providers, oauth_profile_populate,
                    oauth_from_session)
from .mail import RecoverEmail, ActivationEmail
from lever import get_joined, LeverSyntaxError

import re
import werkzeug
import hashlib
import sqlalchemy
import os
import six


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
        return (self.pledges.count() /
                self.pledges.filter(disputed=True).count())


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
                             'desc',
                             {'obj': 'maintainer'},
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

        # flush after finishing creation
        db.session.flush()
        # send a notification to all subscribers
        events.NewProjNotif.generate(project)

        return project

    @classmethod
    def check_taken(cls, value, user=current_user):
        """ Called by the registration form to check if the email address is
        taken """
        try:
            Project.query.filter_by(url_key=value, maintainer=user.get()).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return {'taken': False}
        else:
            return {'taken': True}

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
        Thing, SubscribableMixin, VotableMixin, ReportableMixin):
    id = db.Column(db.Integer, db.ForeignKey('thing.id'), primary_key=True)
    status = db.Column(db.Enum('Completed', 'Discussion', 'Selected', 'Other',
                               name="issue_status"), default='Discussion')
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
                             {'obj': 'creator', 'join_prof': 'disp_join'}]
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

        # flush after finishing creation
        db.session.flush()
        # send a notification to all subscribers
        events.IssueNotif.generate(issue)

        return issue


class Solution(
        Thing, SubscribableMixin, VotableMixin, ReportableMixin):
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
    comments = db.relationship(
        'Comment',
        order_by='Comment.created_at',
        primaryjoin='Comment.thing_id == Thing.id and Comment.banned == False and Comment.hidden == False')
    __mapper_args__ = {'polymorphic_identity': 'Solution'}

    acl = acl['solution']
    standard_join = ['get_abs_url',
                     'title',
                     'report_status',
                     'subscribed',
                     'user_acl',
                     'created_at',
                     '-public_events',
                     'id',
                     'vote_status',
                     {'obj': 'creator', 'join_prof': 'disp_join'},
                     {'obj': 'comments', 'join_prof': 'standard_join'}
                     ]
    page_join = inherit_lst(standard_join,
                            [{'obj': 'issue', 'join_prof': 'page_join'},
                             'vote_status'
                             ]
                            )

    # used for displaying the project in noifications, etc
    disp_join = ['__dont_mongo',
                 'title',
                 'get_abs_url']

    def roles(self, user=current_user):
        roles = Solution.p_roles(issue=self.issue)
        if self.creator == user:
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
                  project=issue.project,
                  creator=user.get())
        sol.create_key()
        db.session.add(sol)

        # flush after finishing creation
        db.session.flush()
        # send a notification to all subscribers
        events.NewSolNotif.generate(sol)

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

    @property
    def get_dur_url(self):
        return "{parent_url}/{id}".format(id=self.id, parent_url=self.thing.get_dur_url)

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

        # send a notification to all subscribers
        events.NewCommentNotif.generate(comment)

        return comment


class Email(base):
    standard_join = ['address', 'activated', 'primary']

    acl = acl['email']

    user = db.relationship('User', backref=db.backref('emails'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    address = db.Column(db.String, primary_key=True)
    activated = db.Column(db.Boolean, default=False, nullable=False)
    primary = db.Column(db.Boolean, nullable=False)
    activate_hash = db.Column(db.String)
    activate_gen = db.Column(db.DateTime)

    @classmethod
    def activate_email(self, email, activate_hash="", force=False):
        current_app.logger.debug(
            "Activating user with params; email: {}; activate_hash: '{}'"
            .format(email, activate_hash))
        if force:
            return bool(Email.query
                        .filter_by(address=email)
                        .update({'activated': True}))
        else:
            day_ago = datetime.utcnow() - timedelta(days=1)
            vals = (Email.query
                    .filter_by(address=email, activate_hash=activate_hash)
                    .filter(Email.activate_gen > day_ago)
                    .update({'activated': True, 'activate_gen': None, 'activate_hash': None}))
            return bool(vals)

    @classmethod
    def check_taken(cls, value):
        """ Called by the registration form to check if the email address is
        taken """
        try:
            Email.query.filter_by(address=value).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return {'taken': False}
        else:
            return {'taken': True}

    @classmethod
    def create(cls, address, primary=True, activated=False, user=current_user):
        inst = cls(address=address,
                   user=user,
                   primary=primary,
                   activated=activated)

        db.session.add(inst)
        return inst

    def send_activation(self, force_send=None):
        """ Regenerates activation hashes and time markers and commits the
        change.  If the commit action is successful, an email will be sent to
        the user """
        self.activate_hash = hashlib.sha256(os.urandom(10)).hexdigest()
        self.activate_gen = datetime.utcnow()

        # complicated block that allows force send to either force to send or
        # force to not send. None defers to send_emails config value
        return ActivationEmail(self).send(self.address)


class User(Thing, SubscribableMixin, ReportableMixin):
    id = db.Column(db.Integer, db.ForeignKey('thing.id'), primary_key=True)
    username = db.Column(db.String(32), unique=True)
    admin = db.Column(db.Boolean, default=False)

    # User information
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    _password = db.Column(db.String)
    gh_token = db.Column(db.String, unique=True)
    tw_token = db.Column(db.String, unique=True)
    go_token = db.Column(db.String, unique=True)

    # recovery
    recover_hash = db.Column(db.String)
    recover_gen = db.Column(db.DateTime)

    # Event information
    public_events = db.Column(EventJSON, default=list)
    events = db.Column(EventJSON, default=list)
    profile = db.Column(JSONEncodedDict, default=dict)
    __mapper_args__ = {'polymorphic_identity': 'User'}

    # financial placeholders

    # total unpaid
    current_balance = db.Column(db.Integer, default=0)
    # total available for pledges
    available_balance = db.Column(db.Integer, default=0)

    standard_join = ['id',
                     'gh_linked',
                     'id',
                     'created_at',
                     'user_acl',
                     'get_abs_url',
                     'roles',
                     'profile',
                     'avatar',
                     '-_password',
                     '-go_token',
                     '-gh_token',
                     '-tw_token',
                     '-public_events',
                     '-events',
                     ]
    home_join = inherit_lst(standard_join,
                            [{'obj': 'events'},
                             {'obj': 'projects', 'join_prof': 'disp_join'}])

    page_join = inherit_lst(standard_join,
                            [{'obj': 'public_events'},
                             {'obj': 'projects', 'join_prof': 'disp_join'},
                              'gh_linked',
                              'go_linked',
                              'tw_linked',
                              'subscribed'])

    settings_join = inherit_lst(standard_join,
                                [{'obj': 'primary_email'},
                                 'gh_linked',
                                 'go_linked',
                                 'tw_linked',
                                 {'obj': 'emails'}])

    # used for displaying the project in noifications, etc
    disp_join = ['__dont_mongo',
                 'username',
                 'get_abs_url',
                 'avatar']

    acl = acl['user']


    # Financial functions
    # =========================================================================
    @property
    def available_marks(self):
        """ returns the available funds from marks """
        return sum([m.remaining for m in Leaf.query.filter_by(
            user_id=self.id, cleared=True)])

    # Password wrapping as encrypted value
    # =========================================================================
    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, val):
        self._password = six.u(crypt.encode(val))

    def check_password(self, password):
        return crypt.check(self._password, password)

    # Utility methods
    # =========================================================================
    @property
    def gh_linked(self): return bool(self.gh_token)

    @property
    def tw_linked(self): return bool(self.tw_token)

    @property
    def go_linked(self): return bool(self.go_token)

    @go_linked.setter
    def go_linked(self, val):
        if val is False:
            self.go_token = None
        else:
            raise AttributeError

    @tw_linked.setter
    def tw_linked(self, val):
        if val is False:
            self.tw_token = None
        else:
            raise AttributeError

    @gh_linked.setter
    def gh_linked(self, val):
        if val is False:
            self.gh_token = None
        else:
            raise AttributeError

    @property
    def get_dur_url(self):
        return "/u/{id}".format(id=self.id)

    def get_abs_url(self):
        return "/{username}".format(
            username=six.u(self.username).encode('utf-8'))

    @property
    def avatar(self):
        # Set your variables here
        default = urljoin(current_app.config['base_url'],
                          current_app.config['static_path'], "img/logo_sm.jpg")
        # construct the url
        gravatar_url = "http://www.gravatar.com/avatar/"
        gravatar_url += hashlib.md5(
            self.primary_email.address.lower().encode('utf8')).hexdigest()
        gravatar_url += "?" + urlencode({'d': default})
        return gravatar_url

    @property
    def linked_accounts(self):
        accts = []
        for key in providers.keys():
            if getattr(self, key + '_token') is not None:
                accts.append(key)
        return accts

    @property
    def primary_email(self):
        for email in self.emails:
            if email.primary:
                return email

    # Github Synchronization Logic
    # ========================================================================
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

    def gh_repos_syncable(self):
        """ Generate a list only of repositories that can be synced """
        for repo in self.gh_repos():
            if repo['permissions']['admin']:
                yield repo

    def gh_repo(self, path):
        """ Get a single repositories information from the gh_path """
        return github.get('repos/{0}'.format(path)).data

    # Action methods
    # ========================================================================
    @classmethod
    def login(cls, identifier=None, password=None):
        # by having kwargs we can run this function from angular with no params
        # and prevent a 400 error... kinda hacky
        if identifier is None or password is None:
            return {'message': 'Invalid credentials',
                    'success': False}

        if '@' in identifier:
            user = User.query.filter(
                User.emails.any(Email.address == identifier)).first()
        else:
            user = User.query.filter_by(username=identifier.lower()).first()

        if user and user.check_password(password):
            login_user(user)
            return {'objects': [get_joined(user)]}
        return False

    @classmethod
    def check_taken(cls, value):
        """ Called by the registration form to check if the username is taken
        """
        try:
            User.query.filter_by(username=value.lower()).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return {'taken': False}
        else:
            return {'taken': True}

    def recover(self, hash, password):
        day_ago = datetime.utcnow() - timedelta(days=1)
        if hash.strip() != self.recover_hash:
            current_app.logger.debug("Wrong recover hash: {} vs {}"
                                     .format(hash, self.recover_hash))
            return {'success': False,
                    'message':
                    ('Invalid recovery hash, maybe you copy and pasted the '
                     'link wrong?')}
        elif self.recover_gen < day_ago:
            return {'success': False,
                    'message':
                    ('Recovery hash has expired (it\'s too old). Please '
                     'resend a fresh one from the Account recovery page.')}

        self.password = password
        self.recover_gen = None
        self.recover_hash = None
        login_user(self)

        return {'objects': [get_joined(self)]}

    @classmethod
    def send_recover(cls, identifier, force_send=None):

        user = User.query.filter(
            sqlalchemy.or_(User.emails.any(Email.address==identifier),
                           User.username==identifier)).first()
        if not user:
            return {'success': False,
                    'message': 'Unable to find an account that matched that information'}

        # set their secure recovery hash
        user.recover_hash = hashlib.sha256(os.urandom(10)).hexdigest()
        user.recover_gen = datetime.utcnow()

        db.session.commit()

        # if they're recovering via an email address, send it to the requested
        # address
        if '@' in identifier:
            recipient = identifier
        else:
            recipient = user.primary_email.address

        # send dat email
        RecoverEmail(user).send(recipient, force_send=force_send)

        return {'email': recipient}

    # User creation logic
    # ========================================================================
    @classmethod
    def create(cls, username, password, email_address, user=None, force_send=None):
        user = cls(username=username.lower())
        user.password = password
        db.session.add(user)

        # create their email and send them an activation email
        email = Email.create(address=email_address, user=user, primary=True)
        if not email.send_activation(force_send=force_send):
            return False
        db.session.add(email)

        db.session.flush()
        login_user(user)
        return user

    @classmethod
    def oauth_create(cls, username, primary, password=None, cust_email=None, force_send=None):
        current_app.logger.debug(
            dict(username=username, password=password, primary=primary, cust_email=cust_email))

        user = cls(username=username)
        if password is not None:
            user.password = password
        db.session.add(user)

        prim_set = False  # a flag for if primary has been found

        # verify that these actions are kosher
        oauth_data = oauth_from_session('signup')
        user_data = oauth_retrieve(oauth_data['provider'],
                                   oauth_data['raw_token'],
                                   email_only=True)

        # set their token
        setattr(user,
                oauth_data['provider'] + '_token',
                oauth_data['raw_token'])

        oauth_profile_populate(oauth_data['provider'], user=user)

        # grab all their emails from oauth to enter into database
        for mail in user_data['emails']:
            email = Email.create(mail['email'],
                                 user=user,
                                 primary=False,
                                 activated=True)
            if primary == mail['email']:
                email.primary = True
                prim_set = True

        # enter a custom email if they provided one
        if cust_email is not None:
            prim = False
            if primary == cust_email:
                prim_set = True
                prim = True
            email = Email.create(cust_email, primary=prim, user=user)
            if primary == cust_email:
                email.primary = True
                prim_set = True
            # send the activation email to the user
            if not email.send_activation(force_send=force_send):
                return False

        if prim_set is False:
            raise LeverSyntaxError(
                "Primary email was not any one of provided emails")

        db.session.flush()

        login_user(user)

        return {'objects': [get_joined(user)]}

    def refresh_provider(self, provider):
        oauth_profile_populate(provider)
        db.session.commit()
        return {'profile_data': self.profile}

    # Authentication
    # ========================================================================
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return six.u(str(self.id))

    def roles(self, user=current_user):
        if self.id == getattr(user, 'id', None):
            return ['owner']
        return []

    def global_roles(self):
        """ Determines global roles for the user. """
        if self.admin:
            return ['admin']
        if self.username is None:
            return ['usernameless']
        if not self.primary_email.activated:
            return ['noactive_user']
        return ['user']

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
