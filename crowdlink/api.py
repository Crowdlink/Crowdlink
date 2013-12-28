from flask import Blueprint, request, current_app, jsonify
from flask.ext.login import (login_required, logout_user, current_user,
                             login_user)

from .api_base import API, get_joined, jsonify_status_code
from .models import (User, Project, Issue, Solution, Email, Dispute, Comment,
                     Thing)
from .fin_models import Earmark, Recipient, Transfer, Charge

import valideer
import sqlalchemy
import decorator


api = Blueprint('api_bp', __name__)


# Common Fixtures
# =============================================================================
@decorator.decorator
def catch_common(func, *args, **kwargs):
    """ tries to catch common exceptions and return properly """
    # get the auth dictionary
    try:
        return func(*args, **kwargs)

    # Missing required data error
    except (KeyError, AttributeError) as e:
        current_app.logger.debug("400: Incorrect Syntax", exc_info=True)
        ret = {'success': False,
               'message': 'Incorrect syntax on key ' + e.message}, 400

    # Permission error
    except AssertionError:
        current_app.logger.debug("Permission error", exc_info=True)
        ret = {'success': False,
               'message': 'You don\'t have permission to do that'}, 403

    # validation errors
    except valideer.base.ValidationError as e:
        current_app.logger.debug("Validation Error", exc_info=True)
        ret = {'success': False, 'validation_errors': e.to_dict()}, 200

    # SQLA errors
    except (sqlalchemy.orm.exc.NoResultFound,
            sqlalchemy.orm.exc.MultipleResultsFound):
        current_app.logger.debug("Does not exist", exc_info=True)
        ret = {'error': 'Could not be found'}, 404
    except sqlalchemy.exc.IntegrityError as e:
        current_app.logger.debug("Attempted to insert duplicate",
                                 exc_info=True)
        ret = {
            'success': False,
            'message': "A duplicate value already exists in the database",
            'detail': e.message},
        200
    except (sqlalchemy.exc, sqlalchemy.orm.exc):
        current_app.logger.debug("Unkown SQLAlchemy Error", exc_info=True)
        ret = {
            'success': False,
            'message': "An unknown database operations error has occurred"},
        200

    # a bit of a hack to make it work with flask-restful and regular views
    r = jsonify(ret[0])
    r.status_code = ret[1]
    return r


# Check functions for forms
# =============================================================================
@decorator.decorator
def check_catch(func, *args, **kwargs):
    """ Catches exceptions and None return types """
    try:
        ret = func(*args, **kwargs)
    except KeyError:
        return jsonify_status_code(400, "Required arguments were missing")
    except sqlalchemy.orm.exc.NoResultFound:
        return jsonify(taken=False, success=True)
    else:
        if ret is None:
            return jsonify(taken=True, success=True)


@api.route("/user/check", methods=['POST'])
@check_catch
def check_user():
    """ Check if a specific username is taken """
    js = request.json_dict
    User.query.filter_by(username=js['value']).one()


@api.route("/purl_key/check", methods=['POST'])
@login_required
@check_catch
def check_ptitle():
    """ Check if a specific project url_key is taken """
    js = request.json_dict
    Project.query.filter_by(
        maintainer_username=current_user.username,
        url_key=js['value']).one()


@api.route("/email/check", methods=['POST'])
@check_catch
def check_email():
    """ Check if a specific email address is taken """
    js = request.json_dict
    Email.query.filter_by(address=js['value']).one()


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


class UserAPI(API):
    model = User


class EmailAPI(API):
    model = Email


class ProjectAPI(API):
    model = Project


class IssueAPI(API):
    model = Issue
    def create_hook(self):
        # do logic to pick out the parent from the database based on parent
        # keys
        purl_key = self.params.pop('project_url_key', None)
        puser = self.params.pop('project_maintainer_username', None)
        pid = self.params.pop('project_id', None)
        # try this method first, most common
        if puser and purl_key:
            project = Project.query.filter(
                Project.maintainer_username == puser,
                Project.url_key == purl_key).one()
        elif pid:
            project = Project.query.filter(Project.id == pid).one()
        else:
            raise SyntaxError(
                    "Unable to identify parent project from information given")

        self.params['project'] = project

    def can_cls(self, action):
        return self.model.can_cls(action, project=self.params['project'])


class SolutionAPI(API):
    model = Solution
    def create_hook(self):
        # do logic to pick out the parent from the database based on parent
        # keys
        purl_key = self.params.pop('project_url_key', None)
        puser = self.params.pop('project_maintainer_username', None)
        iurl_key = self.params.pop('issue_url_key', None)
        iid = self.params.pop('issue_id', None)
        # try this method first, most common
        if puser and purl_key and iurl_key:
            issue = Issue.query.filter(
                Issue.project_maintainer_username == puser,
                Issue.project_url_key == purl_key,
                Issue.url_key == iurl_key).one()
        elif iid:
            issue = Issue.query.filter(Issue.id == iid).one()
        else:
            raise SyntaxError(
                    "Unable to identify parent Issue from information given")

        self.params['issue'] = issue

    def can_cls(self, action):
        return self.model.can_cls(action, issue=self.params['issue'])


class TransferAPI(API):
    model = Transfer


class RecipientAPI(API):
    model = Recipient


class ChargeAPI(API):
    model = Charge


class EarmarkAPI(API):
    model = Earmark


class DisputeAPI(API):
    model = Dispute


class CommentAPI(API):
    model = Comment
    def create_hook(self):
        # do logic to pick out the parent from the database based on parent
        # keys
        tid = self.params.pop('thing_id', None)
        # try this method first, most common
        if tid:
            thing = Thing.query.filter(Thing.id == tid).one()
        else:
            raise SyntaxError(
                    "Unable to identify parent Thing from information given")

        self.params['thing'] = thing

    def can_cls(self, action):
        return self.model.can_cls(action, thing=self.params['thing'])
