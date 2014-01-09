from flask import Blueprint, request, current_app, jsonify
from flask.ext.login import (login_required, logout_user, current_user,
                             login_user)
from flask.ext.oauthlib.client import OAuthException

from .api_base import API, get_joined, jsonify_status_code, APISyntaxError
from .oauth import oauth_retrieve, oauth_from_session
from .models import User, Project, Issue, Solution, Email, Comment, Thing
from .fin_models import Earmark, Recipient, Transfer, Charge, Dispute

from . import oauth

import sqlalchemy
import decorator
import stripe


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
    meth = request.method
    # Some custom exceptions have error notices that can be displayed, thus the
    # error_key is sent back to the frontend so they know where to send the
    # user
    if hasattr(e, 'error_key'):
        kwargs = dict(error_key=e.error_key, success=False)
    else:
        kwargs = dict(success=False)

    # Common API errors
    if e is KeyError or e is AttributeError:
        ret = 400, 'Incorrect syntax or missing key ' + str(exc.message)
    elif e is AssertionError:
        ret = 403, "You don't have permission to do that"
        msg = INFO
    elif e is APISyntaxError:
        ret = 400, exc.message
        msg = INFO
    elif e is TypeError:
        if meth == 'POST':
            if 'at least' in exc.message:
                ret = 400, "Required arguments missing from API create method"
            elif 'argument' in exc.message and 'given' in exc.message:
                ret = 400, "Extra arguments supplied to the API create method"
            elif 'unexpected' in exc.message:
                ret = 400, "Invalid keyword argument provided"
            else:
                ret = 500, "Unkown internal server error"
                msg = ERROR
        else:
            ret = 500, "Unkown internal server error"
            msg = ERROR

    # Stripe handling
    elif e is stripe.InvalidRequestError:
        ret = 402, 'Invalid request was sent to Stripe'
        msg = ERROR
    elif e is stripe.AuthenticationError:
        ret = 402, 'Our Stripe credentials seem to have expired... Darn.'
        msg = ERROR
    elif e is stripe.APIConnectionError:
        ret = 402, 'Unable to connect to Stripe to process request'
        msg = WARN
    elif e is stripe.StripeError:
        ret = 402, 'Unknown stripe error'
        msg = ERROR

    # SQLAlchemy exceptions
    elif e is sqlalchemy.orm.exc.NoResultFound:
        ret = 404, 'Could not be found'
    elif e is sqlalchemy.orm.exc.MultipleResultsFound:
        ret = 400, 'Only one result requested, but MultipleResultsFound'
    elif e is sqlalchemy.exc.IntegrityError:
        ret = 409, "A duplicate value already exists in the database"
    elif e is sqlalchemy.exc.InvalidRequestError:
        ret = 400, "Client programming error, invalid search sytax used."
    elif e is sqlalchemy.exc.DataError:
        ret = 400, "ORM returned invalid data for an argument"
    elif issubclass(e, sqlalchemy.exc.SQLAlchemyError):
        ret = 402, "An unknown database operations error has occurred"
        msg = WARN, 'Uncaught type of database exception'

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


class UserAPI(API):
    model = User


class EmailAPI(API):
    model = Email


class ProjectAPI(API):
    model = Project


class IssueAPI(API):
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


class SolutionAPI(API):
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


class TransferAPI(API):
    model = Transfer


class RecipientAPI(API):
    model = Recipient


class ChargeAPI(API):
    model = Charge


class EarmarkAPI(API):
    model = Earmark


class DisputeAPI(API):
    model = Dispute


class CommentAPI(API):
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


# activate all the APIs on the blueprint
TransferAPI.register(api, '/transfer')
RecipientAPI.register(api, '/recipient')
DisputeAPI.register(api, '/dispute')
ChargeAPI.register(api, '/charge')
EarmarkAPI.register(api, '/earmark')

SolutionAPI.register(api, '/solution')
IssueAPI.register(api, '/issue')
ProjectAPI.register(api, '/project')
CommentAPI.register(api, '/comment')

EmailAPI.register(api, '/email')
UserAPI.register(api, '/user')
