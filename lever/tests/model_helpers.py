"""
model_helpers
~~~~~~~~~~~~~
Provides helper functions for unit testing our unit internal API framework
Heavily borrowed from https://github.com/jfinkels/flask-restless helper
files

:copyright: 2012 Jeffrey Finkelstein <jeffrey.finkelstein@gmail.com>
:license: GNU AGPLv3+ or BSD
"""
import datetime
import sqlalchemy
import unittest

from flask import Flask, jsonify
from flask.ext.sqlalchemy import (_BoundDeclarativeMeta, SQLAlchemy,
                                  _QueryProperty)
from flask.ext.login import LoginManager, current_user, login_user
from sqlalchemy import (Column, create_engine, DateTime, Date, Float,
                        ForeignKey, Integer, Boolean, Unicode)
from sqlalchemy.ext.declarative import declarative_base

from lever import API, LeverException
from lever.mapper import BaseMapper


class FlaskTestBase(unittest.TestCase):
    """Base class for tests which use a Flask application.

    The Flask test client can be accessed at ``self.app``. The Flask
    application itself is accessible at ``self.flaskapp``.

    """

    def setUp(self):
        """Creates the Flask application and the APIManager."""
        # create the Flask application
        app = Flask(__name__)
        app.config['DEBUG'] = True
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = "dfsglkjsdfglkjsdfg"
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        del app.logger.handlers[0]
        self.flaskapp = app
        # add the login manager
        self.lm = LoginManager(self.flaskapp)
        # sqlalchemy flask
        self.db = SQLAlchemy(self.flaskapp)
        self.base = declarative_base(cls=BaseMapper,
                                     metaclass=_BoundDeclarativeMeta,
                                     metadata=self.db.MetaData(),
                                     name='Model')
        self.base.query = _QueryProperty(self.db)
        self.db.Model = self.base

        # create the test client
        self.app = app.test_client()

        # Ensure that all requests have Content-Type set to "application/json"
        # unless otherwise specified.
        for methodname in ('get', 'put', 'patch', 'post', 'delete'):
            # Create a decorator for the test client request methods that adds
            # a JSON Content-Type by default if none is specified.
            def set_content_type(func):
                def new_func(*args, **kw):
                    if 'content_type' not in kw:
                        kw['content_type'] = 'application/json'
                    return func(*args, **kw)
                return new_func
            # Decorate the original test client request method.
            old_method = getattr(self.app, methodname)
            setattr(self.app, methodname, set_content_type(old_method))


class TestModels(FlaskTestBase):
    """Base class for test cases which use a database with some basic models.

    """

    def setUp(self):
        """Creates some example models and creates the database tables.

        This class defines a whole bunch of models with various properties for
        use in testing, so look here first when writing new tests.
        """
        super(TestModels, self).setUp()

        class User(self.base):
            id = Column(Integer, primary_key=True)
            username = Column(Unicode, unique=True)
            description = Column(Unicode)
            password = Column(Unicode)
            admin = Column(Boolean, default=False)
            created_at = Column(DateTime, default=datetime.datetime.utcnow)

            standard_join = ['username', 'created_at', 'id', 'description']
            acl = {'user': set(['view_standard_join']),
                   'anonymous': set(['view_standard_join', 'action_login', 'class_create']),
                   'owner': set(['view_standard_join', 'edit_description']),
                   'admin': set(['delete'])}

            def roles(self, user=current_user):
                if self.id == user.id:
                    return ['owner']
                return []

            def global_roles(self, user=current_user):
                if self.admin:
                    return ['admin', 'user']
                return ['user']

            def login(self, password):
                if password == self.password:
                    login_user(self)
                    return True
                return False

            def is_authenticated(self):
                return True

            def is_active(self):
                return True

            def is_anonymous(self):
                return False

            def get_id(self):
                return str(self.id)

            @classmethod
            def create(cls, username, password, user=current_user):
                inst = cls(username=username,
                           password=password,
                           description='a new user!')
                self.db.session.add(inst)
                return inst

        # Setup the anonymous user to register a single role
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
        self.lm.anonymous_user = AnonymousUser

        # setup login manager stuff
        @self.lm.user_loader
        def user_loader(id):
            try:
                return User.query.filter_by(id=id).one()
            except sqlalchemy.orm.exc.NoResultFound:
                return None

        class UserAPI(API):
            model = User
            session = self.db.session
            current_user = current_user

        self.flaskapp.add_url_rule('/api/user',
                                   view_func=UserAPI.as_view('user'))
        self.User = User
        self.UserAPI = UserAPI

        # Add an error handler that returns straight LeverException
        # recommendations
        @self.flaskapp.errorhandler(LeverException)
        def handler(exc):
            self.flaskapp.logger.debug("Extra: {0}\nEnd User: {1}"
                                       .format(exc.extra, exc.end_user),
                                       exc_info=True)
            print(str(exc.end_user))
            return jsonify(**exc.end_user), exc.code

        # create all the tables required for the models
        self.db.create_all()

    def login(self, username):
        login_user(self.User.query.filter_by(username=username).one())

    def tearDown(self):
        """Drops all tables from the temporary database."""
        #self.session.remove()
        self.db.drop_all()


class TestModelsPrefilled(TestModels):
    """Base class for tests which use a database and have an
    :class:`flask_restless.APIManager` with a :class:`flask.Flask` app object.

    The test client for the :class:`flask.Flask` application is accessible to
    test functions at ``self.app`` and the :class:`flask_restless.APIManager`
    is accessible at ``self.manager``.

    The database will be prepopulated with five ``Person`` objects. The list of
    these objects can be accessed at ``self.people``.

    """

    def setUp(self):
        """Creates the database, the Flask application, and the APIManager."""
        # create the database
        super(TestModelsPrefilled, self).setUp()
        # create some people in the database for testing
        self.people = []
        for u in ['mary', 'lucy', 'katy', 'john']:
            user = self.User(username=u, password='testing')
            self.people.append(user)

        # make an admin user
        self.admin = self.User(username='admin', password='testing', admin=True)
        self.people.append(self.admin)

        self.db.session.add_all(self.people)
        self.db.session.commit()
