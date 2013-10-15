from flask import Blueprint, request, g, current_app, jsonify, abort
from flask.ext.login import login_required, logout_user, current_user

from featurelet import root, lm, app
from featurelet.models import User, Project, Improvement
from featurelet.forms import RegisterForm, LoginForm, NewProjectForm, NewImprovementForm

import json
import mongoengine
import os
import sys

api = Blueprint('api', __name__)

@api.route("/vote", methods=['POST'])
@login_required
def vote_api():
    js = request.json
    try:
        imp = Improvement.objects.get(project=js['proj_id'],
                                    url_key=js['url_key'])
    except KeyError:
        return incorrect_syntax()
    except Improvement.DoesNotExist:
        return resource_not_found()

    if not imp.vote(g.user):
        if g.user in imp.vote_list:
            return jsonify(success=False, code='already_voted')
        else:
            return jsonify(success=False)

    return jsonify(success=True)

def incorrect_syntax(message='Incorrect syntax'):
    response = jsonify({'code': 400,'message': message})
    response.status_code = 400
    return response

def resource_not_found(message='Asset does not exist'):
    response = jsonify({'code': 404,'message': message})
    response.status_code = 404
    return response
