from flask import Blueprint, request, g, current_app, jsonify, abort
from flask.ext.login import login_required, logout_user, current_user, login_user

from . import root, lm, app
from .models import User, Project, Issue, UserSubscriber, ProjectSubscriber, IssueSubscriber, Transaction
from .lib import get_json_joined, redirect_angular

import json
import bson
import mongoengine
import datetime
import os
import sys
import stripe

api = Blueprint('api', __name__)

@api.route("/vote", methods=['POST'])
@login_required
def vote_api():
    js = request.json
    try:
        issue = Issue.objects.get(
            project=js['project'],
            url_key=js['url_key'])
        vote_status = js['vote_status']
    except KeyError:
        return incorrect_syntax()
    except Issue.DoesNotExist:
        return resource_not_found()

    if vote_status and not issue.set_vote(g.user):
        if issue.vote_status:
            return jsonify(success=False, code='already_voted', disp="Already voted!")
        else:
            return jsonify(success=False)
    elif not vote_status and not issue.set_unvote(g.user):
        if not issue.vote_status:
            return jsonify(success=False, code='already_voted', disp="Haven't voted yet")
        else:
            return jsonify(success=False)

    return jsonify(success=True)


@api.route("/project", methods=['GET'])
def get_project():
    username = request.args.get('username', '')
    url_key = request.args.get('url_key', '')
    join_prof = request.args.get('join_prof', 'standard_join')

    # try to access the issue with identifying information
    try:
        project = Project.objects(username=username, url_key=url_key)
        return get_json_joined(project, join_prof=join_prof)
    except KeyError as e:
        return incorrect_syntax()
    except Issue.DoesNotExist:
        return resource_not_found()


@api.route("/user", methods=['GET'])
@login_required
def get_user():
    js = request.args

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
        return get_json_joined(user)
    except User.DoesNotExist:
        pass
    return resource_not_found()


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

    return jsonify(success=True, user=get_json_joined(user))

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

    open_status = js.pop('open', None)
    if open_status == True:
        issue.set_open()
    elif open_status == False:
        issue.set_close()

    try:
        issue.save()
    except mongoengine.errors.ValidationError as e:
        return jsonify(success=False, validation_errors=e.to_dict())

    # return a true value to the user
    return_val.update({'success': True})
    return jsonify(return_val)


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
