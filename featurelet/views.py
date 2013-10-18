from flask import Blueprint, request, redirect, render_template, url_for, send_file, g, current_app, send_from_directory
from flask.ext.login import login_user, logout_user, current_user, login_required

from featurelet import root, lm, app, oauth, github
from featurelet.models import User, Project, Improvement
from featurelet.forms import RegisterForm, LoginForm, NewProjectForm, NewImprovementForm, PasswordForm, CommentForm

import json
import mongoengine
import os
import sys
import base64


main = Blueprint('main', __name__, template_folder='../templates')

@app.before_request
def before_request():
    g.user = current_user

@lm.user_loader
def user_loader(id):
    try:
        return User.objects.get(username=id)
    except User.DoesNotExist:
        pass


@main.route("/favicon.ico")
def favicon():
    return send_file(os.path.join(root, 'static/favicon.ico'))


@main.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    password_form = PasswordForm()
    if request.method == 'POST':
        # Handle new password logic
        if request.form.get('_arg_form', None) == 'password':
            if password_form.validate(request.form):
                data = password_form.data_by_attr()
                try:
                    g.user.password = data['password']
                    g.user.save()
                    password_form.start.add_error(
                        {'message': 'Password successfully updated',
                         'type': 'success' })
                except Exception:
                    catch_error_graceful(password_form)

    return render_template('account.html',
                           password_form=password_form.render())

@main.route("/login/github/deauthorize")
def unlink_github():
    current_app.logger.warn(
        github.get('authorizations', headers={"Authorization": "Basic %s" % current_app.config['GITHUB_ACCOUNT_KEY']}).data)
    return (g.user.github_token, '')

@github.tokengetter
def get_github_oauth_token():
    return (g.user.github_token, '')

@main.route("/login/github")
def github_init_auth():
    return github.authorize(callback=url_for('main.github_auth', _external=True))

@main.route("/login/github/authorize")
@github.authorized_handler
def github_auth(resp):
    if resp is None:
        return 'Access denied: reason=%s error=%s' % (
            request.args['error_reason'],
            request.args['error_description']
        )
    # if they're logged in
    if 'access_token' not in resp:
        return redirect(url_for('main.account'))
    if g.user:
        g.user.github_token = resp['access_token']
        g.user.save()
        g.github
        return redirect(url_for('main.account'))
    else:
        # they're trying to login, or create an account
        pass


@main.route("/<username>/<url_key>")
def view_project(username=None, url_key=None):
    project = Project.objects.get(maintainer=User(username=username),
                                  url_key=url_key)
    return render_template('proj.html', project=project)


@main.route("/<user>/<purl_key>/<url_key>", methods=['GET', 'POST'])
def view_improvement(user=None, purl_key=None, url_key=None):
    proj = Project.objects.get(url_key=purl_key, maintainer=user)
    imp = Improvement.objects.get(url_key=url_key,
                                  project=proj)
    form = CommentForm()
    if request.method == 'POST':
        if form.validate(request.form):
            # Going to submit a comment
            data = form.data_by_attr()
            try:
                imp.add_comment(g.user, data['body'])
            except Exception:
                catch_error_graceful(form)
            else:
                form.start.add_error({"message": "Comment successfully posted",
                                    "type": "success"})

    print g.user.to_json()
    return render_template('improvement.html',
                           imp=imp,
                           can_edit=imp.can_edit_imp(g.user),
                           comment_form=form.render())


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


@main.route("/<maintainer>/<purl_key>/new_improvement", methods=['GET', 'POST'])
@login_required
def new_improvement(maintainer=None, purl_key=None):
    # XXX Add check on the purl_key
    form = NewImprovementForm()
    if request.method == 'POST':
        if form.validate(request.form):
            data = form.data_by_attr()
            try:
                project = Project.objects.get(maintainer=maintainer, url_key=purl_key)
                imp = Improvement(
                    creator=g.user.id,
                    project=project,
                    brief=data['brief'],
                    description=data['description'])
                imp.set_url_key()
                imp.save()
            except Exception:
                catch_error_graceful(form)
            else:
                form.set_json_success(redirect=imp.get_abs_url())

        return form.render_json()

    return render_template('new_improvement.html', form=form.render())


@main.route("/u/<username>")
def user(username=None):
    user = User.objects.get(username=username)
    return render_template('prof.html', user=user)


@main.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.home'))

@main.route("/login", methods=['GET', 'POST'])
def login():
    if g.user is not None and g.user.is_authenticated():
        return redirect(url_for('main.home'))
    form = LoginForm()
    if request.method == 'POST':
        success = form.validate(request.form)
        data = form.data_by_attr()
        if success:
            try:
                user = User.objects.get(username=data['username'])
            except User.DoesNotExist:
                pass
            except Exception:
                catch_error_graceful(form)
            else:
                if user and user.check_password(data['password']):
                    login_user(user)
                    return redirect(url_for('main.home'))
                else:
                    form.start.add_error({"message": "Invalid credentials"})
    return render_template('login.html', form=form.render())


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
                return redirect(url_for('main.home'))
            else:
                form.start.add_error({'message': 'Unknown database error, please retry.', 'error': True})

    return render_template('register.html', form=form.render())


@main.route("/plans")
def plans():
    return render_template('plans.html')


@main.route("/", methods=['GET', 'POST'])
def home():
    if g.user is not None and g.user.is_authenticated():
        projects = g.user.get_projects()
        return render_template('user_home.html', projects=projects)
    else:
        form = RegisterForm.get_sm()
        return render_template('home.html', form=form.render())


from featurelet.lib import catch_error_graceful
