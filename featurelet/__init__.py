from flask import Flask, g
from flask.ext.mongoengine import MongoEngine
from flask.ext.login import LoginManager, current_user
from jinja2 import FileSystemLoader
from yota.renderers import JinjaRenderer
from yota import Form

import babel.dates as dates
import os
import datetime
import mongoengine

root = os.path.abspath(os.path.dirname(__file__) + '/../')

# initialize our flask application
app = Flask(__name__, static_folder='../static', static_url_path='/static')
app.debug = True

# Setup login stuff
lm = LoginManager()
lm.init_app(app)
lm.login_view = 'login'

# set our template path
app.jinja_loader = FileSystemLoader(os.path.join(root, 'templates'))
# setup mongo connection information
app.config["MONGODB_SETTINGS"] = {'DB': "featurelet"}
app.config["SECRET_KEY"] = "KeepThisS3cr3t"

try:
    db = MongoEngine(app)
except mongoengine.connection.ConnectionError:
    import mock
    db = mock.Mock()
    error_occured = True

@app.before_first_request
def first_req():
    if error_occured:
        # If there was a database failure, raise an exception to trigger the
        # reload of the application when the first request comes in
        raise AttributeError

# patch yota to use bootstrap3
JinjaRenderer.templ_type = 'bs3'
JinjaRenderer.search_path.insert(0, root + "/templates/yota/")
Form.type_class_map = {'error': 'alert alert-danger',
                      'info': 'alert alert-info',
                      'success': 'alert alert-success',
                      'warn': 'alert alert-warn'}

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

# Make user availible easily in the global var
@app.before_request
def before_request():
    g.user = current_user

# tell the session manager how to access the user object
@lm.user_loader
def user_loader(id):
    return User.objects.get(username=id)

from featurelet import views, models
app.register_blueprint(views.main)
