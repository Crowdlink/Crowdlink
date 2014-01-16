from flask import Blueprint, current_app, jsonify
from flask.ext.login import login_required, logout_user, current_user
from flask.ext.oauthlib.client import OAuthException

from pprint import pformat
from lever import API, LeverException
from .oauth import oauth_retrieve, oauth_from_session
from .models import User, Project, Issue, Solution, Email, Comment, Thing, EmailList

from . import oauth, db

import sqlalchemy


api = Blueprint('api_bp', __name__)


@api.errorhandler(Exception)
def api_error_handler(exc):
    # set some defaults
    log = 'debug'
    msg = "Exception occured in error handling"
    code = 500
    extra = {}
    end_user = {}

    try:
        raise exc
    except LeverException as e:
        code = e.code
        msg = str(e)
        end_user = e.end_user
        extra = e.extra

    # OAuth Exceptions
    except oauth.OAuthAlreadyLinked:
        msg = 'That account is already linked by you'
        code = 400
    except oauth.OAuthLinkedOther:
        msg = 'That account is already linked by another user'
        code = 400
    except oauth.OAuthEmailPresent:
        msg = 'That email already exists in our system'
        code = 400
    except oauth.OAuthCommError:
        msg = 'Error communicating with the OAuth provider'
        code = 400
    except oauth.OAuthDenied:
        msg = 'OAuth session information expired or you denied the OAuth request'
        code = 400
    except OAuthException:
        msg = 'Unkown OAuth error occured'
        code = 400
        log = 'warn'
    except Exception:
        current_app.logger.error(
            "Unhadled API error of type {0} raised".format(e.__name__))

    if hasattr(exc, 'error_key'):
        end_user['error_key'] = e.error_key
    end_user['success'] = False

    # ensure the message of the exception gets passed on
    end_user['message'] = msg
    response = jsonify(**end_user)
    response.status_code = code

    # logging

    # log the message using flasks logger. In the future this will use
    # logstash and other methods
    message = ('Extra: {}\nEnd User: {}'
               .format(pformat(extra), pformat(end_user)))
    getattr(current_app.logger, log)(message, exc_info=True)

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
    current_user = current_user


class UserAPI(APIBase):
    model = User


class EmailAPI(APIBase):
    model = EmailList


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

EmailAPI.register(api, '/email_list')
UserAPI.register(api, '/user')
