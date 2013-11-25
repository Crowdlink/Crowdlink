from flask import Blueprint, request, g, current_app, jsonify, abort
from flask.ext.login import login_required, logout_user, current_user, login_user
from flask.ext.restful import Resource

from . import root, lm, app, api_restful
from .models import User, Project, Issue, UserSubscriber, ProjectSubscriber, IssueSubscriber, Transaction
from .lib import get_json_joined, get_joined, redirect_angular
from .util import convert_args

import json
import bson
import mongoengine
import datetime
import os
import sys
import stripe

api = Blueprint('api_bp', __name__)


# Utility functions
# =============================================================================
@api.route("/user/check", methods=['POST'])
def check_user():
    """ Check if a specific username is taken """
    js = request.json

    # try to access the issue with identifying information
    try:
        username = js.pop('value')
        user = User.objects.get(username=username)
    except KeyError:
        return incorrect_syntax()
    except User.DoesNotExist:
        return jsonify(taken=False)
    else:
        return jsonify(taken=True)


@api.route("/purl_key/check", methods=['POST'])
@login_required
def check_ptitle():
    """ Check if a specific username is taken """
    js = request.json

    # try to access the issue with identifying information
    try:
        url_key = js.pop('value')
        project = Project.objects.get(username=g.user.username, url_key=url_key)
    except KeyError:
        return incorrect_syntax()
    except Project.DoesNotExist:
        return jsonify(taken=False)
    else:
        return jsonify(taken=True)


@api.route("/email/check", methods=['POST'])
def check_email():
    """ Check if a specific username is taken """
    js = request.json

    # try to access the issue with identifying information
    try:
        email = js.pop('value')
        user = User.objects.get(emails__address=email)
    except KeyError:
        return incorrect_syntax()
    except User.DoesNotExist:
        return jsonify(taken=False)
    else:
        return jsonify(taken=True)


# Project getter/setter
# =============================================================================

def catch_common(func):
    # tries to catch common exceptions and return properly
    def decorated(self, *args, **kwargs):
        # get the auth dictionary
        try:
            return func(self, *args, **kwargs)
        except KeyError:
            return {'error': 'Incorrect syntax'}, 400
        except self.model.DoesNotExist:
            return {'error': 'Could not be found'}, 404
        except AssertionError:  # all permissions should be done via assertions
            return {'error': 'You don\'t have permission to do that'}, 403

    return decorated

class BaseResource(Resource):
    def update_model(self, data, project):
        # updates all fields if data is provided, checks acl
        for field in self.model._fields:
            new_val = data.pop(field, None)
            assert project.can('edit_' + field)
            project[field] = new_val


class ProjectAPI(BaseResource):
    model = Project

    def get_project(self, data):
        proj_id = data.pop('id', None)
        username = data.pop('username', None)
        url_key = data.pop('url_key', None)

        if url_key and username:
            return Project.objects.get(url_key=url_key, username=username)
        else:
            return Project.objects.get(id=proj_id)

    @catch_common
    def get(self):
        data = request.dict_args()
        join_prof = data.pop('join_prof', 'standard_join')
        project = self.get_project(data)
        assert project.can('view_' + join_prof)
        return get_joined(project, join_prof=join_prof)

    @catch_common
    def put(self):
        data = request.dict_args()
        project = self.get_project(data)

        self.update_model(data, project)

        sub_status = data.pop('subscribed', None)
        if sub_status == True:
            # Subscription logic, will need to be expanded to allow granular selection
            subscribe = ProjectSubscriber(user=g.user.id)
            project.subscribe(subscribe)
        elif sub_status == False:
            project.unsubscribe(g.user)

        vote_status = data.pop('vote_status', None)
        if vote_status is not None:
            project.set_vote(vote_status)

        try:
            project.save()
        except mongoengine.errors.ValidationError as e:
            return {'success': False, 'validation_errors': e.to_dict()}

        # return a true value to the user
        return_val['success'] = True
        return return_val

api_restful.add_resource(ProjectAPI, '/api/project')

# User getter/setter
# =============================================================================
@api.route("/user", methods=['GET'])
@login_required
def get_user():
    js = request.args
    join_prof = request.args.get('join_prof', 'standard_join')

    # try to access the issue with identifying information
    try:
        username = js.get('username', None)
        userid = js.get('id', None)

        if username:
            user = User.objects.get(username=username)
        elif userid:
            user = User.objects.get(id=userid)
        else:
            return incorrect_syntax()
        return get_json_joined(user, join_prof=join_prof)
    except User.DoesNotExist:
        pass
    return resource_not_found()


@api.route("/user", methods=['POST'])
@login_required
def update_user():
    js = request.json

    # try to access the issue with identifying information
    try:
        username = js.pop('username')
        user = User.objects.get(username=username)
    except KeyError:
        return incorrect_syntax()
    except User.DoesNotExist:
        return resource_not_found()

    status = js.pop('subscribed', None)
    if status == True:
        # Subscription logic, will need to be expanded to allow granular selection
        subscribe = UserSubscriber(user=g.user.id)
        user.subscribe(subscribe)
    elif status == False:
        user.unsubscribe(g.user)

    try:
        user.save()
    except mongoengine.errors.ValidationError as e:
        return jsonify(success=False, validation_errors=e.to_dict())

    return jsonify(success=True)


# Issue getter/setter
# =============================================================================
@api.route("/issue", methods=['GET'])
def get_issue():
    args = request.args
    limit = args.get('limit', 15)
    username = args.get('username', None)
    purl_key = args.get('purl_key', None)
    project = args.get('project', None)
    url_key = args.get('url_key', None)
    join_prof = request.args.get('join_prof', 'standard_join')
    if (purl_key and username) and not project:
        try:
            project = Project.objects.get(username=username, url_key=purl_key).id
        except Issue.DoesNotExist:
            return resource_not_found()

    try:
        # if the request was for a single issue
        if url_key:
            issue = Issue.objects(project=project, url_key=url_key)
        else:
            issue = Issue.objects(project=project)[:limit]
        return get_json_joined(issue, join_prof=join_prof)
    except KeyError:
        return incorrect_syntax()
    except Issue.DoesNotExist:
        return resource_not_found()


@api.route("/issue", methods=['POST'])
@login_required
def update_issue():
    js = request.json
    return_val = {}

    # try to access the issue with identifying information
    try:
        proj_id = js.pop('project', None)
        url_key = js.pop('url_key', None)
        if url_key and proj_id:
            issue = Issue.objects.get(project=proj_id,
                                          url_key=url_key)
        else:
            issue_id = js.pop('id')
            issue = Issue.objects.get(id=issue_id)
    except KeyError:
        return incorrect_syntax()
    except Issue.DoesNotExist:
        return resource_not_found()

    brief = js.pop('brief', None)
    if brief and 'brief' in issue.user_acl:
        issue.brief = brief

    desc = js.pop('desc', None)
    if desc and 'desc' in issue.user_acl:
        issue.desc = desc

    sub_status = js.pop('subscribed', None)
    if sub_status == True:
        # Subscription logic, will need to be expanded to allow granular selection
        subscribe = IssueSubscriber(user=g.user.id)
        issue.subscribe(subscribe)
    elif sub_status == False:
        issue.unsubscribe(g.user)

    vote_status = js.pop('vote_status', None)
    if vote_status is not None:
        issue.set_vote(vote_status)

    status = js.pop('status', None)
    if status:
        issue.set_status(status)

    try:
        issue.save()
    except mongoengine.errors.ValidationError as e:
        return jsonify(success=False, validation_errors=e.to_dict())

    # return a true value to the user
    return_val.update({'success': True})
    return jsonify(return_val)

@api.route("/logout")
@login_required
def logout():
    logout_user()
    return jsonify(access_denied=True)

@api.route("/login", methods=['POST'])
def login():
    js = request.json

    try:
        user = User.objects.get(username=js['username'])
        if user.check_password(js['password']):
            login_user(user)
        else:
            return jsonify(success=False, message="Invalid credentials")
    except KeyError:
        return jsonify(success=False, message="Invalid credentials")
    except User.DoesNotExist:
        return jsonify(success=False, message="Invalid credentials")

    return jsonify(success=True, user=get_joined(user))


# Finance related function
# =============================================================================
@api.route("/transaction", methods=['GET'])
def transaction():
    js = request.args

    userid = request.args.get('userid', None)

    # try to access the issue with identifying information
    try:
        trans = Transaction.objects(user=userid)
        return get_json_joined(trans)
    except KeyError as e:
        return incorrect_syntax()
    except Transaction.DoesNotExist, mongoengine.errors.ValidationError:
        return resource_not_found()


@api.route("/charge", methods=['POST'])
def run_charge():
    js = request.json

    # try to access the issue with identifying information
    try:
        amount = js['amount']
        card = js['token']['id']
        livemode = js['token']['livemode']
        if amount > 100000 or amount < 500:
            return incorrect_syntax()
        user = User.objects.get(id=js['userid'])

        stripe.api_key = app.config['STRIPE_SECRET_KEY']
        try:
            retval = stripe.Charge.create(
                amount=amount,
                currency="usd",
                card=card)
        except stripe.CardError as e:
            body = e.json_body
            err  = body['error']

            current_app.logger.info(err)
            return jsonify(success=False)
        except stripe.InvalidRequestError, e:
            current_app.logger.error(
                "An InvalidRequestError was recieved from stripe."
                "Original token information: {0}".format(js['token']))
            return jsonify(success=False)
        except stripe.AuthenticationError, e:
            current_app.logger.error(
                "An AuthenticationError was recieved from stripe."
                "Original token information: {0}".format(js['token']))
            return jsonify(success=False)
        except stripe.APIConnectionError, e:
            current_app.logger.warn(
                "An APIConnectionError was recieved from stripe."
                "Original token information: {0}".format(js['token']))
            return jsonify(success=False)
        except stripe.StripeError, e:
            current_app.logger.warn(
                "An StripeError occurred in stripe API."
                "Original token information: {0}".format(js['token']))
            return jsonify(success=False)
        else:
            if retval['paid']:
                status = Transaction.StatusVals.Cleared.index
            else:
                status = Transaction.StatusVals.Pending.index

            trans = Transaction(
                amount=amount,
                livemode=livemode,
                stripe_id=retval['id'],
                created=datetime.datetime.fromtimestamp(retval['created']),
                user=user.id,
                _status=status,
                last_four=retval['card']['last4']
            )
            trans.save()

    except KeyError:
        return incorrect_syntax()
    except User.DoesNotExist:
        return resource_not_found()

    return jsonify(success=True)

def incorrect_syntax(message='Incorrect syntax', **kwargs):
    return jsonify(code=400, message=message, **kwargs)

def resource_not_found(message='Asset does not exist', **kwargs):
    return jsonify(code=404, message=message, **kwargs)
