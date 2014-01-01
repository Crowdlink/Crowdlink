from flask.views import MethodView
from flask.ext.sqlalchemy import BaseQuery
from flask.ext.login import current_user
from flask import jsonify, current_app, request

from . import db

import json
import sys


class APISyntaxError(Exception):
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


class AnonymousUser(object):
    id = -100
    gh_token = None
    tw_token = None
    go_token = None

    def is_anonymous(self):
        return True

    def global_roles(self):
        return ['anonymous']

    def is_authenticated(self):
        return False

    def get(self):
        return self


class API(MethodView):
    max_pg_size = 100
    pkey_val = 'id'
    create_method = 'create'
    params = ''
    session = db.session

    @property
    def pkey(self):
        try:
            return getattr(self.model, self.pkey_val)
        except AttributeError:
            raise AttributeError(
                'Invalid primary key defined for model {}'
                .format(self.model.__class__.__name__))

    def dispatch_request(self, *args, **kwargs):
        method_name = request.method.lower()
        meth = getattr(self, method_name, None)
        # if the request method is HEAD and we don't have a handler for it
        # retry with GET
        if meth is None and request.method == 'HEAD':
            meth = getattr(self, 'get', None)
            method_name = 'get'
        assert meth is not None, 'Unimplemented method %r' % request.method

        return meth(*args, **kwargs)

    def get_obj(self):
        pkey = self.params.pop(self.pkey_val, None)
        if pkey:  # if a int primary key is passed
            return self.model.query.filter(self.pkey == pkey).one()
        return False

    def can_cls(self, action):
        """ This function should parse the current parameters to gain parent
        information for properly running can_cls on the model this API wraps
        """
        return self.model.can_cls(action)

    def get(self):
        """ Retrieve an object from the database """
        # convert args to a real dictionary that can be popped
        self.params = {one: two for one, two in request.args.iteritems()}
        join = self.params.pop('join_prof', 'standard_join')
        obj = self.get_obj()
        if obj:  # if a int primary key is passed
            assert obj.can('view_' + join), "Can't view that object with join " + join
            return jsonify(success=True, objects=[get_joined(obj, join)])
        else:
            query = self.search()
            one = self.params.pop('__one', None)
            if one:
                query = [query.one()]
            else:
                query = self.paginate(query=query)
            for obj in query:
                assert obj.can('view_' + join), "Can't view that object with join " + join
            return jsonify(success=True, objects=get_joined(query, join))

    def post(self):
        """ Create a new object """
        self.params = request.get_json(silent=True)
        if not self.params:
            return jsonify_status_code(400, "To create, values must be specified")
        # check to ensure the user can create for others if requested
        username = self.params.pop('__username', None)
        userid = self.params.pop('__user_id', None)
        if userid or username:
            query = self.model.query
            if userid:
                query = query.filter_by(id=userid)
            if username:
                query = query.filter_by(username=username)
            self.params['user'] = query.one()
            self.create_hook()
            assert self.can_cls('class_create_other', params=self.params), "Cant create for other users"
        else:
            self.params['user'] = current_user.get()
            self.create_hook()
            assert self.can_cls('class_create'), "Cant create that object"

        model = getattr(self.model, self.create_method)(**self.params)

        self.session.commit()
        if model:  # only return the model if we recieved it back
            return jsonify(success=True, objects=[get_joined(model)])
        else:
            return jsonify(success=True)

    def patch(self):
        """ Used to execute methods on an object """
        self.params = request.get_json(silent=True)
        if not self.params:
            return jsonify_status_code(400, "To run an action, values must be specified")

        action = self.params.pop('__action')
        cls = self.params.pop('__cls', None)
        if cls is None:
            obj = self.get_obj()
            if not obj:
                raise APISyntaxError("Could not find any object to perform an action on")
            assert obj.can('action_' + action), "Cant perform action " + action
        else:
            assert self.can_cls('action_' + action), "Can't perform cls action " + action
            obj = self.model

        retval = {}
        try:
            ret = getattr(obj, action)(**self.params)
            if ret is None or ret is True:
                retval['success'] = True
            elif ret is False:
                retval['success'] = False
            else:
                retval['success'] = True
                retval.update(ret)

        except TypeError as e:
            if 'argument' in e.message:
                current_app.logger.debug(self.params)
                raise APISyntaxError, "Wrong number of arguments supplied for action {}".format(action), sys.exc_info()[2]
            else:
                raise
        self.session.commit()

        return jsonify(**retval)

    def create_hook(self):
        """ Does logic required for checking permissions on a create action """
        pass

    def put(self):
        """ Updates an objects values """
        self.params = request.get_json(silent=True)
        if not self.params:
            return jsonify_status_code(400, "To update, values must be specified")
        obj = self.get_obj()
        if not obj:
            raise APISyntaxError("Could not find any object to update")

        # updates all fields if data is provided, checks acl
        for key, val in self.params.iteritems():
            current_app.logger.debug(
                "Updating value for '{}' to '{}'".format(key, val))
            assert obj.can('edit_' + key), "Can't edit key {} on type {}"\
                .format(key, self.model.__name__)
            setattr(obj, key, val)

        self.session.commit()

        return jsonify(success=True)

    def delete(self):
        self.params = request.get_json(silent=True)
        if not self.params:
            return jsonify_status_code(400, "To delete, values must be specified")

        obj = self.get_obj()
        if not obj:
            raise APISyntaxError("Could not find any object to delete")
        assert obj.can('delete'), "Can't delete that object"
        self.session.delete(obj)
        self.session.commit()

        return jsonify(success=True)

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
        if query is None:
            query = self.model.query

        filters = self.params.pop('__filter', None)
        try:
            if filters:
                # it's a json encoded parameter to get
                if isinstance(filters, basestring):
                    filters = safe_json(filters)
                for op in filters:
                    args = []
                    args.append(getattr(self.model, op['name']))
                    if 'val' in op:
                        args.append(op['val'])
                    if 'field' in op:
                        args.append(getattr(self.model, op['field']))
                    operator = OPERATORS.get(op['op'])
                    if operator is None:
                        raise APISyntaxError("Invalid operator specified in filter arguments")
                    func = operator(*args)
                    query = query.filter(func)
        except AttributeError:
            current_app.logger.debug("Attribute filter error", exc_info=True)
            raise APISyntaxError(
                'Filter operator "{}" accessed invalid field'
                .format(op))
        except KeyError:
            current_app.logger.debug("Key filter error", exc_info=True)
            raise APISyntaxError(
                'Filter operator "{}" was missing required arguments'
                .format(op))
        except TypeError:
            current_app.logger.debug("Argument count error", exc_info=True)
            raise APISyntaxError(
                'Incorrect argument count for requested filter operation'
                .format(op))

        order_by = self.params.pop('__order_by', None)
        try:
            if order_by:
                # it's a json encoded parameter to get
                if isinstance(order_by, basestring):
                    order_by = safe_json(order_by)
                for key in order_by:
                    if key.startswith('-'):
                        base = getattr(self.model, key[1:]).desc()
                    else:
                        base = getattr(self.model, key)
                    query = query.order_by(base)
        except AttributeError:
            raise APISyntaxError(
                'Order_by operator "{}" accessed invalid field'
                .format(key))

        filter_by = self.params.pop('__filter_by', None)
        if filter_by:
            # it's a json encoded parameter to get
            if isinstance(filter_by, basestring):
                filter_by = safe_json(filter_by)
            for key, value in filter_by.items():
                try:
                    query = query.filter_by(**{key: value})
                except AttributeError:
                    raise APISyntaxError(
                        'Filter_by key "{}" accessed invalid field'
                        .format(key))

        return query

    @classmethod
    def register(cls, mod, url):
        """ Registers the API to a blueprint or application """
        symfunc = cls.as_view(cls.__name__)
        mod.add_url_rule(url,
                         view_func=symfunc,
                         methods=['GET', 'PUT', 'PATCH', 'DELETE'])

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


def safe_json(json_string):
    try:
        return json.loads(json_string)
    except Exception as e:
        raise APISyntaxError(
            "Error decoding JSON parameters. Original exception was {}"
            .format(e.message))


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
