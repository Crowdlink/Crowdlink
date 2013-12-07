from flask import Flask, current_app, jsonify
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager, user_unauthorized
from flask.ext.restful import Api
from flask_oauthlib.client import OAuth

from jinja2 import FileSystemLoader

import os


root = os.path.abspath(os.path.dirname(__file__) + '/../')

db = SQLAlchemy()
lm = LoginManager()
oauth = OAuth()

# OAuth configuration, must be outside function to be importable
github = oauth.remote_app(
    'github',
    app_key='GITHUB'
)


def create_app():

    # initialize our flask application
    app = Flask(__name__, static_folder='../static', static_url_path='/static')

    # set our template path and configs
    app.jinja_loader = FileSystemLoader(os.path.join(root, 'templates'))
    app.config.from_pyfile('../application.cfg')
    app.config.update(
        EMAIL_SERVER="localhost",
        EMAIL_DEBUG=0,
        EMAIL_USE_TLS=False,
        EMAIL_PORT=25
    )
    app.config['GITHUB'] = dict(
        consumer_key=app.config['GITHUB_CONSUMER_KEY'],
        consumer_secret=app.config['GITHUB_CONSUMER_SECRET'],
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

    # register all our plugins
    db.init_app(app)
    lm.init_app(app)
    oauth.init_app(app)
    api_restful = Api(app)

    # Monkey patch the login managers error function
    # =========================================================================
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
    # =========================================================================
    from flask import Request

    @property
    def dict_args(self):
        return {one: two for one, two in self.args.iteritems()}

    @property
    def json_dict(self):
        js = self.json
        if js is None:
            return {}
        return js
    Request.dict_args = dict_args
    Request.json_dict = json_dict

    # Route registration
    # =========================================================================
    from . import api, views, models
    app.register_blueprint(api.api, url_prefix='/api')
    app.register_blueprint(views.main)

    api_restful.add_resource(api.ProjectAPI, '/api/project')
    api_restful.add_resource(api.IssueAPI, '/api/issue')
    api_restful.add_resource(api.SolutionAPI, '/api/solution')

    return app
