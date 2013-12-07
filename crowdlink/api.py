from flask import Blueprint, request, g, current_app, jsonify, abort, Response
from flask.ext.login import login_required, logout_user, current_user, login_user
from flask.ext.restful import Resource

from . import root, lm
from .models import (User, Project, Issue, Transaction, Solution, Email)
from .lib import get_json_joined, get_joined, redirect_angular

import json
import valideer
import bson
import sqlalchemy
import decorator
import datetime
import os
import sys
import stripe
import valideer as V


api = Blueprint('api_bp', __name__)


# Common Fixtures
# =============================================================================
def catch_common(func):
    # tries to catch common exceptions and return properly
    def decorated(*args, **kwargs):
        # get the auth dictionary
        try:
            return func(*args, **kwargs)

        # Missing required data error
        except KeyError as e:
            current_app.logger.debug("400: Incorrect Syntax", exc_info=True)
            ret = {'success': False, 'message': 'Incorrect syntax on key ' + e.message}, 400

        # Permission error
        except AssertionError:
            current_app.logger.debug("Permission error", exc_info=True)
            ret = {'success': False, 'message': 'You don\'t have permission to do that'}, 403

        # validation errors
        except valideer.base.ValidationError as e:
            current_app.logger.debug("Validation Error", exc_info=True)
            ret = {'success': False, 'validation_errors': e.to_dict()}, 200

        # SQLA errors
        except sqlalchemy.orm.exc.NoResultFound:
            current_app.logger.debug("Does not exist", exc_info=True)
            ret = {'error': 'Could not be found'}, 404
        except sqlalchemy.exc.IntegrityError as e:
            current_app.logger.debug("Attempted to insert duplicate", exc_info=True)
            ret = {'success': False, 'message': "A duplicate value already exists in the database", 'detail': e.message}, 200
        except sqlalchemy.exc:
            current_app.logger.debug("Unkown SQLAlchemy Error", exc_info=True)
            ret = {'success': False, 'message': "An unknown database operations error has occurred"}, 200

        # a bit of a hack to make it work with flask-restful and regular views
        r = jsonify(ret[0])
        r.status_code = ret[1]
        return r

    return decorated


@decorator.decorator
def catch_stripe(func, *args, **kwargs):
    # catches the more generic stripe errors and logs them
    js = request.json_dict
    try:
        return func(*args, **kwargs)

    except stripe.InvalidRequestError as e:
        current_app.logger.error(
            "An InvalidRequestError was recieved from stripe."
            "Original token information: {0}".format(js.get('token')), exc_info=True)
        return jsonify(success=False)
    except stripe.AuthenticationError as e:
        current_app.logger.error(
            "An AuthenticationError was recieved from stripe."
            "Original token information: {0}".format(js.get('token')), exc_info=True)
        return jsonify(success=False)
    except stripe.APIConnectionError as e:
        current_app.logger.warn(
            "An APIConnectionError was recieved from stripe."
            "Original token information: {0}".format(js.get('token')), exc_info=True)
        return jsonify(success=False)
    except stripe.StripeError as e:
        current_app.logger.warn(
            "An StripeError occurred in stripe API."
            "Original token information: {0}".format(js.get('token')), exc_info=True)
        return jsonify(success=False)

    return jsonify(success=False)


class BaseResource(Resource):
    def update_model(self, data, model):
        # updates all fields if data is provided, checks acl
        for field in sqlalchemy.orm.class_mapper(model.__class__).columns:
            field = str(field).split('.')[1]
            new_val = data.pop(field, None)
            if new_val:
                current_app.logger.debug("Updating value {} to {}".format(field, new_val))
                assert model.can('edit_' + field)
                setattr(model, field, new_val)


# Check functions for forms
# =============================================================================
@decorator.decorator
def check_catch(func, *args, **kwargs):
    """ Catches exceptions and None return types """
    try:
        ret = func(*args, **kwargs)
    except KeyError:
        return incorrect_syntax()
    except sqlalchemy.orm.exc.NoResultFound:
        return jsonify(taken=False)
    else:
        if ret is None:
            return jsonify(taken=True)

    return jsonify(), 500

@api.route("/user/check", methods=['POST'])
@check_catch
def check_user():
    """ Check if a specific username is taken """
    js = request.json_dict
    user = User.query.filter_by(username=js['value']).one()


@api.route("/purl_key/check", methods=['POST'])
@login_required
@check_catch
def check_ptitle():
    """ Check if a specific project url_key is taken """
    js = request.json_dict
    project = Project.query.filter_by(maintainer_username=current_user.username,
                                      url_key=js['value']).one()


@api.route("/email/check", methods=['POST'])
@check_catch
def check_email():
    """ Check if a specific email address is taken """
    js = request.json_dict
    user = Email.query.filter_by(address=js['value']).one()


# Project getter/setter
# =============================================================================
class ProjectAPI(BaseResource):
    model = Project

    @classmethod
    def get_project(cls, data, minimal=False):
        proj_id = data.pop('id', None)

        # Mild optimization for objects that need to get the project from
        # url_key and username
        """
        if minimal:
            base = Project.query.only('id', 'url_key')
        else:
            base = Project.objects
        """

        if proj_id:
            return Project.query.filter_by(id=proj_id).one()


        return Project.query.filter_by(url_key=data['url_key'],
                                       maintainer_username=data['username']).one()

    @catch_common
    def get(self):
        data = request.dict_args()
        join_prof = data.pop('join_prof', None)
        project = self.get_project(data)
        retval = {}

        # not currently handled elegantly, here's a manual workaround
        issue_join_prof = data.pop('issue_join_prof', None)
        if issue_join_prof:
            issues = project.issues()
            for issue in issues:
                assert issue.can('view_' + issue_join_prof)
            retval['issues'] = get_joined(issues, issue_join_prof)

        if join_prof:
            assert project.can('view_' + join_prof)
            retval.update(get_joined(project, join_prof=join_prof))

        retval['success'] = True
        return retval

    @catch_common
    def put(self):
        data = request.json_dict
        project = self.get_project(data)
        return_val = {}

        self.update_model(data, project)

        sub_status = data.pop('subscribed', None)
        if sub_status:
            assert project.can('action_watch')
        if sub_status == True:
            project.subscribe()
        elif sub_status == False:
            project.unsubscribe()

        vote_status = data.pop('vote_status', None)
        if vote_status:
            assert project.can('action_vote')
        if vote_status is not None:
            project.set_vote(vote_status)

        project.safe_save()

        # return a true value to the user
        return_val['success'] = True
        return return_val

    @catch_common
    def post(self):
        data = request.json_dict
        project = Project()
        project.username = g.user.username
        project.maintainer = g.user.get()
        project.url_key = data.get('url_key')
        project.name = data.get('name')
        project.website = data.get('website')
        project.description = data.get('website')

        project.safe_save()

        return {'success': True}


# Solution getter/setter
# =============================================================================
class SolutionAPI(BaseResource):
    model = Solution

    @classmethod
    def get_solution(cls, data):
        id = data.pop('id')
        return Solution.query.filter_by(id=id).one()

    @catch_common
    def post(self):
        data = request.json_dict
        issue = IssueAPI.get_issue(data)
        # ensure that the user was allowed to insert that issue
        assert issue.can('action_add_solution')

        sol = Solution()
        sol.title = data.get('title')
        sol.create_key()
        sol.desc = data.get('description')
        sol.issue = issue
        sol.project = issue.project
        sol.creator = g.user.get()

        sol.safe_save()

        return {'success': True, 'url_key': sol.url_key, 'id': str(sol.id)}

    @catch_common
    def get(self):
        data = request.dict_args()
        join_prof = data.get('join_prof', 'standard_join')

        sol = SolutionAPI.get_solution(data)
        return get_joined(sol, join_prof=join_prof)


    @catch_common
    def put(self):
        data = request.json_dict
        return_val = {}

        sol = SolutionAPI.get_solution(data)

        # updating of regular attributes
        self.update_model(data, sol)

        sub_status = data.pop('subscribed', None)
        if sub_status:
            assert sol.can('action_watch')
        if sub_status == True:
            sol.subscribe()
        elif sub_status == False:
            sol.unsubscribe()

        vote_status = data.pop('vote_status', None)
        if vote_status:
            assert sol.can('action_vote')
        if vote_status is not None:
            sol.set_vote(vote_status)

        sol.safe_save()

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
            return Issue.query.filter_by(id=idval).one()
        else:
            project = IssueAPI.get_parent_project(data, minimal=True)
            return Issue.query.filter_by(url_key=data['url_key'], project=project).one()

    @classmethod
    def get_parent_project(cls, data, **kwargs):
        proj_data = {'url_key': data.pop('purl_key', None),
                    'id': data.pop('pid', None),
                    'username': data.pop('username', None)}
        return ProjectAPI.get_project(proj_data, **kwargs)

    @catch_common
    def post(self):
        data = request.json_dict
        project = IssueAPI.get_parent_project(data, minimal=True)
        # ensure that the user was allowed to insert that issue
        assert project.can('action_add_issue')

        issue = Issue()
        issue.title = data.get('title')
        issue.create_key()
        issue.desc = data.get('description')
        issue.project = project
        issue.creator = g.user.get()

        issue.safe_save()

        return {'success': True, 'url_key': issue.url_key, 'id': str(issue.id)}

    @catch_common
    def get(self):
        data = request.dict_args()

        retval = {}
        issue = IssueAPI.get_issue(data)

        # not currently handled elegantly, here's a manual workaround
        sol_join_prof = data.pop('solution_join_prof', None)
        if sol_join_prof:
            solutions = issue.solutions()
            for sol in solutions:
                assert sol.can('view_' + sol_join_prof)
            retval['solutions'] = get_joined(solutions, sol_join_prof)


        join_prof = data.get('join_prof', None)
        if join_prof:
            retval.update(get_joined(issue, join_prof=join_prof))

        return retval


    @catch_common
    def put(self):
        data = request.json_dict
        return_val = {}

        issue = IssueAPI.get_issue(data)

        self.update_model(data, issue)

        sub_status = data.pop('subscribed', None)
        if sub_status:
            assert issue.can('action_watch')
        if sub_status == True:
            # Subscription logic, will need to be expanded to allow granular selection
            #subscribe = IssueSubscriber(user=g.user.id)
            issue.subscribe()
        elif sub_status == False:
            issue.unsubscribe()

        vote_status = data.pop('vote_status', None)
        if vote_status:
            assert issue.can('action_vote')
        if vote_status is not None:
            issue.set_vote(vote_status)

        status = data.pop('status', None)
        if status:
            issue.set_status(status)

        issue.safe_save()

        # return a true value to the user
        return_val.update({'success': True})
        return jsonify(return_val)


# User getter/setter
# =============================================================================
@api.route("/user", methods=['GET'])
def get_user():
    js = request.args
    join_prof = request.args.get('join_prof', 'standard_join')

    # try to access the issue with identifying information
    try:
        username = js.get('username', None)
        userid = js.get('id', None)

        if username:
            user = User.query.filter_by(username=username).one()
        elif userid:
            user = User.query.filter_by(id=userid).one()
        else:
            return incorrect_syntax()
        ret = {'success': True}
        ret.update(get_joined(user, join_prof=join_prof))
        return jsonify(ret)
    except sqlalchemy.orm.exc.NoResultFound:
        pass
    return resource_not_found()


@api.route("/user", methods=['POST'])
@login_required
def update_user():
    js = request.json_dict

    # try to access the issue with identifying information
    try:
        username = js.pop('username')
        user = User.query.filter_by(username=username).one()
    except KeyError:
        return incorrect_syntax()
    except sqlalchemy.orm.exc.NoResultFound:
        return resource_not_found()

    status = js.pop('subscribed', None)
    if status == True:
        # Subscription logic, will need to be expanded to allow granular selection
        #subscribe = UserSubscriber(user=g.user.id)
        user.subscribe(subscribe)
    elif status == False:
        user.unsubscribe(g.user)

    try:
        user.safe_save()
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
    js = request.json_dict

    try:
        user = User.query.filter_by(username=js['username']).one()
        if user.check_password(js['password']):
            login_user(user)
    except (KeyError, sqlalchemy.orm.exc.NoResultFound):
        pass
    else:
        return jsonify(success=True, user=get_joined(user))

    return jsonify(success=False, message="Invalid credentials")



# Finance related function
# =============================================================================
@api.route("/transaction", methods=['GET'])
@login_required
def transaction():
    js = request.args

    # try to access the issue with identifying information
    try:
        trans = Transaction.query.filter_by(user_id=current_user.id)
        return get_json_joined(trans)
    except KeyError as e:
        return incorrect_syntax()
    except sqlalchemy.orm.exc.NoResultFound:
        return resource_not_found()



@api.route("/charge", methods=['POST'])
@catch_stripe
@catch_common
@login_required
def run_charge():
    """ Runs a charge for a User and generates a new transaction in the process
    """
    js = request.json_dict

    amount = js['amount']
    card = js['token']['id']
    livemode = js['token']['livemode']
    if amount > 100000 or amount < 500:
        raise KeyError('amount')

    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    try:
        retval = stripe.Charge.create(
            amount=amount,
            currency="usd",
            card=card)
    except stripe.CardError as e:
        body = e.json_body
        err = body['error']

        current_app.logger.info(err, exc_info=True)
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
            user=current_user,
            _status=status,
            last_four=retval['card']['last4']
        )

        return jsonify(success=True, transaction=trans.to_dict())

def incorrect_syntax(message='Incorrect syntax', **kwargs):
    return jsonify(message=message, **kwargs), 400

def resource_not_found(message='Asset does not exist', **kwargs):
    return jsonify(message=message, **kwargs), 404
