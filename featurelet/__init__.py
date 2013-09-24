from flask import Flask
from flask.ext.mongoengine import MongoEngine
from jinja2 import FileSystemLoader
from yota.renderers import JinjaRenderer

import os

app = Flask(__name__, static_folder='../static', static_url_path='/static')
root = os.path.abspath(os.path.dirname(__file__) + '/../')
app.jinja_loader = FileSystemLoader(os.path.join(root, 'templates'))
app.config["MONGODB_SETTINGS"] = {'DB': "featurelet"}
app.config["SECRET_KEY"] = "KeepThisS3cr3t"

# Patch out jinjarenderer to include templates that are local.
JinjaRenderer.search_path.insert(
    0, os.path.dirname(os.path.realpath(__file__)) + "/../templates/yota/")


db = MongoEngine(app)

def register_blueprints(app):
    # Prevents circular imports
    from featurelet.views import views
    app.register_blueprint(views)

register_blueprints(app)
