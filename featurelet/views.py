from flask import Blueprint, request, redirect, render_template, url_for, send_file, g
from flask.ext.login import login_user, logout_user, current_user, login_required

from featurelet import root, lm, app
from featurelet.models import User, Project
from featurelet.forms import RegisterForm, LoginForm, NewProjectForm

import json
import os

main = Blueprint('main', __name__, template_folder='../templates')

@app.before_request
def before_request():
    g.user = current_user

@lm.user_loader
def user_loader(id):
    return User.objects.get(id=id)

@main.route("/favicon.ico")
def favicon():
    return send_file(os.path.join(root, 'static/favicon.ico'))


@main.route("/account")
@login_required
def account():
    return render_template('account.html')


@main.route("/new_project", methods=['GET', 'POST'])
@login_required
def new_project():
    form = NewProjectForm()
    if request.method == 'POST':
        success, json = form.json_validate(request.form, piecewise=True)
        if success:
            data = form.data_by_attr()

        try:
            proj = Project(maintainer=g.user.id,
                           name=data['ptitle'],
                           website=data['website'],
                           source_url=data['source'],
                           description=data['description'])
        except mongoengine.errors.OperationError:
            return form.update_success({'redirect': '/test/'})
        else:
            return json

    return render_template('new_project.html', form=form.render())


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
        success, invalid_nodes = form.validate(request.form)
        data = form.data_by_attr()
        if success:
            try:
                user = User.objects.get(username=data['username'])
            except User.DoesNotExist:
                pass
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
        success, invalid_nodes = form.validate(request.form)
        data = form.data_by_attr()
        if success:
            user = User.create_user(data['username'], data['password'], data['email'])
            if user:
                login_user(user)
                return redirect(url_for('main.home'))
            else:
                form.start.add_error({'message': 'Unknown database error, please retry.', 'error': True})
    return render_template('register.html', form=form.render())


@main.route("/plans")
def plans():
    return render_template('plans.html')


@main.route("/")
def home():
    if g.user is not None and g.user.is_authenticated():
        return render_template('user_home.html')
    else:
        form = RegisterForm()
        return render_template('home.html', form=form.render())
