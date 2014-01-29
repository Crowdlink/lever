import unittest
import types
import datetime

from flask import Flask
from pprint import pprint
from sqlalchemy import (Column, create_engine, DateTime, Date, Float,
                        ForeignKey, Integer, Boolean, Unicode, create_engine)

from lever import API, preprocess, postprocess, ModelBasedACL, ImpersonateMixin
from lever.tests.model_helpers import FlaskTestBase, TestUserACL


class ProcessTests(unittest.TestCase):
    """ Ensures our metaclasses and decorators operate as we want for assigning
    preprocessors and postprocessors """
    def test_basic_preprocess(self):
        class APIAwesome(API):
            @preprocess(method='post')
            def preprocess_those(self):
                pass

            @preprocess(action='something')
            def preprocess_that(self):
                pass

        assert isinstance(APIAwesome._pre_method['post'][0],
                          types.FunctionType)
        assert isinstance(APIAwesome._pre_action['something'][0],
                          types.FunctionType)

    def test_inheritence_mixins(self):
        class APIParent(object):
            @preprocess(method='post')
            def preprocess_those(self):
                pass
        class APIAwesome(API, APIParent):
            pass

        assert isinstance(APIAwesome._pre_method['post'][0],
                          types.FunctionType)

    def test_inheritence(self):
        class APIParent(API):
            @preprocess(method='post')
            def preprocess_those(self):
                pass
        class APIAwesome(APIParent):
            pass

        assert isinstance(APIAwesome._pre_method['post'][0],
                          types.FunctionType)

    def test_inheritence_reversal(self):
        class APIParent(API):
            pass
        class APIAwesome(APIParent):
            @preprocess(method='post')
            def preprocess_those(self):
                pass

        assert isinstance(APIAwesome._pre_method['post'][0],
                          types.FunctionType)

    def test_multi_preprocess(self):
        class APIAwesome(API):
            @preprocess(method=['post', 'get'])
            def preprocess_those(self):
                pass

            @preprocess(action=['create', 'other'])
            def preprocess_that(self):
                pass

        assert isinstance(APIAwesome._pre_method['post'][0],
                          types.FunctionType)
        assert isinstance(APIAwesome._pre_method['get'][0],
                          types.FunctionType)
        assert isinstance(APIAwesome._pre_action['other'][0],
                          types.FunctionType)
        assert isinstance(APIAwesome._pre_action['create'][0],
                          types.FunctionType)

    def test_basic_postprocess(self):
        class APIAwesome(API):
            @postprocess(method='post')
            def preprocess_those(self):
                pass

            @postprocess(action='something')
            def preprocess_that(self):
                pass

        assert isinstance(APIAwesome._post_method['post'][0],
                          types.FunctionType)
        assert isinstance(APIAwesome._post_action['something'][0],
                          types.FunctionType)

    def test_multi_postprocess(self):
        class APIAwesome(API):
            @postprocess(method=['post', 'get'])
            def preprocess_those(self):
                pass

            @postprocess(action=['create', 'other'])
            def preprocess_that(self):
                pass

        assert isinstance(APIAwesome._post_method['post'][0],
                          types.FunctionType)
        assert isinstance(APIAwesome._post_method['get'][0],
                          types.FunctionType)
        assert isinstance(APIAwesome._post_action['other'][0],
                          types.FunctionType)
        assert isinstance(APIAwesome._post_action['create'][0],
                          types.FunctionType)

    def test_preprocess_priority(self):
        class APIAwesome(API):
            @postprocess(method='post')
            def preprocess_those(self):
                pass

            @postprocess(method='post')
            def preprocess_that(self):
                pass

        self.assertEqual(
            APIAwesome._post_method['post'][0].__name__, 'preprocess_that')

        class APIAwesome(API):
            @postprocess(method='post', pri=0)
            def preprocess_those(self):
                pass

            @postprocess(method='post')
            def preprocess_that(self):
                pass

        self.assertEqual(
            APIAwesome._post_method['post'][0].__name__, 'preprocess_those')

    def test_none(self):
        class APIAwesome(API):
            pass

        assert APIAwesome._pre_method == {}
        assert APIAwesome._pre_action == {}


class TestProcessorUsage(FlaskTestBase):
    """ These tests ensure that preprocessors and postprocessors are getting
    called when they should be """

    def test_methods_preprocess(self):
        for meth in ['post', 'get', 'delete', 'put']:
            class APIAwesome(API):
                @preprocess(method=meth)
                def preprocessor_one(self):
                    raise SyntaxError  # pick an obscure one to catch..

            inst = APIAwesome()
            self.assertRaises(SyntaxError, getattr(inst, meth))

    def test_methods_postprocess(self):
        obj = self.provision_single_asset()
        data = [('post', {'name': 'test'}),
                ('get', {}),
                ('put', {'id': obj.id, 'name': 'test2'}),
                ('delete', {'id': obj.id})]
        for meth, vals in data:
            class APIAwesome(self.widget_api):
                @postprocess(method=meth)
                def postprocess_one(self, retval):
                    raise SyntaxError  # pick an obscure one to catch..

            self.app.add_url_rule('/' + meth, view_func=APIAwesome.as_view(meth))

        for meth, vals in data:
            self.assertRaises(SyntaxError, getattr(self, meth), meth, 500, params=vals)


class TestAPICreation(FlaskTestBase):
    def test_create_bad_pkey(self):
        """ ensure that exception is thrown for invalid primary_key """
        class Testing(self.base):
            __tablename__ = "testing_table"
            bad_id = Column(Integer, primary_key=True)

        class UserAPI(API):
            model = Testing
            session = self.session

        t = UserAPI()
        self.assertRaises(AttributeError, lambda: t.pkey)


class TestGet(FlaskTestBase):
    """ Test facets of our get method """

    def test_get_pkey(self):
        obj = self.provision_single_asset()
        d = self.get('widget', 200, {'id': obj.id})
        assert len(d['objects']) > 0
        assert d['objects'][0]['id'] == obj.id

    def test_many_query(self):
        self.provision_many_asset()
        d = self.get('widget', 200)
        assert len(d['objects']) >= 4


class TestPut(FlaskTestBase):
    """ Test facets of our get method """
    def test_update(self):
        """ can we change an object """
        obj = self.provision_single_asset()
        test_string = "testing this thing"
        p = {'id': obj.id, 'description': test_string}
        self.put('widget', 200, params=p)
        self.session.refresh(obj)
        assert obj.description == test_string

    def test_cant_find(self):
        self.basic_api()
        self.base.metadata.create_all(self.engine)
        ret = self.put('widget', 404, params={'id': 123})
        assert 'not be found' in ret['message']

    def test_cant_find_invalid_key(self):
        self.basic_api()
        self.base.metadata.create_all(self.engine)
        ret = self.put('widget', 404, params={'tid': 123})
        assert 'any object to update' in ret['message']


class TestDelete(FlaskTestBase):
    def test_delete(self):
        """ can we delete an object """
        obj = self.provision_single_asset()
        obj_id = obj.id
        self.delete('widget', 200, params={'id': obj_id})
        obj = self.session.query(self.widget_model).filter_by(id=obj_id).first()
        assert obj is None

    def test_cant_find_put_delete(self):
        self.basic_api()
        self.base.metadata.create_all(self.engine)
        ret = self.delete('widget', 404, params={'id': 123})
        assert 'Object could not be found' in ret['message']

    def test_cant_find(self):
        self.basic_api()
        self.base.metadata.create_all(self.engine)
        ret = self.delete('widget', 404, params={'tid': 123})
        assert 'object to delete' in ret['message']


class TestPost(FlaskTestBase):
    def test_create_dup(self):
        """ make a duplicate entry and fail """
        obj = self.provision_single_asset()
        p = self.post('widget', 409, params={'name': u'Testing'})
        assert 'duplicate value already' in p['message']

    def test_create_new(self):
        """ try creating a new object """
        self.basic_api()
        self.base.metadata.create_all(self.engine)
        p = self.post('widget', 200, params={'name': u'Testing'})
        assert p['objects'][0]['name'] == 'Testing'

    def test_bad_action(self):
        obj = self.provision_single_asset()
        p = {'id': obj.id, '__action': 'dsflgjksdfglk'}
        ret = self.post('widget', 400, params=p)
        assert 'missing key' in ret['message']


class TestSearch(FlaskTestBase):
    """ Run a bunch of positive and negative tests on our searching system """
    def test_filter_by(self):
        obj = self.provision_single_asset()
        d = self.get('widget', 200, {'__filter_by': {'name': obj.name}})
        assert len(d['objects']) > 0
        assert d['objects'][0]['name'] == obj.name

    def test_single_failure(self):
        self.basic_api()
        self.base.metadata.create_all(self.engine)
        ret = self.get('widget', 404, params={'__one': True})
        assert 'not be found' in ret['message']

    def test_query_bad_param_filter_by(self):
        self.basic_api()
        ret = self.get('widget', 400, params={'__filter_by': {'sdflgj': True}})
        assert 'invalid field' in ret['message']

    def test_query_filter(self):
        obj = self.provision_single_asset()
        ret = self.get('widget', 200,
                       params={'__filter': [
                           {'val': 'Testing', 'name': 'name', 'op': 'eq'}]})
        assert ret['objects'][0]['name'] == 'Testing'

    def test_query_filter_field(self):
        """ test filtering by comparing different fields to eachother """
        obj = self.provision_single_asset()
        # TODO: Write a positive test for this
        ret = self.get('widget', 200,
                       params={'__filter': [
                           {'field': 'created_at', 'name': 'name', 'op': 'eq'}]})
        assert len(ret['objects']) == 0

    def test_query_bad_param_filter(self):
        self.basic_api()
        ret = self.get('widget', 400,
                       params={'__filter': [
                           {'val': True, 'name': 'dsflgjsdflgk', 'op': 'eq'}]})
        assert 'invalid field' in ret['message']

    def test_query_bad_param_op(self):
        self.basic_api()
        ret = self.get('widget', 400,
                 params={'__filter': [
                     {'val': True, 'name': 'name', 'op': 'fake'}]})
        assert 'operator specified in' in ret['message']

    def test_query_missing_param(self):
        self.basic_api()
        ret = self.get('widget', 400,
                 params={'__filter': [
                     {'val': True, 'name': 'name', 'op2': 'fake'}]})
        assert 'missing required arguments' in ret['message']

    def test_query_bad_param_count(self):
        self.basic_api()
        ret = self.get('widget', 400,
                 params={'__filter': [{'name': 'name', 'op': '=='}]})
        assert 'argument count' in ret['message']

    def test_order_by(self):
        self.provision_many_asset()
        ret = self.get('widget', 200, params={'__order_by': ['id']})
        assert len(ret['objects']) >= 4
        assert ret['objects'][0]['id'] < ret['objects'][1]['id']
        assert ret['objects'][2]['id'] < ret['objects'][3]['id']

    def test_order_by_desc(self):
        self.provision_many_asset()
        ret = self.get('widget', 200, params={'__order_by': ['-id']})
        assert len(ret['objects']) >= 4
        assert ret['objects'][0]['id'] > ret['objects'][1]['id']
        assert ret['objects'][2]['id'] > ret['objects'][3]['id']

    def test_order_by_bad_key(self):
        self.basic_api()
        ret = self.get('widget', 400, params={'__order_by': ['dflgjksdfgl']})
        assert 'Order_by operator' in ret['message']


class TestLogin(TestUserACL):
    """ Tests abilities of the User ACL mixin class """
    def test_login(self):
        """ can we login with a patch action """
        self.user_api()
        self.base.metadata.create_all(self.engine)
        people = self.provision_users()
        p = {'__action': 'login', 'id': people[0].id, 'password': "testing"}
        self.post('user', 200, params=p)

    def test_delete_fail(self):
        """ will delete fail with bad permissions? """
        self.user_api()
        self.base.metadata.create_all(self.engine)
        people = self.provision_users()
        p = {'id': people[2].id}
        self.delete('user', 403, params=p)

    def test_impersonate(self):
        """ can the admin properly impersonate someone for a create?"""
        self.user_api()
        class Widget(self.base):
            __tablename__ = 'testing'
            id = Column(Integer, primary_key=True)
            name = Column(Unicode, unique=True)
            owner = Column(Unicode)
            created_at = Column(DateTime, default=datetime.datetime.utcnow)

            acl = {'admin': set(['class_create_other', 'action_create'])}
            standard_join = ['name', 'created_at', 'id']

            @classmethod
            def create(cls, name, user=None):
                inst = cls(name=name)
                if user:
                    self.owner = user.username
                self.session.add(inst)
                return inst


        class WidgetAPI(ImpersonateMixin, ModelBasedACL, API):
            model = Widget
            session = self.session
            create_method = "create"
            user_model = self.user_model


        self.app.add_url_rule('/widget', view_func=WidgetAPI.as_view('widget'))
        self.base.metadata.create_all(self.engine)
        people = self.provision_users()
        p = {'__action': 'login', 'id': self.admin.id, 'password': "testing"}
        self.post('user', 200, params=p)
        p = {'__user_id': people[2].id, 'name': 'testing'}
        self.post('widget', 200, params=p)
