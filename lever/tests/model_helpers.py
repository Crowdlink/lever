import datetime
import sqlalchemy
import unittest
import json

from flask import Flask, jsonify
from flask.ext.login import LoginManager, current_user, login_user
from flask.ext.testing import TestCase
from sqlalchemy import (Column, create_engine, DateTime, Date, Float,
                        ForeignKey, Integer, Boolean, Unicode, create_engine)
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from lever import API, LeverException, UserACLMixin
from lever.mapper import BaseMapper


class FlaskTestBase(TestCase):
    """Base class for tests which use a Flask application.

    The Flask test client can be accessed at ``self.app``. The Flask
    application itself is accessible at ``self.flaskapp``.

    """

    def create_app(self):
        """Creates the Flask application and the APIManager."""
        # create the Flask application
        app = Flask(__name__)
        app.config['DEBUG'] = True
        app.config['TESTING'] = True
        del app.logger.handlers[0]
        # sqlalchemy flask
        self.base = declarative_base()
        self.engine = create_engine('sqlite://')
        self.session = scoped_session(sessionmaker(autocommit=False,
                                                   autoflush=False,
                                                   bind=self.engine))
        return app

    def get(self, uri, status_code, params=None, has_data=True, success=True,
            headers=None):
        if params:
            for p in params:
                if isinstance(params[p], dict) or isinstance(params[p], list):
                    params[p] = json.dumps(params[p])
        if headers is None:
            headers = {}
        response = self.client.get(uri, query_string=params, headers=headers)
        print(response.status_code)
        assert response.status_code == status_code
        if has_data:
            assert response.data
        j = json.loads(response.data.decode('utf8'))
        pprint(j)
        if success and status_code == 200:
            assert j['success']
        else:
            assert not j['success']
        return j

    def post(self, uri, status_code, params=None, has_data=True, headers=None,
             success=True, typ='post'):
        if headers is None:
            headers = {}
        response = getattr(self.client, typ)(
            uri,
            data=json.dumps(params),
            headers=headers,
            content_type='application/json')
        print(response.status_code)
        j = json.loads(response.data.decode('utf8'))
        pprint(j)
        assert response.status_code == status_code
        if has_data:
            assert response.data
        if success and status_code == 200:
            assert j['success']
        else:
            assert not j['success']
        return j

    def patch(self, uri, status_code, **kwargs):
        return self.post(uri, status_code, typ='patch', **kwargs)

    def put(self, uri, status_code, **kwargs):
        return self.post(uri, status_code, typ='put', **kwargs)

    def delete(self, uri, status_code, **kwargs):
        return self.post(uri, status_code, typ='delete', **kwargs)

    def basic_api(self):
        """ Generates a basic API endpoint with Lever to be tested """
        class Widget(self.base):
            __tablename__ = 'testing'
            id = Column(Integer, primary_key=True)
            name = Column(Unicode, unique=True)
            description = Column(Unicode)
            created_at = Column(DateTime, default=datetime.datetime.utcnow)

            standard_join = ['name', 'created_at', 'id', 'description']

        class WidgetAPI(API):
            model = Widget
            session = self.session
            current_user = current_user

        self.app.add_url_rule('/widget', view_func=WidgetAPI.as_view('widget'))

        return Widget, WidgetAPI


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

        class UserAPI(API, UserACLMixin):
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
