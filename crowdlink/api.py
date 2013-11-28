from flask import Blueprint, request, g, current_app, jsonify, abort
from flask.ext.login import login_required, logout_user, current_user, login_user
from flask.ext.restful import Resource

from . import root, lm, app, api_restful
from .models import (User, Project, Issue, UserSubscriber, ProjectSubscriber,
                     IssueSubscriber, Transaction, Solution, SolutionSubscriber)
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

def catch_create(func):
    # catch errors that are common to creation actions
    def decorated(self, *args, **kwargs):
        # get the auth dictionary
        try:
            return func(self, *args, **kwargs)
        except KeyError:
            return {'error': 'Incorrect syntax'}, 400
        except mongoengine.errors.ValidationError as e:
            return {'success': False, 'validation_errors': e.to_dict()}
        except AssertionError:  # all permissions should be done via assertions
            return {'error': 'You don\'t have permission to do that'}, 403
        except mongoengine.errors.NotUniqueError as e:
            return {'success': False, 'message': e.message}

    return decorated

class BaseResource(Resource):
    def update_model(self, data, model):
        # updates all fields if data is provided, checks acl
        for field in self.model._fields:
            new_val = data.pop(field, None)
            if new_val:
                assert model.can('edit_' + field)
                model[field] = new_val


class ProjectAPI(BaseResource):
    model = Project

    @classmethod
    def get_project(cls, data, minimal=False):
        proj_id = data.pop('id', None)

        # Mild optimization for objects that need to get the project from
        # url_key and username
        if minimal:
            base = Project.objects.only('id', 'url_key')
        else:
            base = Project.objects

        if proj_id:
            return base.get(id=proj_id)


        return base.get(url_key=data['url_key'],
                        username=data['username'])

    @catch_common
    def get(self):
        data = request.dict_args()
        join_prof = data.pop('join_prof', 'standard_join')
        project = self.get_project(data)

        # not currently handled elegantly, here's a manual workaround
        if join_prof == 'issue_join':
            issues = project.issues()
            issue_join_prof = data.pop('issue_join_prof', 'standard_join')
            for issue in issues:
                assert issue.can('view_brief_join')
            return {'issues': get_joined(issues, issue_join_prof)}

        assert project.can('view_' + join_prof)
        return get_joined(project, join_prof=join_prof)

    @catch_common
    def put(self):
        data = request.json
        project = self.get_project(data)
        return_val = {}

        self.update_model(data, project)

        sub_status = data.pop('subscribed', None)
        if sub_status:
            assert project.can('action_watch')
        if sub_status == True:
            # Subscription logic, will need to be expanded to allow granular selection
            subscribe = ProjectSubscriber(user=g.user.id)
            project.subscribe(subscribe)
        elif sub_status == False:
            project.unsubscribe(g.user)

        vote_status = data.pop('vote_status', None)
        if vote_status:
            assert project.can('action_vote')
        if vote_status is not None:
            project.set_vote(vote_status)

        try:
            project.save()
        except mongoengine.errors.ValidationError as e:
            return {'success': False, 'validation_errors': e.to_dict()}

        # return a true value to the user
        return_val['success'] = True
        return return_val

    @catch_create
    def post(self):
        data = request.json
        project = Project()
        project.username = g.user.username
        project.maintainer = g.user.get()
        project.url_key = data.get('url_key')
        project.name = data.get('name')
        project.website = data.get('website')
        project.description = data.get('website')

        project.save()

        return {'success': True}


# Solution getter/setter
# =============================================================================
class SolutionAPI(BaseResource):
    model = Solution

    @classmethod
    def get_solution(cls, data):
        return Issue.objects.get(id=data['id'])

    @catch_create
    def post(self):
        data = request.json
        issue = IssueAPI.get_issue(data)
        # ensure that the user was allowed to insert that issue
        assert issue.can('action_add_solution')

        sol = Solution()
        sol.title = data.get('title')
        sol.create_key()
        sol.desc = data.get('description')
        sol.issue = issue
        sol.creator = g.user.get()

        sol.save()

        return {'success': True, 'url_key': sol.url_key}

    @catch_common
    def get(self):
        data = request.dict_args()
        join_prof = data.get('join_prof', 'standard_join')

        sol = SolutionAPI.get_solution(data)
        return get_joined(sol, join_prof=join_prof)


    @catch_common
    def put(self):
        data = request.json
        return_val = {}

        sol = IssueAPI.get_issue(data)

        # updating of regular attributes
        self.update_model(data, sol)

        sub_status = data.pop('subscribed', None)
        if sub_status:
            assert sol.can('action_watch')
        if sub_status == True:
            # Subscription logic, will need to be expanded to allow granular selection
            subscribe = SolutionSubscriber(user=g.user.id)
            sol.subscribe(subscribe)
        elif sub_status == False:
            sol.unsubscribe(g.user)

        vote_status = data.pop('vote_status', None)
        if vote_status:
            assert sol.can('action_vote')
        if vote_status is not None:
            sol.set_vote(vote_status)

        try:
            sol.save()
        except mongoengine.errors.ValidationError as e:
            return jsonify(success=False, validation_errors=e.to_dict())

        # return a true value to the user
        return_val.update({'success': True})
        return jsonify(return_val)

# Issue getter/setter
# =============================================================================
class IssueAPI(BaseResource):
    model = Issue

    @classmethod
    def get_issue(cls, data):
        idval = data.pop('id', None)
        if idval:
            return Issue.objects.get(id=idval)
        else:
            project = IssueAPI.get_parent_project(data, minimal=True)
            return Issue.objects.get(url_key=data['url_key'], project=project)

    @classmethod
    def get_parent_project(cls, data, **kwargs):
        proj_data = {'url_key': data.pop('purl_key', None),
                    'id': data.pop('pid', None),
                    'username': data.pop('username', None)}
        try:
            return ProjectAPI.get_project(proj_data, **kwargs)
        except Project.DoesNotExist:
            # re-raise the error in a manner that will get caught and returned
            # as a 404 error
            raise cls.model.DoesNotExist

    @catch_create
    def post(self):
        data = request.json
        project = IssueAPI.get_parent_project(data, minimal=True)
        # ensure that the user was allowed to insert that issue
        assert project.can('action_add_issue')

        issue = Issue()
        issue.title = data.get('title')
        issue.create_key()
        issue.desc = data.get('description')
        issue.project = project
        issue.creator = g.user.get()

        issue.save()

        return {'success': True, 'url_key': issue.url_key}

    @catch_common
    def get(self):
        data = request.dict_args()
        join_prof = data.get('join_prof', 'standard_join')

        issue = IssueAPI.get_issue(data)

        # not currently handled elegantly, here's a manual workaround
        if join_prof == 'solution_join':
            solutions = issue.solutions()
            solution_join_prof = data.pop('solution_join_prof', 'standard_join')
            for sol in solutions:
                assert sol.can('view_brief_join')
            return {'solutions': get_joined(solutions, solution_join_prof)}

        return get_joined(issue, join_prof=join_prof)


    @catch_common
    def put(self):
        data = request.json
        return_val = {}

        issue = IssueAPI.get_issue(data)

        self.update_model(data, issue)

        sub_status = data.pop('subscribed', None)
        if sub_status:
            assert issue.can('action_watch')
        if sub_status == True:
            # Subscription logic, will need to be expanded to allow granular selection
            subscribe = IssueSubscriber(user=g.user.id)
            issue.subscribe(subscribe)
        elif sub_status == False:
            issue.unsubscribe(g.user)

        vote_status = data.pop('vote_status', None)
        if vote_status:
            assert issue.can('action_vote')
        if vote_status is not None:
            issue.set_vote(vote_status)

        status = data.pop('status', None)
        if status:
            issue.set_status(status)

        try:
            issue.save()
        except mongoengine.errors.ValidationError as e:
            return jsonify(success=False, validation_errors=e.to_dict())

        # return a true value to the user
        return_val.update({'success': True})
        return jsonify(return_val)


api_restful.add_resource(ProjectAPI, '/api/project')
api_restful.add_resource(IssueAPI, '/api/issue')
api_restful.add_resource(SolutionAPI, '/api/solution')

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
