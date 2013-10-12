from flask import Blueprint, request, redirect, render_template, url_for, send_file, g, current_app
from flask.ext.login import login_user, logout_user, current_user, login_required

from featurelet import root, lm, app
from featurelet.models import User, Project, Improvement
from featurelet.forms import RegisterForm, LoginForm, NewProjectForm, NewImprovementForm

import json
import mongoengine
import os
import sys


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


@main.route("/account")
@login_required
def account():
    return render_template('account.html')


@main.route("/<username>/<url_key>")
def view_project(username=None, url_key=None):
    project = Project.objects.get(maintainer=User(username=username),
                                  url_key=url_key)
    return render_template('proj.html', project=project)


@main.route("/<purl_key>/<url_key>")
def view_improvement(purl_key=None, url_key=None):
    imp = Improvement.objects.get(url_key=url_key,
                                  project=Project(url_key=purl_key))
    return render_template('improvement.html', project=project)


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
            except mongoengine.errors.OperationError:
                form.start.add_error({'message': 'An unknown database error has occurred, this has been logged.'})
            except mongoengine.errors.ValidationError:
                form.start.add_error({'message': 'A database schema validation error has occurred. This has been logged.'})
            else:
                form.set_json_success(redirect=proj.get_abs_url())

        return form.render_json()

    return render_template('new_project.html', form=form.render())


@main.route("/new_improvement/<purl_key>", methods=['GET', 'POST'])
@login_required
def new_improvement(purl_key=None):
    # XXX Add check on the purl_key
    form = NewImprovementForm()
    if request.method == 'POST':
        if form.validate(request.form):
            data = form.data_by_attr()
            try:
                project = Project.objects.get(url_key=purl_key)
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

def catch_error_graceful(form):
    # grab current exception information
    exc, txt, tb = sys.exc_info()

    def log(msg):
        from pprint import pformat
        from traceback import format_exc
        current_app.logger.warn(
            "=============================================================\n" +
            "{0}\nRequest dump: {1}\n{2}\n".format(msg, pformat(vars(request)), format_exc()) +
            "=============================================================\n"
        )

    if exc is mongoengine.errors.OperationError:
        form.start.add_error({'message': 'An unknown database error has occurred, this has been logged.'})
        log("An unknown operation error occurred")
    elif exc is mongoengine.errors.ValidationError:
        form.start.add_error({'message': 'A database schema validation error has occurred. This has been logged with a high priority.'})
        log("A validation occurred.")
    elif exc is mongoengine.errors.InvalidQueryError:
        form.start.add_error({'message': 'A database schema validation error has occurred. This has been logged with a high priority.'})
        log("An inconsistency in the models was detected")
    else:
        form.start.add_error({'message': 'An unknown error has occurred'})
        log("")



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
