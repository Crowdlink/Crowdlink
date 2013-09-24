from flask import Blueprint, request, redirect, render_template, url_for
from flask import current_app
from featurelet.models import User
from featurelet.forms import RegisterForm

import json

views = Blueprint('posts', __name__, template_folder='../templates')


@views.route("/favicon.ico")
def favicon():
    return send_file(os.path.join(root, 'static/favicon.ico'))


@views.route("/u/<username>")
def user(username=None):
    user = User.objects.get(username=username)
    return render_template('prof.html', user=user)


@views.route("/signup", methods=['GET', 'POST'])
def signup():
    form = RegisterForm()

    if request.method == 'POST':
        success, invalid_nodes = form.validate(request.form)
        data = form.data_by_attr()
        if success:
            print "Whoohooo!"
    return render_template('register.html', form=form.render())


@views.route("/plans")
def plans():
    return render_template('plans.html')


@views.route("/")
def hello():
    form = RegisterForm()
    return render_template('home.html', form=form.render())
