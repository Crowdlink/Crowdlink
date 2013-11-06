from flask import Blueprint, request, g, current_app, jsonify, abort
from flask.ext.login import login_required, logout_user, current_user

from . import root, lm, app
from .models import User, Project, Improvement, UserSubscriber, ProjectSubscriber, ImpSubscriber
from .forms import RegisterForm, LoginForm, NewProjectForm, NewImprovementForm
from .lib import get_json_joined

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

    if vote_status and not imp.set_vote(g.user):
        if imp.vote_status:
            return jsonify(success=False, code='already_voted', disp="Already voted!")
        else:
            return jsonify(success=False)
    elif not vote_status and not imp.set_unvote(g.user):
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

@api.route("/improvement", methods=['GET'])
def get_improvements():
    args = request.args
    fltr = args.get('filter', None)
    limit = args.get('limit', 15)

    # try to access the improvements with identifying information
    try:
        # If the user is running a fulltext search
        if fltr:
            coll = Improvement._get_collection()
            # Run the fulltext search command manually
            results = coll.database.command(
                "text",
                coll.name,
                search=fltr,
                limit=limit)
            improvements = []
            for res in results['results']:
                # Kinda hacky. We make an in memory improvement to generate
                # properties and join them in for return
                prop = Improvement(**res['obj']).jsonize(
                    raw=1,
                    **Improvement.standard_join)
                res['obj'].update(prop)
                improvements.append(res['obj'])
            # Serialize the bson directly, rather than proxying to improvement
            # objects
            return bson.json_util.dumps(improvements)
        # otherwise, just dump the project results back
        else:
            return get_json_joined(Improvement.objects(project=args['project'])[:limit])
    except KeyError:
        return incorrect_syntax()
    except Improvement.DoesNotExist:
        return resource_not_found()


@api.route("/improvement", methods=['POST'])
@login_required
def update_improvement():
    js = request.json
    return_val = {}

    # try to access the improvement with identifying information
    try:
        proj_id = js.pop('project', None)
        url_key = js.pop('url_key', None)
        if url_key and proj_id:
            imp = Improvement.objects.get(project=proj_id,
                                          url_key=url_key)
        else:
            imp_id = js.pop('id')
            imp = Improvement.objects.get(id=imp_id)
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
        if js.pop('render_md', True):
            return_val['md'] = imp.md

    sub_status = js.pop('subscribed', None)
    if sub_status == True:
        # Subscription logic, will need to be expanded to allow granular selection
        subscribe = ImpSubscriber(user=g.user.username)
        imp.subscribe(subscribe)
    elif sub_status == False:
        imp.unsubscribe(g.user.username)

    open_status = js.pop('open', None)
    if open_status == True:
        imp.set_open()
    elif open_status == False:
        imp.set_close()

    try:
        imp.save()
    except mongoengine.errors.ValidationError as e:
        return jsonify(success=False, validation_errors=e.to_dict())

    # return a true value to the user
    return_val.update({'success': True})
    return jsonify(return_val)

def incorrect_syntax(message='Incorrect syntax', **kwargs):
    return jsonify(code=400, message=message, **kwargs)

def resource_not_found(message='Asset does not exist', **kwargs):
    return jsonify(code=404, message=message, **kwargs)
