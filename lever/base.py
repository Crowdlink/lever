from flask.views import MethodView
from flask import jsonify, current_app, request

import json
import six
import sqlalchemy
import sys
import calendar
import datetime


class LeverException(Exception):
    """ Lever handles many common errors that occur in the API and raises this
    exception with recommended return information.

    An attribute 'code' carries an http return code.

    End_user carries a dictionary of information that could be helpful to
    return to the user. End user dictionary will always include a key message,
which will mirror the message text of the exception, but can contain more
information when applicable information is available. The original stack trace
will always be passed back on the Exception.

    In addition to the end_user dictionary, there is an extra dictionary which
    will contain potentially helpful debugging information, but may be unsafe
    to return to the User.

    These exceptions can be raised by your custom PATCH methods and will be
    handled as expected. Anything raised by custom methods that isn't a
    KeyError, AttributeError, or child of LeverException will cause a 500.  """
    code = 500

    def __init__(self, message, code=None, end_user=None, extra=None):
        Exception.__init__(self, message)
        if code is not None:
            self.code = code
        self.message = message
        if end_user is None:
            self.end_user = {}
        else:
            self.end_user = end_user
        if extra is None:
            self.extra = {}
        else:
            self.extra = extra
        self.end_user.update({'message': message})


class LeverSyntaxError(LeverException):
    code = 400


class LeverNotFound(LeverException):
    code = 404
    pass


class LeverServerError(LeverException):
    code = 500


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
    params = {}
    session = None
    current_user = None

    @property
    def pkey(self):
        try:
            return getattr(self.model, self.pkey_val)
        except AttributeError:
            raise AttributeError(
                'Invalid primary key defined for model {0}'
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
        except Exception:
            # capture the info
            info = sys.exc_info()

        extra = {'original_exc': str(info[1]),
                 'original_exc_type': str(info[0]),
                 'params': self.params}
        end_user = {'success': False}
        code = None

        try:
            # reraise to handle differnet exceptions differently
            raise info[1]
        # Common API errors
        except KeyError as e:
            msg = 'Incorrect syntax or missing key ' + str(e)
            code = 400
            extra = {'key': str(e)}
        except AttributeError:
            msg = 'Incorrect syntax or missing key'
            code = 400
        except AssertionError:
            msg = "You don't have permission to do that"
            code = 403
        except LeverException as e:
            # add in the default params, but let the manually raised exception
            # take precedence
            end_user.update(e.end_user)
            extra.update(e.extra)
            e.extra = extra
            e.end_user = end_user
            raise e

        # SQLAlchemy exceptions
        except sqlalchemy.orm.exc.NoResultFound:
            msg = 'Object could not be found'
            code = 404
        except sqlalchemy.orm.exc.MultipleResultsFound:
            msg = 'Only one result requested, but MultipleResultsFound'
            code = 400
        except sqlalchemy.exc.IntegrityError:
            msg = "A duplicate value already exists in the database"
            code = 409
        except sqlalchemy.exc.InvalidRequestError:
            msg = "Client programming error, likely invalid search sytax used."
            code = 400
        except sqlalchemy.exc.DataError:
            msg = "ORM returned invalid data for an argument"
            code = 400
        except sqlalchemy.exc.SQLAlchemyError:
            msg = "An unknown database operations error has occurred"
            code = 402
        except:
            raise

        # get our exception info and try to extract extra information out of it
        exc = LeverException(msg, code=code, extra=extra, end_user=end_user)
        six.reraise(LeverException, exc, tb=info[2])

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
        self.params = dict((one, two) for one, two in six.iteritems(request.args))
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
            raise LeverSyntaxError("To create, values must be specified")
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
            self.params['user'] = self.current_user.get()
            self.create_hook()
            assert self.can_cls('class_create'), "Cant create that object"

        try:
            model = getattr(self.model, self.create_method)(**self.params)
        except TypeError as e:
            if 'argument' in str(e):
                msg = "Wrong number of arguments supplied for create."
                six.reraise(LeverSyntaxError, msg, tb=sys.exc_info()[2])
            else:
                raise

        self.session.commit()
        if model:  # only return the model if we recieved it back
            return jsonify(success=True, objects=[get_joined(model)])
        else:
            return jsonify(success=True)

    def patch(self):
        """ Used to execute methods on an object """
        self.params = request.get_json(silent=True)
        if not self.params:
            raise LeverSyntaxError("To run an action, values must be specified")

        action = self.params.pop('__action')
        cls = self.params.pop('__cls', None)
        if cls is None:
            obj = self.get_obj()
            if not obj:
                raise LeverNotFound("Could not find any object to perform an action on")
            assert obj.can('action_' + action), "Cant perform action " + action
        else:
            assert self.can_cls('action_' + action), "Can't perform cls action " + action
            obj = self.model

        retval = {}
        try:
            ret = getattr(obj, action)(**self.params)
        except TypeError as e:
            if 'argument' in str(e):
                msg = ("Wrong number of arguments supplied for action {0}."
                       .format(action))
                six.reraise(LeverSyntaxError, msg, tb=sys.exc_info()[2])
            else:
                raise

        if ret is None or ret is True:
            retval['success'] = True
        elif ret is False:
            retval['success'] = False
        else:
            retval['success'] = True
            retval.update(ret)

        self.session.commit()

        try:
            return jsonify(**retval)
        except (LeverException, KeyError, AttributeError):
            raise
        except Exception as e:
            if 'not JSON serializable' in str(e):
                raise LeverServerError(
                    "Response was not JSON serializable, patch method returned"
                    " invalid data.",
                    extra={'retval': str(retval)},
                    end_user={'method': action})

    def create_hook(self):
        """ Does logic required for checking permissions on a create action """
        pass

    def put(self):
        """ Updates an objects values """
        self.params = request.get_json(silent=True)
        if not self.params:
            raise LeverSyntaxError("To update, values must be specified")
        obj = self.get_obj()
        if not obj:
            raise LeverNotFound("Could not find any object to update")

        # updates all fields if data is provided, checks acl
        for key, val in six.iteritems(self.params):
            current_app.logger.debug(
                "Updating value for '{0}' to '{1}'".format(key, val))
            assert obj.can('edit_' + key), "Can't edit key {0} on type {1}"\
                .format(key, self.model.__name__)
            setattr(obj, key, val)

        self.session.commit()

        return jsonify(success=True)

    def delete(self):
        self.params = request.get_json(silent=True)
        if not self.params:
            raise LeverSyntaxError("To delete, values must be specified")

        obj = self.get_obj()
        if not obj:
            raise LeverNotFound("Could not find any object to delete")
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
                if isinstance(filters, six.string_types):
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
                        raise LeverSyntaxError("Invalid operator specified in filter arguments")
                    func = operator(*args)
                    query = query.filter(func)
        except AttributeError:
            current_app.logger.debug("Attribute filter error", exc_info=True)
            raise LeverSyntaxError(
                'Filter operator "{0}" accessed invalid field'
                .format(op))
        except KeyError:
            current_app.logger.debug("Key filter error", exc_info=True)
            raise LeverSyntaxError(
                'Filter operator "{0}" was missing required arguments'
                .format(op))
        except TypeError:
            current_app.logger.debug("Argument count error", exc_info=True)
            raise LeverSyntaxError(
                'Incorrect argument count for requested filter operation'
                .format(op))

        order_by = self.params.pop('__order_by', None)
        try:
            if order_by:
                # it's a json encoded parameter to get
                if isinstance(order_by, six.string_types):
                    order_by = safe_json(order_by)
                for key in order_by:
                    if key.startswith('-'):
                        base = getattr(self.model, key[1:]).desc()
                    else:
                        base = getattr(self.model, key)
                    query = query.order_by(base)
        except AttributeError:
            raise LeverSyntaxError(
                'Order_by operator "{0}" accessed invalid field'
                .format(key))

        filter_by = self.params.pop('__filter_by', None)
        if filter_by:
            # it's a json encoded parameter to get
            if isinstance(filter_by, six.string_types):
                filter_by = safe_json(filter_by)
            for key, value in six.iteritems(filter_by):
                try:
                    query = query.filter_by(**{key: value})
                except sqlalchemy.exc.InvalidRequestError:
                    raise LeverSyntaxError(
                        'Filter_by key "{0}" accessed invalid field'
                        .format(key))

        return query

    @classmethod
    def register(cls, mod, url):
        """ Registers the API to a blueprint or application """
        symfunc = cls.as_view(cls.__name__)
        mod.add_url_rule(url,
                         view_func=symfunc,
                         methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])


def get_joined(obj, join_prof="standard_join"):
    # If it's a list, join each of the items in the list and return
    # modified list
    if isinstance(obj, (sqlalchemy.orm.Query,
                        sqlalchemy.orm.collections.InstrumentedList,
                        list)):
        lst = []
        for item in obj:
            lst.append(get_joined(item, join_prof=join_prof))
        return lst

    # split the join list into it's compoenents, obj to be removed, sub
    # object join data, and current object join values
    if isinstance(join_prof, six.string_types):
        join = getattr(obj, join_prof)
    else:
        join = join_prof

    remove = []
    sub_obj = []
    join_keys = []
    for key in join:
        if isinstance(key, six.string_types):
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
    join_vals = jsonize(obj, join_keys, raw=True)
    # catch our special config key
    if include_base:
        # first we get the names of all the columns on your model
        columns = [c.key for c in sqlalchemy.orm.class_mapper(obj.__class__).columns]
        # then we return their values in a dict
        dct = dict((c, getattr(obj, c)) for c in columns)
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
        raise LeverSyntaxError(
            "Error decoding JSON parameters. Original exception was {}"
            .format(e))


def jsonize(obj, args, raw=False):
    """ Used to join attributes or functions to an objects json
    representation.  For passing back object state via the api """
    dct = {}
    for key in args:
        attr = getattr(obj, key)
        # if it's a callable function call it, then do the parsing below
        if callable(attr):
            try:
                attr = attr()
            except TypeError:
                current_app.logger.warn(
                    "{0} callable requires argument on obj {1}"
                    .format(str(attr), obj.__class__.__name__))
                continue
        # convert datetime to seconds since epoch, much more universal
        if isinstance(attr, datetime.datetime):
            attr = calendar.timegm(attr.utctimetuple()) * 1000
        # don't convert these common types to strings
        elif (isinstance(attr, bool) or
              isinstance(attr, int) or
              isinstance(attr, dict) or
              attr is None or
              isinstance(attr, list)):
            pass
        # convert set to a dictionary for easy conditionals
        elif isinstance(attr, set):
            attr = dict((x, True) for x in attr)
        else:  # if we don't know what it is, stringify it
            attr = str(attr)

        dct[key] = attr

    if raw:
        return dct
    else:
        return json.dumps(dct)
