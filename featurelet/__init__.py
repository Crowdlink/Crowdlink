from flask import Flask, g, current_app, abort, jsonify, request
from flask.ext.mongoengine import MongoEngine
from flask.ext.login import LoginManager, current_user, user_unauthorized
from flask.ext.restful import Api
from flask_oauthlib.client import OAuth

from jinja2 import FileSystemLoader

from . import util

import babel.dates as dates
import os
import datetime
import mongoengine

root = os.path.abspath(os.path.dirname(__file__) + '/../')

# initialize our flask application
app = Flask(__name__, static_folder='../static', static_url_path='/static')
# set our template path and configs
app.jinja_loader = FileSystemLoader(os.path.join(root, 'templates'))
app.config.update(
    EMAIL_SERVER="localhost",
    EMAIL_DEBUG=0,
    EMAIL_USE_TLS=False,
    EMAIL_PORT=25
)
app.config.from_pyfile('../application.cfg')

if app.config['DEBUG']:
    from flask_debugtoolbar import DebugToolbarExtension
    toolbar = DebugToolbarExtension(app)

# Setup login stuff
lm = LoginManager()
lm.init_app(app)

# api extension
api_restful = Api(app)

# Monkey patch the login managers error function
def unauthorized(self):
    '''
    This is a slightly patched version of the default flask-login
    de-auth function. Instead of a 302 redirect we pass some json back
    for angular to catch
    '''
    user_unauthorized.send(current_app._get_current_object())

    if self.unauthorized_callback:
        return self.unauthorized_callback()

    return jsonify(access_denied=True)
LoginManager.unauthorized = unauthorized

# Monkey patch flasks request to inject a helper function
from flask import Request
def dict_args(self):
    return {one: two for one, two in self.args.iteritems()}
Request.dict_args = dict_args


# OAuth configuration
oauth = OAuth(app)
github = oauth.remote_app(
        'github',
        consumer_key=app.config['GITHUB_CONSUMER_KEY'],
        consumer_secret=app.config['GITHUB_CONSUMER_SECRET'],
        request_token_params={'scope': 'user:email,repo'},
        base_url='https://api.github.com/',
        request_token_url=None,
        access_token_method='POST',
        access_token_url='https://github.com/login/oauth/access_token',
        authorize_url='https://github.com/login/oauth/authorize'
)


# Try to force a server reload if we can't connect to mongodb. Inelegant, really
# should be changed before release! XXX
error_occured = False
try:
    db = MongoEngine(app)
except mongoengine.connection.ConnectionError:
    app.logger.warn("Couldn't load database, using mock object")
    import mock
    db = mock.Mock()
    error_occured = True

@app.before_first_request
def first_req():
    if error_occured:
        # If there was a database failure, raise an exception to trigger the
        # reload of the application when the first request comes in
        raise AttributeError

# General configuration
# ======================

# Add a date format filter to jinja templating
@app.template_filter('datetime')
def format_datetime(value, format='medium'):
    if format == 'full':
        format="EEEE, d. MMMM y 'at' HH:mm"
    elif format == 'medium':
        format="EE dd.MM.y HH:mm"
    return dates.format_datetime(value, format)

@app.template_filter('date')
def format_datetime(value, format='medium'):
    if format == 'full':
        format="EEEE, d. MMMM y"
    elif format == 'medium':
        format="EE dd.MM.y"
    return dates.format_datetime(value, format)

@app.template_filter('plural')
def plural(value):
    if value > 1:
        return 's'
    else:
        return ''

@app.template_filter('attrencode')
def attr_encode(value):
    html_escape_table = {
        "&": "&amp;",
        '"': "&quot;",
        "'": "&apos;",
        ">": "&gt;",
        "<": "&lt;",
    }
    return "".join(html_escape_table.get(c,c) for c in value)

@app.template_filter('date_ago')
def format_date_ago(time):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    now = datetime.datetime.now()
    if type(time) is int:
        diff = now - datetime.fromtimestamp(time)
    elif isinstance(time, datetime.datetime):
        diff = now - time
    elif not time:
        diff = now - now
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return str(second_diff) + " seconds ago"
        if second_diff < 120:
            return  "a minute ago"
        if second_diff < 3600:
            return str( second_diff / 60 ) + " minutes ago"
        if second_diff < 7200:
            return "an hour ago"
        if second_diff < 86400:
            return str( second_diff / 3600 ) + " hours ago"
    if day_diff == 1:
        return "Yesterday"
    if day_diff < 7:
        return str(day_diff) + " days ago"
    if day_diff < 31:
        return str(day_diff/7) + " weeks ago"
    if day_diff < 365:
        return str(day_diff/30) + " months ago"
    return str(day_diff/365) + " years ago"

from . import api, views, models
app.register_blueprint(api.api, url_prefix='/api')
app.register_blueprint(views.main)
