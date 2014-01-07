from flask import Flask, request, url_for, redirect
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager
from flask.ext.oauthlib.client import OAuth

from jinja2 import FileSystemLoader

import os
import json
import logging
import cryptacular.bcrypt
import sqlalchemy


root = os.path.abspath(os.path.dirname(__file__) + '/../')

db = SQLAlchemy()
lm = LoginManager()
oauth_lib = OAuth()
crypt = cryptacular.bcrypt.BCRYPTPasswordManager()

# OAuth configuration, must be outside function to be importable
github = oauth_lib.remote_app(
    'github',
    app_key='github'
)
twitter = oauth_lib.remote_app(
    'twitter',
    app_key='twitter'
)
google = oauth_lib.remote_app(
    'google',
    app_key='google'
)


app = None


def create_app(config='/application.json'):
    global app

    # initialize our flask application
    app = Flask(__name__, static_folder='../static', static_url_path='/static')

    # set our template path and configs
    app.jinja_loader = FileSystemLoader(os.path.join(root, 'templates'))
    config_vars = json.loads(file(root + config).read())
    # merge the public and private keys
    config_vars = dict(config_vars['public'].items() + config_vars['private'].items())
    for key, val in config_vars.items():
        app.config[key] = val
    app.config['github'] = dict(
        consumer_key=app.config['github_consumer_key'],
        consumer_secret=app.config['github_consumer_secret'],
        request_token_params={'scope': 'user:email'},
        base_url='https://api.github.com/',
        request_token_url=None,
        access_token_method='POST',
        access_token_url='https://github.com/login/oauth/access_token',
        authorize_url='https://github.com/login/oauth/authorize'
    )
    app.config['twitter'] = dict(
        consumer_key=app.config['twitter_consumer_key'],
        consumer_secret=app.config['twitter_consumer_secret'],
        base_url='https://api.twitter.com/1.1/',
        request_token_url='https://api.twitter.com/oauth/request_token',
        access_token_url='https://api.twitter.com/oauth/access_token',
        authorize_url='https://api.twitter.com/oauth/authenticate',
    )
    app.config['google'] = dict(
        consumer_key=app.config['google_consumer_key'],
        consumer_secret=app.config['google_consumer_secret'],
        request_token_params={'scope': 'email profile'},
        base_url='https://www.googleapis.com/oauth2/v1/',
        request_token_url=None,
        access_token_method='POST',
        access_token_url='https://accounts.google.com/o/oauth2/token',
        authorize_url='https://accounts.google.com/o/oauth2/auth',
    )

    # add the debug toolbar if we're in debug mode...
    if app.config['DEBUG']:
        from flask_debugtoolbar import DebugToolbarExtension
        DebugToolbarExtension(app)
        app.logger.handlers[0].setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(filename)s:%(lineno)d]'))

    # register all our plugins
    db.init_app(app)
    lm.init_app(app)
    oauth_lib.init_app(app)

    # Setup the anonymous user to register a single role
    lm.anonymous_user = AnonymousUser

    # Route registration
    # =========================================================================
    from . import api, views, oauth, models, monkey_patch, fin_models, log_models
    app.register_blueprint(api.api, url_prefix='/api')
    app.register_blueprint(views.main)

    # tell the session manager how to access the user object
    @lm.user_loader
    def user_loader(id):
        try:
            return models.User.query.filter_by(id=id).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    def error_handler(e, code):
        # prevent error loops
        if request.path == '/':
            return str(code)
        return redirect(url_for('main.angular_root', _anchor='/errors/' + str(code)))

    app.register_error_handler(404, lambda e: error_handler(e, 404))
    app.register_error_handler(400, lambda e: error_handler(e, 400))
    app.register_error_handler(402, lambda e: error_handler(e, 402))
    app.register_error_handler(403, lambda e: error_handler(e, 403))
    app.register_error_handler(409, lambda e: error_handler(e, 409))
    app.register_error_handler(500, lambda e: error_handler(e, 500))

    return app

from .api_base import AnonymousUser
