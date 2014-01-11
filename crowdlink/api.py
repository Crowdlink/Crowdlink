from flask import Blueprint, request, current_app, jsonify
from flask.ext.login import login_required, logout_user
from flask.ext.oauthlib.client import OAuthException

from lever import API, LeverException
from .oauth import oauth_retrieve, oauth_from_session
from .models import User, Project, Issue, Solution, Email, Comment, Thing

from . import oauth, db

import sqlalchemy


api = Blueprint('api_bp', __name__)


@api.errorhandler(Exception)
def api_error_handler(exc):
    """ This handles all exceptions that can be thrown by the API and takes
    care of logging them and reporting to the end user.

    Each branch must define ret to be a tuple
    (status_code, message back to the user).
    Msg can be defined as optional logging information that shouldn't be
    reported to the user. By default the message will be logged in debug
    mode if no msg is specified"""
    # debug constants
    ERROR = 0
    WARN = 1
    INFO = 2
    DEBUG = 3

    e = type(exc)
    msg = None
    ret = None
    # Some custom exceptions have error notices that can be displayed, thus the
    # error_key is sent back to the frontend so they know where to send the
    # user
    if hasattr(e, 'error_key'):
        kwargs = dict(error_key=e.error_key, success=False)
    else:
        kwargs = dict(success=False)

    if e is LeverException:
        ret = exc.code, exc.message
        kwargs.update(exc.end_user)
    # OAuth Exceptions
    elif e is oauth.OAuthAlreadyLinked:
        ret = 400, 'That account is already linked by you'
    elif e is oauth.OAuthLinkedOther:
        ret = 400, 'That account is already linked by another user'
    elif e is oauth.OAuthEmailPresent:
        ret = 400, 'That email already exists in our system'
    elif e is oauth.OAuthCommError:
        ret = 400, 'Error communicating with the OAuth provider'
    elif e is oauth.OAuthDenied:
        ret = 400, 'OAuth session information expired or you denied the OAuth request'
    elif issubclass(e, OAuthException):
        ret = 400, 'Unkown OAuth error occured'
        msg = WARN
    else:
        ret = 500, "Internal Server error"

    if ret is None:
        current_app.logger.error("Error handler for type {} failed to return "
                                 "proper information".format(e.__name__))
        ret = 500, "Exception occured in error handling"

    # quick hack to prevent duplicate arguments from lever
    kwargs.pop('message', None)
    response = jsonify(message=ret[1], **kwargs)
    response.status_code = ret[0]
    # if we should run special logging...
    if msg is not None:
        # allow the user to just change the log level by changing msg
        if isinstance(msg, int):
            msg = msg, ret[1]
        attr_map = {0: 'error', 1: 'warn', 2: 'info', 3: 'debug'}
        # log the message using flasks logger. In the future this will use
        # logstash and other methods
        getattr(current_app.logger, attr_map[msg[0]])(msg[1], exc_info=True)
    else:
        current_app.logger.debug(str(ret), exc_info=True)
    return response


@api.route("/logout")
@login_required
def logout():
    logout_user()
    return jsonify(access_denied=True)


@api.route("/oauth", methods=['GET'])
def oauth_user_data():
    """ Thin wrapper around the oauth retrieve function for the signup page to
    use. """
    data = oauth_from_session('signup')
    data = oauth_retrieve(data['provider'], data['raw_token'])
    if data is not False:

        # check for presently taken email addresses
        if len(data['emails']) > 0:
            from .models import Email
            args = []
            for email in data['emails']:
                args.append(Email.address == email['email'])
            matches = Email.query.filter(sqlalchemy.or_(*args))
            if matches.count() > 0:
                return jsonify(success=False, error='oauth_email_present')

        return jsonify(success=True, data=data)
    return jsonify(success=False, error='oauth_missing_token')


class APIBase(API):
    session = db.session


class UserAPI(APIBase):
    model = User


class EmailAPI(APIBase):
    model = Email


class ProjectAPI(APIBase):
    model = Project


class IssueAPI(APIBase):
    model = Issue
    def create_hook(self):
        # do logic to pick out the parent from the database based on parent
        # keys
        purl_key = self.params.pop('project_url_key', None)
        puser = self.params.pop('project_maintainer_username', None)
        pid = self.params.pop('project_id', None)
        # try this method first, most common
        if puser and purl_key:
            project = Project.query.filter(
                Project.maintainer_username == puser,
                Project.url_key == purl_key).one()
        elif pid:
            project = Project.query.filter(Project.id == pid).one()
        else:
            raise APISyntaxError(
                    "Unable to identify parent project from information given")

        self.params['project'] = project

    def can_cls(self, action):
        return self.model.can_cls(action, project=self.params['project'])


class SolutionAPI(APIBase):
    model = Solution
    def create_hook(self):
        # do logic to pick out the parent from the database based on parent
        # keys
        purl_key = self.params.pop('project_url_key', None)
        puser = self.params.pop('project_maintainer_username', None)
        iurl_key = self.params.pop('issue_url_key', None)
        iid = self.params.pop('issue_id', None)
        # try this method first, most common
        if puser and purl_key and iurl_key:
            issue = Issue.query.filter(
                Issue.project_maintainer_username == puser,
                Issue.project_url_key == purl_key,
                Issue.url_key == iurl_key).one()
        elif iid:
            issue = Issue.query.filter(Issue.id == iid).one()
        else:
            raise APISyntaxError(
                    "Unable to identify parent Issue from information given")

        self.params['issue'] = issue

    def can_cls(self, action):
        return self.model.can_cls(action, issue=self.params['issue'])


class CommentAPI(APIBase):
    model = Comment
    def create_hook(self):
        # do logic to pick out the parent from the database based on parent
        # keys
        tid = self.params.pop('thing_id', None)
        # try this method first, most common
        if tid:
            thing = Thing.query.filter(Thing.id == tid).one()
        else:
            raise APISyntaxError(
                    "Unable to identify parent Thing from information given")

        self.params['thing'] = thing

    def can_cls(self, action):
        return self.model.can_cls(action, thing=self.params['thing'])


SolutionAPI.register(api, '/solution')
IssueAPI.register(api, '/issue')
ProjectAPI.register(api, '/project')
CommentAPI.register(api, '/comment')

EmailAPI.register(api, '/email')
UserAPI.register(api, '/user')
