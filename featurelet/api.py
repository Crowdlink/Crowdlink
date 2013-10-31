from flask import Blueprint, request, g, current_app, jsonify, abort
from flask.ext.login import login_required, logout_user, current_user

from featurelet import root, lm, app
from featurelet.models import User, Project, Improvement, UserSubscriber, ProjectSubscriber, ImpSubscriber
from featurelet.forms import RegisterForm, LoginForm, NewProjectForm, NewImprovementForm

import json
import bson
import mongoengine
import os
import sys

api = Blueprint('api', __name__)

@api.route("/vote", methods=['POST'])
@login_required
def vote_api():
    js = request.json
    try:
        imp = Improvement.objects.get(
            project=js['project'],
            url_key=js['url_key'])
        vote_status = js['vote_status']
    except KeyError:
        return incorrect_syntax()
    except Improvement.DoesNotExist:
        return resource_not_found()

    if vote_status and not imp.vote(g.user):
        if imp.vote_status:
            return jsonify(success=False, code='already_voted', disp="Already voted!")
        else:
            return jsonify(success=False)
    elif not vote_status and not imp.unvote(g.user):
        if not imp.vote_status:
            return jsonify(success=False, code='already_voted', disp="Haven't voted yet")
        else:
            return jsonify(success=False)

    return jsonify(success=True)


@api.route("/project", methods=['POST'])
@login_required
def update_project():
    js = request.json

    # try to access the improvement with identifying information
    try:
        proj_id = js.pop('id')
        project = Project.objects.get(id=proj_id)
    except KeyError:
        return incorrect_syntax()
    except Improvement.DoesNotExist:
        return resource_not_found()

    status = js.pop('subscribed', None)
    if status == True:
        # Subscription logic, will need to be expanded to allow granular selection
        subscribe = ProjectSubscriber(user=g.user.username)
        project.subscribe(subscribe)
    elif status == False:
        project.unsubscribe(g.user.username)

    try:
        project.save()
    except mongoengine.errors.ValidationError as e:
        return jsonify(success=False, validation_errors=e.to_dict())

    return jsonify(success=True)


@api.route("/user", methods=['POST'])
@login_required
def update_user():
    js = request.json

    # try to access the improvement with identifying information
    try:
        username = js.pop('username')
        user = User.objects.get(username=username)
    except KeyError:
        return incorrect_syntax()
    except Improvement.DoesNotExist:
        return resource_not_found()

    status = js.pop('subscribed', None)
    if status == True:
        # Subscription logic, will need to be expanded to allow granular selection
        subscribe = UserSubscriber(user=g.user.username)
        user.subscribe(subscribe)
    elif status == False:
        user.unsubscribe(g.user.username)

    try:
        user.save()
    except mongoengine.errors.ValidationError as e:
        return jsonify(success=False, validation_errors=e.to_dict())

    return jsonify(success=True)

@api.route("/improvements", methods=['GET'])
def get_improvements():
    args = request.args
    fltr = args.get('filter', None)
    limit = args.get('limit', 10)

    # try to access the improvements with identifying information
    try:
        if fltr:
            coll = Improvement._get_collection()
            # Run the fulltext search command manually
            results = coll.database.command(
                "text",
                coll.name,
                search=fltr,
                limit=15)
            improvements = []
            for res in results['results']:
                prop = Improvement(**res['obj']).jsonize(
                    raw=1,
                    get_abs_url=1,
                    vote_status=1,
                    project=1)
                res['obj'].update(prop)
                print res['obj']
                improvements.append(res['obj'])
            # Serialize the bson directly, rather than proxying to improvement
            # objects
            return bson.json_util.dumps(improvements)
        else:
            improvements = Improvement.objects(project=args['project'])[:limit]
    except KeyError:
        return incorrect_syntax()
    except Improvement.DoesNotExist:
        return resource_not_found()

    return improvements.to_json()

@api.route("/improvement", methods=['POST'])
@login_required
def update_improvement():
    js = request.json

    # try to access the improvement with identifying information
    try:
        proj_id = js.pop('project')
        url_key = js.pop('url_key')
        imp = Improvement.objects.get(project=proj_id,
                                    url_key=url_key)
    except KeyError:
        return incorrect_syntax()
    except Improvement.DoesNotExist:
        return resource_not_found()

    brief = js.pop('brief', None)
    if brief:
        imp.brief = brief

    desc = js.pop('description', None)
    if desc:
        imp.description = desc

    status = js.pop('subscribed', None)
    if status == True:
        # Subscription logic, will need to be expanded to allow granular selection
        subscribe = ImpSubscriber(user=g.user.username)
        imp.subscribe(subscribe)
    elif status == False:
        imp.unsubscribe(g.user.username)

    try:
        imp.save()
    except mongoengine.errors.ValidationError as e:
        return jsonify(success=False, validation_errors=e.to_dict())

    return jsonify(success=True)

def incorrect_syntax(message='Incorrect syntax', **kwargs):
    print "testing"
    return jsonify(code=400, message=message, **kwargs)

def resource_not_found(message='Asset does not exist', **kwargs):
    return jsonify(code=404, message=message, **kwargs)
