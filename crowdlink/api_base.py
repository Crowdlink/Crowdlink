from flask.views import MethodView
from flask.ext.sqlalchemy import BaseQuery
from flask.ext.login import current_user
from flask import abort, request, jsonify, current_app

from . import db

import sqlalchemy
import stripe
import valideer
import json


class SyntaxError(Exception):
    pass


OPERATORS = {
    # Operators which accept a single argument.
    'is_null': lambda f: f == None,
    'is_not_null': lambda f: f != None,
    # TODO what are these?
    'desc': lambda f: f.desc,
    'asc': lambda f: f.asc,
    # Operators which accept two arguments.
    '==': lambda f, a: f == a,
    'eq': lambda f, a: f == a,
    'equals': lambda f, a: f == a,
    'equal_to': lambda f, a: f == a,
    '!=': lambda f, a: f != a,
    'ne': lambda f, a: f != a,
    'neq': lambda f, a: f != a,
    'not_equal_to': lambda f, a: f != a,
    'does_not_equal': lambda f, a: f != a,
    '>': lambda f, a: f > a,
    'gt': lambda f, a: f > a,
    '<': lambda f, a: f < a,
    'lt': lambda f, a: f < a,
    '>=': lambda f, a: f >= a,
    'ge': lambda f, a: f >= a,
    'gte': lambda f, a: f >= a,
    'geq': lambda f, a: f >= a,
    '<=': lambda f, a: f <= a,
    'le': lambda f, a: f <= a,
    'lte': lambda f, a: f <= a,
    'leq': lambda f, a: f <= a,
    'ilike': lambda f, a: f.ilike(a),
    'like': lambda f, a: f.like(a),
    'in': lambda f, a: f.in_(a),
    'not_in': lambda f, a: ~f.in_(a),
}


class API(MethodView):
    max_pg_size = 100
    pkey_val = 'id'
    create_method = 'create'

    @property
    def pkey(self):
        try:
            return getattr(self.model, self.pkey_val)
        except AttributeError:
            raise AttributeError(
                'Invalid primary key defined for model {}'
                .format(self.model.__class__.__name__))

    def dispatch_request(self, *args, **kwargs):
        meth = getattr(self, request.method.lower(), None)
        # if the request method is HEAD and we don't have a handler for it
        # retry with GET
        if meth is None and request.method == 'HEAD':
            meth = getattr(self, 'get', None)
        assert meth is not None, 'Unimplemented method %r' % request.method
        try:
            return meth(*args, **kwargs)
        # Now catch all our common errors and return proper error messages for
        # them....

        # Missing required data error
        except (KeyError, AttributeError) as e:
            current_app.logger.debug("400: Incorrect Syntax", exc_info=True)
            ret = jsonify_status_code(400, 'Incorrect syntax on key ' + e.message)

        # Permission error
        except AssertionError:
            current_app.logger.debug("Permission error", exc_info=True)
            ret = jsonify_status_code(403, "You don't have permission to do that")

        # validation errors
        except valideer.base.ValidationError as e:
            current_app.logger.debug("Validation Error", exc_info=True)
            ret = jsonify_status_code(200,
                                "Validation Error",
                                validation_errors=e.to_dict())

        # typeerrors that occur when calling functions (create or action)
        # dynamically
        except TypeError as e:
            current_app.logger.debug("TypeError from API", exc_info=True)
            if 'at least' in e.message:
                ret = jsonify_status_code(
                    400, "Required arguments missing from API create method")
            elif 'argument' in e.message and 'given' in e.message:
                ret = jsonify_status_code(
                    400, "Extra arguments supplied to the API create method")
            else:
                ret = jsonify_status_code(500, "Internal Server error")

        # catch syntax errors and re-raise them
        except SyntaxError as e:
            ret = jsonify_status_code(400, e.message)

        # SQLA errors
        except sqlalchemy.orm.exc.NoResultFound:
            current_app.logger.debug("Does not exist", exc_info=True)
            ret = jsonify_status_code(404, 'Could not be found')
        except sqlalchemy.orm.exc.MultipleResultsFound:
            current_app.logger.debug("MultipleResultsFound", exc_info=True)
            ret = jsonify_status_code(
                400, 'Only one result requested, but MultipleResultsFound')
        except sqlalchemy.exc.IntegrityError as e:
            current_app.logger.debug("Attempted to insert duplicate",
                                     exc_info=True)
            ret = jsonify_status_code(
                200,
                "A duplicate value already exists in the database",
                detail=e.message)
        except sqlalchemy.exc.InvalidRequestError as e:
            current_app.logger.debug("Invalid search syntax", exc_info=True)
            ret = jsonify_status_code(
                400, "Client programming error, invalid search sytax used.",
                detail=e.message)
        except sqlalchemy.exc.SQLAlchemyError:
            current_app.logger.debug("Unkown SQLAlchemy Error", exc_info=True)
            ret = jsonify_status_code(
                500, "An unknown database operations error has occurred")
        except stripe.InvalidRequestError:
            current_app.logger.error(
                "An InvalidRequestError was recieved from stripe."
                "Original token information: "
                "{0}".format(self.params.get('token')), exc_info=True)
            ret = jsonify_status_code(500)
        except stripe.AuthenticationError:
            current_app.logger.error(
                "An AuthenticationError was recieved from stripe."
                "Original token information: "
                "{0}".format(self.params.get('token')), exc_info=True)
            ret = jsonify_status_code(500)
        except stripe.APIConnectionError:
            current_app.logger.warn(
                "An APIConnectionError was recieved from stripe."
                "Original token information: "
                "{0}".format(self.params.get('token')), exc_info=True)
            ret = jsonify_status_code(500)
        except stripe.StripeError:
            current_app.logger.warn(
                "An StripeError occurred in stripe API."
                "Original token information: "
                "{0}".format(self.params.get('token')), exc_info=True)
            ret = jsonify_status_code(500)

        current_app.logger.debug(self.params)
        return ret

    def get_obj(self):
        pkey = self.params.pop(self.pkey_val, None)
        if pkey:  # if a int primary key is passed
            return self.model.query.filter(self.pkey == pkey).one()
        return False

    def get(self):
        """ Retrieve an object from the database """
        self.params = request.dict_args
        join = self.params.pop('join_prof', 'standard_join')
        obj = self.get_obj()
        if obj:  # if a int primary key is passed
            assert obj.can('view_' + join)
            return jsonify(success=True, objects=[get_joined(obj, join)])
        else:
            query = self.search()
            one = self.params.pop('__one', None)
            if one:
                query = [query.one()]
            else:
                query = self.paginate(query=query)
            for obj in query:
                assert obj.can('view_' + join)
            return jsonify(success=True, objects=get_joined(query, join))

    def post(self):
        """ Create a new object """
        self.params = request.get_json(silent=True)
        if not self.params:
            abort(400)
        # check to ensure the user can create for others if requested
        username = self.params.get('username', None)
        userid = self.params.get('user_id', None)
        if userid or username:
            assert self.model.can_cls('class_create_other')
            query = self.model.query
            if userid:
                query = query.filter_by(id=userid)
            if username:
                query = query.filter_by(username=username)
            self.params['user'] = query.one()
        else:
            assert self.model.can_cls('class_create')
            self.params['user'] = current_user.get()

        # A hook to run permission checks/preprocessing on this creation that
        # are specific to the model
        self.create_hook()

        model = getattr(self.model, self.create_method)(**self.params)

        db.session.commit()
        if model:  # only return the model if we recieved it back
            return jsonify(success=True, objects=[get_joined(model)])
        else:
            return jsonify(success=True)

    def patch(self):
        """ Used to execute methods on an object """
        self.params = request.get_json(silent=True)
        if not self.params:
            abort(400)

        action = self.params.pop('action')
        kwargs = self.params.pop('args', {})
        obj = self.get_obj()
        if obj.can('action_' + action):
            ret = getattr(obj, action)(**kwargs)

        db.session.commit()

        return jsonify(success=ret)

    def create_hook(self):
        """ Does logic required for checking permissions on a create action """
        pass

    def put(self):
        """ Updates an objects values """
        self.params = request.get_json(silent=True)
        if not self.params:
            abort(400)

        obj = self.get_obj()

        # updates all fields if data is provided, checks acl
        for key, val in self.params.iteritems():
            current_app.logger.debug(
                "Updating value {} to {}".format(key, val))
            assert obj.can('edit_' + key)
            setattr(obj, key, val)

        db.session.commit()

        return jsonify(success=True)

    def delete(self):
        self.params = request.get_json(silent=True)
        if not self.params:
            abort(400)

        action = self.params.pop('action')
        obj = self.get_obj()
        if obj.can('delete' + action):
            count = obj.delete()

        return jsonify(success=(count > 0), count=count)

    def paginate(self, query=None):
        """ Sets limit and offset values on a query object based on arguments,
        and limited by class settings """
        if not query:
            query = self.model.query
        pg_size = self.params.get('pg_size')
        # don't do any pagination if we don't have a max page size and no
        # pagination is requested
        if pg_size is None and self.max_pg_size is None:
            return query
        elif pg_size is None:  # default to max_pg_size
            pg_size = self.max_pg_size
        pg_size = min(pg_size, self.max_pg_size)  # limit their option to max
        page = self.params.get('pg', 1)
        return query.offset((page - 1) * pg_size).limit(pg_size)

    def search(self, query=None):
        """ Handles arguments __filter_by, __filter, and __order_by by
        modifying the query parameters before execution """
        if not query:
            query = self.model.query

        filters = self.params.pop('__filters', None)
        try:
            if filters:
                for op in filters:
                    args = []
                    args.append(getattr(self.model, op['name']))
                    if 'val' in op:
                        args.append(op['val'])
                    if 'field' in op:
                        args.append(getattr(self.model, op['field']))
                    op = OPERATORS.get(op)(*args)
                    query = query.filter(op)
        except AttributeError:
            raise SyntaxError(
                'Filter operator "{}" accessed invalid field on '
                'model {}'.format(op, self.model.__class__.__name__))
        except KeyError:
            raise SyntaxError(
                'Filter operator "{}" was missing required arguments'
                'on model {}'.format(op, self.model.__class__.__name__))

        order_by = self.params.pop('__order_by', None)
        try:
            if order_by:
                for key in order_by:
                    if key.startswith('-'):
                        base = getattr(self.model, key[1:]).desc()
                    else:
                        base = getattr(self.model, key)
                    query = query.order_by(base)
        except AttributeError:
            raise SyntaxError(
                'Order_by operator "{}" accessed invalid field on '
                'model {}'.format(op, self.model.__class__.__name__))

        filter_by = self.params.pop('__filter_by', None)
        if filter_by:
            for key, value in json.loads(filter_by).items():
                try:
                    query = query.filter_by(**{key: value})
                except AttributeError:
                    raise SyntaxError(
                        'Filter_by key "{}" accessed invalid field on '
                        'model {}'.format(key, self.model.__class__.__name__))

        return query

def get_joined(obj, join_prof="standard_join"):
    # If it's a list, join each of the items in the list and return
    # modified list
    if isinstance(obj, BaseQuery) or isinstance(obj, list):
        lst = []
        for item in obj:
            lst.append(get_joined(item, join_prof=join_prof))
        return lst

    # split the join list into it's compoenents, obj to be removed, sub
    # object join data, and current object join values
    if isinstance(join_prof, basestring):
        join = getattr(obj, join_prof)
    else:
        join = join_prof

    remove = []
    sub_obj = []
    join_keys = []
    for key in join:
        if isinstance(key, basestring):
            if key.startswith('-'):
                remove.append(key[1:])
            else:
                join_keys.append(key)
        else:
            sub_obj.append(key)

    include_base = False
    try:
        join_keys.remove('__dont_mongo')
    except ValueError:
        include_base = True
    # run the primary object join
    join_vals = obj.jsonize(join_keys, raw=True)
    # catch our special config key
    if include_base:
        dct = obj.to_dict()
        # Remove keys from the bson that the join prefixes with a -
        for key in remove:
            dct.pop(key, None)
        dct.update(join_vals)
    else:
        dct = join_vals
    dct['_cls'] = obj.__class__.__name__

    # run all the subobject joins
    for conf in sub_obj:
        key = conf.get('obj')
        # allow the conf dictionary to specify a join profiel
        prof = conf.get('join_prof', "standard_join")
        subobj = getattr(obj, key)
        if subobj is not None:
            dct[key] = get_joined(subobj, join_prof=prof)
        else:
            current_app.logger.info(
                "Attempting to access attribute {} from {} resulted in {} "
                "type".format(key, type(obj), subobj))
            dct[key] = subobj
    return dct


def jsonify_status_code(
        status_code, message=None, headers=None, success=False, **kw):
    """Returns a jsonified response with the specified HTTP status code.

    If `headers` is specified, it must be a dictionary specifying headers to
    set before sending the JSONified response to the client. Headers on the
    response will be overwritten by headers specified in the `headers`
    dictionary.

    The remaining positional and keyword arguments are passed directly to the
    :func:`flask.jsonify` function which creates the response.

    """
    if message:
        kw['message'] = message
    if success is not None:  # allow removal of the success default arg by None
        kw['success'] = success
    response = jsonify(**kw)
    response.status_code = status_code
    if headers:
        for key, value in headers.iteritems():
            response.headers[key] = value
    return response
