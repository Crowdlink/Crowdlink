from flask import Flask, g
from flask.ext.mongoengine import MongoEngine
from flask.ext.login import LoginManager, current_user
from jinja2 import FileSystemLoader
from yota.renderers import JinjaRenderer
from yota import Form

import babel.dates as dates
import os

root = os.path.abspath(os.path.dirname(__file__) + '/../')

# initialize our flask application
app = Flask(__name__, static_folder='../static', static_url_path='/static')

# Setup login stuff
lm = LoginManager()
lm.init_app(app)
lm.login_view = 'login'

# set our template path
app.jinja_loader = FileSystemLoader(os.path.join(root, 'templates'))
# setup mongo connection information
app.config["MONGODB_SETTINGS"] = {'DB': "featurelet"}
app.config["SECRET_KEY"] = "KeepThisS3cr3t"
db = MongoEngine(app)

# patch yota to use bootstrap3
JinjaRenderer.templ_type = 'bs3'
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

# Make user availible easily in the global var
@app.before_request
def before_request():
    g.user = current_user

# tell the session manager how to access the user object
@lm.user_loader
def user_loader(id):
    return User.objects.get(id=id)

from featurelet import views, models
app.register_blueprint(views.main)
