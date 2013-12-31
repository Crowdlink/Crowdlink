from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager
from flask.ext.restful import Api
from flask_oauthlib.client import OAuth

from jinja2 import FileSystemLoader

import os
import json
import logging
import cryptacular.bcrypt


root = os.path.abspath(os.path.dirname(__file__) + '/../')

db = SQLAlchemy()
lm = LoginManager()
oauth = OAuth()
crypt = cryptacular.bcrypt.BCRYPTPasswordManager()

# OAuth configuration, must be outside function to be importable
github = oauth.remote_app(
    'github',
    app_key='github'
)


def create_app(config='/application.json'):

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
        request_token_params={'scope': 'user:email,repo'},
        base_url='https://api.github.com/',
        request_token_url=None,
        access_token_method='POST',
        access_token_url='https://github.com/login/oauth/access_token',
        authorize_url='https://github.com/login/oauth/authorize'
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
    oauth.init_app(app)
    api_restful = Api(app)

    # Setup the anonymous user to register a single role
    lm.anonymous_user = AnonymousUser

    # Route registration
    # =========================================================================
    from . import api, views, models, monkey_patch, fin_models, log_models
    app.register_blueprint(api.api, url_prefix='/api')
    app.register_blueprint(views.main)

    api_restful.add_resource(api.ProjectAPI, '/api/project')
    api_restful.add_resource(api.IssueAPI, '/api/issue')
    api_restful.add_resource(api.SolutionAPI, '/api/solution')
    api_restful.add_resource(api.UserAPI, '/api/user')
    api_restful.add_resource(api.ChargeAPI, '/api/charge')
    api_restful.add_resource(api.EarmarkAPI, '/api/earmark')
    api_restful.add_resource(api.RecipientAPI, '/api/recipient')
    api_restful.add_resource(api.TransferAPI, '/api/transfer')
    api_restful.add_resource(api.CommentAPI, '/api/comment')

    return app

from .api_base import AnonymousUser
