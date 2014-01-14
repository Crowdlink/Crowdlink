from flask import (Blueprint, request, redirect, url_for, current_app,
                   abort, session)
from flask.ext.login import current_user, login_user
from flask.ext.oauthlib.client import OAuthException

from . import github, twitter, google, db
from .views import main

import copy
import sqlalchemy
import sys


class OAuthAlreadyLinked(OAuthException):
    error_key = 'oauth_already_linked'
class OAuthLinkedOther(OAuthException):
    error_key = 'oauth_linked_other'
class OAuthCommError(OAuthException):
    error_key = 'oauth_comm_error'
class OAuthEmailPresent(OAuthException):
    error_key = 'oauth_email_present'
class OAuthDenied(OAuthException):
    pass
class OAuthSessionExpired(OAuthException):
    error_key = 'oauth_error'


@github.tokengetter
def get_github_oauth_token():
    return (current_user.gh_token, '')


@google.tokengetter
def get_google_oauth_token():
    return (current_user.go_token, '')


@twitter.tokengetter
def get_twitter_oauth_token():
    try:
        return unicode(current_user.tw_token).split(':')
    except AttributeError:
        return None


@main.errorhandler(OAuthException)
def oauth_error_handler(e):
    """ If any of the oauth views throws an OAuth exception it will be
    redirect the user to a useful error message via this method. """
    current_app.logger.debug(e.message, exc_info=True)
    if isinstance(e, OAuthDenied):
        # notify the user
        send_message('Session has expired or you denied the OAuth request',
              'alert-danger')
        return redirect('/')
    elif type(e) is OAuthException:
        error = 'oauth_error'
    else:
        error = e.error_key
    return redirect('/errors/' + error)


oauth_actions = ['login', 'signup', 'link']
providers = {'gh': github, 'tw': twitter, 'go': google}


def check_action_provider(action, provider):
    """ Provides simple checks to validate whether the users desired OAuth
    action makes sense and is possible """
    provider_obj = providers.get(provider)
    # try a not available action
    if action not in oauth_actions:
        abort(400)
    # try not available provider
    if provider_obj is None:
        abort(400)
    # not logged in
    if action == 'link' and current_user.is_anonymous():
        abort(403)
    # already linked
    if action == 'link' and provider in current_user.linked_accounts:
        raise OAuthAlreadyLinked("A user has already linked this account")
    # can't signup while logged in
    if action == 'signup' and not current_user.is_anonymous():
        abort(400)
    # already_logged
    if action == 'login' and not current_user.is_anonymous():
        abort(400)

    return (provider_obj, action)


@main.route("/gh/<action>")
@main.route("/tw/<action>")
@main.route("/go/<action>")
def init(provider=None, action=None):
    """ This redirects the user to the OAuth provider after checking that their
    actions are valid to the best of our knowledge. Defines a callback url that
    passes along users intended action and the oauth provider information. """
    # catch many common consistency errors
    provider_obj, action = check_action_provider(action, provider)

    # send them to the oauth provider with correct callback for desired action
    return provider_obj.authorize(callback=url_for('oauth.authorize',
                                                   action=action,
                                                   provider=provider,
                                                   _external=True))


@main.route("/callback/<provider>/<action>")
def authorize(provider=None, action=None):
    """ The primary oauth logic view. OAuth provider will return the user to
    this URL with either valid token information or empty token depending on
    their decision to authorize. This handles logic of what action they're
    trying to perform (link, signup, or login) and takes appropriate actions
    """
    # catch many common consistency errors
    provider_obj, action = check_action_provider(action, provider)

    # Logic that is applied by the flask oauthlib decorator, but adapted to
    # run with one of many providers for easy patterning of functionality.
    # Exception hooks have been removed and are handled by exceptionhandler
    if 'oauth_verifier' in request.args:
        data = provider_obj.handle_oauth1_response()
    elif 'code' in request.args:
        data = provider_obj.handle_oauth2_response()
    else:
        data = provider_obj.handle_unknown_response()

    # free request token
    session.pop('%s_oauthtok' % provider_obj.name, None)
    session.pop('%s_oauthredir' % provider_obj.name, None)
    # End pulled section from flask oauthlib
    # =========================================================================
    # if the auth failed
    raw_token = None
    try:
        if provider == 'tw':  # OAuth v1.0a
            raw_token = '{}:{}'.format(data['oauth_token'],
                                   data['oauth_token_secret'])
        else:
            raw_token = data['access_token']
    except (KeyError, TypeError):
        current_app.logger.warn(
            "Got access denied from auth type {} on provider {}.\nReason: {}"
            "\nDescription: {}"
            .format(action,
                    provider,
                    request.args.get('error_reason'),
                    request.args.get('error_description')))

    if raw_token is None:  # damn, nothing back
        raise OAuthDenied("No token present in return response")

    if not current_user.is_anonymous() and action == 'link':
        # they're trying to link their currently logged in account
        current_app.logger.debug("Linking a currently logged in account")
        setattr(current_user, provider + '_token', raw_token)
        # set their username/identities in their profile
        oauth_profile_populate(provider)

        # add all un-added emails to the database as verified
        from .models import Email
        data = oauth_retrieve(provider, raw_token, email_only=False)
        for mail in data['emails']:
            exists = Email.query.filter_by(address=mail['email']).first()
            if not exists:
                Email.create(mail['email'], primary=False, verified=True)
            else:
                current_app.logger.debug(
                    "An email address from the OAuth provider was already "
                    "entered into the database")

        try:
            db.session.commit()
        except sqlalchemy.exc.IntegrityError:
            # edge case is that someone registers with an emails address
            # that is being added in this transaction, very unlikely.
            raise OAuthLinkedOther(
                "Another user has already linked that account"), None, sys.exc_info()[2]

        return redirect('/account')
    elif action == 'link':  # can't link if not logged in
        abort(403)
    elif current_user.is_anonymous():  # ensure they're logged out
        # lookup a user who might have that token
        from .models import User
        query = {provider + '_token': raw_token}
        user = User.query.filter_by(**query).first()

        # if they're trying to signup and a user was found give error
        if user and action == 'signup':
            send_message("An account was already linked with that account, so "
                         "we logged you in.",
                         cls='alert-warning')

        if user:
            current_app.logger.debug("Logging in a user with a matching token")
            login_user(user)
            return redirect('/home')
        else:
            oauth_to_session(provider, raw_token)
            current_app.logger.debug(
                "Redirecting to OAuth signup page after setting session.")

            # if they're trying to login but no user was found, display a
            # notice
            if action == 'login':
                send_message(
                    "No account is linked with that OAuth provider, please "
                    "signup.", cls='alert-danger')
                return redirect('/login')

            return redirect('/oauth_signup')


def oauth_retrieve(provider, raw_token, email_only=False):
    """ A method that gets username and emails addresses from session stored
    OAuth information.  This basically is used to populate the frontend when a
    user signs up with OAuth, but is also used to retrieve un-tampered data
    when running the actual register action. """
    retval = {}
    current_app.logger.debug("OAuth data from session {}"
                             .format(session.get('oauth')))
    try:
        if provider == 'gh':
            # request new api that gives verification status
            headers = {'Accept': 'application/vnd.github.v3+json'}
            token = (raw_token, '')
            if not email_only:
                dat = github.get('user',
                                 token=token,
                                 headers=headers).data
                retval['username'] = dat['login']

            emails = github.get('user/emails',
                                token=token,
                                headers=headers).data
            retval['emails'] = [mail for mail in emails if mail['verified']]
            return retval
        if provider == 'go':
            dat = google.get('userinfo',
                             data={'fields': 'verified_email,email'},
                             token=(raw_token, '')).data
            # google only returns one email address from this request
            if dat['verified_email']:
                retval['emails'] = [{'email': dat['email'], 'verified': True}]
            else:
                retval['emails'] = []
            retval['username'] = dat['email'].split('@')[0]
            return retval
        if provider == 'tw':
            token = unicode(raw_token).split(':')
            dat = twitter.get('account/verify_credentials.json', token=token)
            return {'username': dat.data['screen_name'], 'emails': []}
    except KeyError:  # if one of the responses didn't have what we needed
        pass

    raise OAuthCommError(
        "Populating user information from the provider failed"), None, sys.exc_info()[2]


def oauth_profile_populate(provider, user=current_user):
    """ Initilaizes a users cached profile information from a specified OAuth
    provider. Called when an account is linked, created with OAuth, or the
    information is deemed stale. Allows us to show information on the linked
    accounts in the users profile. """
    profile = copy.copy(user.profile)
    if profile is None:
        profile = {}
    try:
        if provider == 'gh':
            token = (getattr(user, provider + '_token'), '')
            data = github.get('user', token=token).data
            profile['gh'] = {'username': data['login'],
                             'name': data['name'],
                             'profile_link': data['html_url'],
                             'id': data['id']}
        elif provider == 'tw':
            token = unicode(getattr(user, provider + '_token')).split(":")
            data = twitter.get('account/verify_credentials.json',
                               token=token).data
            profile['tw'] = {'username': data['screen_name'],
                             'name': data['name'],
                             'id': data['id']}
        elif provider == 'go':
            token = (getattr(user, provider + '_token'), '')
            data = google.get('userinfo',
                              data={'fields': 'link,name,id'},
                              token=token).data
            profile['go'] = {'name': data['name'],
                             'profile_link': data['link'],
                             'id': data['id']}
        user.profile = profile
    except KeyError:
        raise OAuthCommError(
            "Problem populating profile data from provider"), None, sys.exc_info()[2]

    return False


def oauth_from_session(action):
    """ Decodes token information from the session, runs the check action
    function to catch possible errors early, returns a dictionary of useful
    information """
    try:
        data = session['oauth']
        provider = data['provider']
        raw_token = data['token']
        provider_obj, action = check_action_provider(action, provider)
        if provider == 'tw':
            token = unicode(raw_token).split(":")
        else:
            token = (raw_token, '')
        return {'raw_token': raw_token,
                'token': token,
                'provider_obj': provider_obj,
                'provider': provider}
    except KeyError:
        raise OAuthSessionExpired(
            "Problem populating profile data from provider"), None, sys.exc_info()[2]


def oauth_to_session(provider, token):
    session['oauth'] = {'provider': provider, 'token': token}

from .views import send_message
