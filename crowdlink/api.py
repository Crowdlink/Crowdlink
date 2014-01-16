from flask import Blueprint, current_app, jsonify
from flask.ext.login import login_required, logout_user, current_user
from flask.ext.oauthlib.client import OAuthException

from pprint import pformat
from lever import API, LeverException
from .oauth import oauth_retrieve, oauth_from_session
from .models import EmailList

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
        msg = e.message
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
        current_app.logger.error("Error handler for type {} failed to return "
                                 "proper information".format(e.__name__))

    if hasattr(e, 'error_key'):
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




class APIBase(API):
    session = db.session
    current_user = current_user


class EmailAPI(APIBase):
    model = EmailList

EmailAPI.register(api, '/email_list')
