from flask import Blueprint, request, redirect, render_template, url_for, send_file, g, current_app, send_from_directory, abort, flash
from flask.ext.login import login_user, logout_user, current_user, login_required

from . import root, lm, app, oauth, github
from .models import User, Project, Issue, Transaction
from .lib import jsonify
from .forms import *

import json
import mongoengine
import os
import sys
import base64


main = Blueprint('main', __name__, template_folder='../templates')


# Make user availible easily in the global var
@app.before_request
def before_request():
    g.user = current_user


# tell the session manager how to access the user object
@lm.user_loader
def user_loader(id):
    try:
        return User.objects.get(id=id)
    except User.DoesNotExist:
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
    return (g.user.gh_token, '')

@github.tokengetter
def get_github_oauth_token():
    return (g.user.gh_token, '')

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

    if g.user:
        g.user.gh_token = resp['access_token']
        g.user.gh_synced = True
        g.user.safe_save()
        # Populate the github cache
        g.user.gh
        return redirect(url_for('main.account'))
    else:
        # they're trying to login, or create an account
        user = User.create_user_github(resp['access_token'])


@main.route("/<username>/<url_key>/settings/", methods=['GET', 'POST'])
def project_settings(username=None, url_key=None):
    # get view objects and confirm permissions
    try:
        usr = User.objects.get(username=username)
        project = Project.objects.get(maintainer=usr.id,
                                  url_key=url_key)
    except Project.DoesNotExist:
        abort(404)
    if not project.can_edit_settings(g.user):
        abort(403)

    sync = project.can_sync(g.user) and not project.gh_synced and g.user.gh_linked
    if sync:
        sync_form = SyncForm.get_form()
    else:
        sync_form = None

    if request.method == 'POST':
        # They've submitted the synchronization form and everything checks out
        if request.form.get('_arg_form', None) == 'sync' and \
           sync and \
           sync_form.validate(request.form):
            repo = g.user.gh_repo(sync_form.repo.data)
            try:
                project.gh_sync(repo)
            except KeyError:
                sync_form.add_msg(
                    message="Project could not be found under your user",
                    type="error")
            else:
                if project.safe_save(flash=True):
                    flash('Your project is linked', category="success")

    if sync_form:
        sync_form_out = sync_form.render()
    else:
        sync_form_out = None

    return render_template('psettings.html',
                           project=project,
                           sync_form=sync_form_out)


@main.route("/new_project", methods=['GET', 'POST'])
@login_required
def new_project():
    form = NewProjectForm()
    form.g_context.update({'user': g.user})
    if request.method == 'POST':
        if form.validate(request.form):
            data = form.data_by_attr()
            try:
                proj = Project(
                    maintainer=g.user.id,
                    username=g.user.username,
                    name=data['ptitle'],
                    website=data['website'],
                    source_url=data['source'],
                    url_key=data['url_key'],
                    description=data['description'])
                proj.save()
            except Exception:
                catch_error_graceful(form)
            else:
                form.set_json_success(redirect=proj.get_abs_url())

        return form.render_json()

    return render_template('new_project.html', form=form.render())


@main.route("/<username>/<purl_key>/new_issue", methods=['GET', 'POST'])
@login_required
def new_issue(username=None, purl_key=None):
    # XXX Add check on the purl_key
    form = NewImprovementForm()
    if request.method == 'POST':
        if form.validate(request.form):
            data = form.data_by_attr()
            try:
                project = Project.objects.get(maintainer=username, url_key=purl_key)
                imp = Issue(
                    creator=g.user.id,
                    brief=data['brief'],
                    description=data['description'])
                project.add_issue(imp, g.user)
            except Exception:
                catch_error_graceful(form)
            else:
                form.set_json_success(redirect=imp.get_abs_url())

        return form.render_json()

    return render_template('new_issue.html', form=form.render())


@main.route("/logout")
@login_required
def logout():
    logout_user()
    return jsonify(access_denied=True)


@main.route("/signup", methods=['GET', 'POST'])
def signup():
    form = RegisterForm()

    if request.method == 'POST':
        success = form.validate(request.form)
        data = form.data_by_attr()
        if success:
            try:
                user = User.create_user(data['username'], data['password'], data['email'])
            except Exception:
                catch_error_graceful(form)

            if user:
                login_user(user)
                return redirect_angular(url_for('main.home'))
            else:
                form.start.add_msg(
                    message='Unknown database error, please retry.', error=True)

    return render_template('sign_up.html', form=form.render())


@main.route("/", methods=['GET', 'POST'])
def angular_root():
    logged_in = "true" if g.user.is_authenticated() else "false"
    userid = g.user.id if g.user.is_authenticated() else "undefined"
    return render_template('base.html',
                           logged_in=logged_in,
                           userid=userid)


@main.route("/home", methods=['GET', 'POST'])
def home():
    if g.user is not None and g.user.is_authenticated():
        projects = g.user.get_projects()
        return render_template('user_home.html', projects=projects)
    else:
        form = RegisterForm.get_sm()
        return render_template('home.html', form=form.render())


from featurelet.lib import catch_error_graceful
