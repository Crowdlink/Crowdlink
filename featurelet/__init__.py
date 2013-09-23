import datetime
from flask import Flask, Blueprint, render_template, url_for, request, send_file
import json
from flask.ext.mongoengine import MongoEngine
from flask.views import MethodView
from featurelet.forms import *
import cryptacular.bcrypt
import os
from jinja2 import FileSystemLoader
from yota.renderers import JinjaRenderer


app = Flask(__name__, static_folder='../static', static_url_path='/static')
root = os.path.abspath(os.path.dirname(__file__) + '/../')
app.jinja_loader = FileSystemLoader(os.path.join(root, 'templates'))
app.config["MONGODB_SETTINGS"] = {'DB': "featurelet"}
app.config["SECRET_KEY"] = "KeepThisS3cr3t"

# Patch out jinjarenderer to include templates that are local.
JinjaRenderer.search_path.insert(
    0, os.path.dirname(os.path.realpath(__file__)) + "/../templates/yota/")


db = MongoEngine(app)
user = "isaac"


@app.route("/favicon.ico")
def favicon():
    return send_file(os.path.join(root, 'static/favicon.ico'))


@app.route("/u/<username>")
def user(username=None):
    user = User.objects.get(username=username)
    return render_template('prof.html', user=user)


@app.route("/register")
def register():
    return render_template('register.html')


@app.route("/plans")
def plans():
    return render_template('plans.html')


@app.route("/")
def hello():
    form = RegisterForm()
    return render_template('home.html', form=form.render())


class User(db.Document):
    id = db.ObjectIdField()
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)
    _password = db.StringField(max_length=1023, required=True)
    username = db.StringField(max_length=32, min_length=3, unique=True)

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, val):
        self._password = unicode(crypt.encode(val))

    def get_absolute_url(self):
        return url_for('user', username=self.username)

if __name__ == "__main__":
    app.debug = True
    app.run(host='0.0.0.0')
