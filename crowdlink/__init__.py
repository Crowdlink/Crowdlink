from flask import Flask, request, redirect
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager
from flask.ext.oauthlib.client import OAuth

from jinja2 import FileSystemLoader

import os
import six
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
    config_vars = json.load(open(root + config))
    # merge the public and private keys
    public = list(six.iteritems(config_vars['public']))
    private = list(six.iteritems(config_vars['private']))
    config_vars = dict(private + public)
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
    class AnonymousUser(object):
        id = -100
        gh_token = None
        tw_token = None
        go_token = None

        def is_anonymous(self):
            return True

        def global_roles(self):
            return ['anonymous']

        def is_authenticated(self):
            return False

        def get(self):
            return self
    lm.anonymous_user = AnonymousUser

    # Route registration
    # =========================================================================
    from . import api, views, oauth, models, monkey_patch
    app.register_blueprint(api.api, url_prefix='/api')
    app.register_blueprint(views.main)

    # tell the session manager how to access the user object
    @lm.user_loader
    def user_loader(id):
        return None

    return app
