from flask import Blueprint, request, redirect, render_template, url_for, send_file, g, current_app, send_from_directory, abort, flash
from flask.ext.login import login_user, logout_user, current_user, login_required

from . import root, lm, oauth, github
from .models import User, Project, Issue, Transaction
from .lib import jsonify

import json
import sqlalchemy
import os
import sys
import base64


main = Blueprint('main', __name__, template_folder='../templates')


# tell the session manager how to access the user object
@lm.user_loader
def user_loader(id):
    try:
        return User.query.filter_by(id=id).one()
    except sqlalchemy.orm.exc.NoResultFound:
        return None


@main.errorhandler(403)
def access_denied(e):
    return render_template('403.html')


@main.route("/favicon.ico")
def favicon():
    return send_file(os.path.join(root, 'static/favicon.ico'))


@main.route("/login/github/deauthorize/")
def unlink_github():
    """ Not working atm """
    current_app.logger.warn(
        github.get('authorizations',
                   headers={"Authorization": "Basic %s" %\
                            current_app.config['GITHUB_ACCOUNT_KEY']}).data)
    return (current_user.gh_token, '')


@github.tokengetter
def get_github_oauth_token():
    return (current_user.gh_token, '')


@main.route("/login/github/")
def github_init_auth():
    """ Redirects to github to obtain auth token """
    return github.authorize(callback=url_for('main.github_auth', _external=True))


@main.route("/login/github/authorize/")
@github.authorized_handler
def github_auth(resp):
    """ The github authorization callback """
    if resp is None:
        return 'Access denied: reason=%s error=%s' % (
            request.args['error_reason'],
            request.args['error_description']
        )
    # if the auth failed
    if 'access_token' not in resp:
        current_app.logger.info("Return response from Github didn't contain an access token")
        return redirect(url_for('main.account'))

    if current_user:
        current_user.gh_token = resp['access_token']
        current_user.gh_synced = True
        current_user.safe_save()
        # Populate the github cache
        current_user.gh
        return redirect(url_for('main.account'))
    else:
        # they're trying to login, or create an account
        user = User.create_user_github(resp['access_token'])


@main.route("/", methods=['GET', 'POST'])
def angular_root():
    logged_in = "true" if current_user.is_authenticated() else "false"
    userid = current_user.id if current_user.is_authenticated() else "undefined"
    return render_template('base.html',
                           logged_in=logged_in,
                           userid=userid)


@main.route("/home", methods=['GET', 'POST'])
def home():
    if current_user is not None and current_user.is_authenticated():
        projects = current_user.get_projects()
        return render_template('user_home.html', projects=projects)
    else:
        form = RegisterForm.get_sm()
        return render_template('home.html', form=form.render())
