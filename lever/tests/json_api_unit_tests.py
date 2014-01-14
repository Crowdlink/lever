import json

from lever.tests.model_helpers import TestModelsPrefilled, FlaskTestBase
from lever import API

from pprint import pprint


class TestCreateAPI(FlaskTestBase):
    def test_create_bad_pkey(self):
        class Testing(self.base):
            bad_id = self.db.Column(self.db.Integer, primary_key=True)

        class UserAPI(API):
            model = Testing
            session = self.db.session

        t = UserAPI()
        self.assertRaises(AttributeError, lambda: t.pkey)


class TestBasic(TestModelsPrefilled):

    def get(self, uri, status_code, params=None, has_data=True, success=True,
            headers=None):
        if params:
            for p in params:
                if isinstance(params[p], dict) or isinstance(params[p], list):
                    params[p] = json.dumps(params[p])
        if headers is None:
            headers = {}
        response = self.app.get(uri, query_string=params, headers=headers)
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
        response = getattr(self.app, typ)(
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

    # Get Methods
    #########################################################################
    def test_get_user(self, username="mary"):
        d = self.get('/api/user', 200,
                     {'__filter_by': {'username': username}})
        assert len(d['objects']) > 0
        assert d['objects'][0]['username'] == username
        return d

    def test_get_pkey(self):
        person = self.people[0]
        username = person.username
        d = self.get('/api/user', 200, {'id': person.id})
        assert len(d['objects']) > 0
        assert d['objects'][0]['username'] == username

    def test_many_query(self):
        d = self.get('/api/user', 200)
        assert len(d['objects']) >= 5

    # Search testing
    #########################################################################
    def test_single_failure(self):
        self.get('/api/user', 400, params={'__one': True})

    def test_query_bad_param_filter_by(self):
        self.get('/api/user', 400, params={'__filter_by': {'sdflgj': True}})

    def test_query_filter(self):
        ret = self.get('/api/user', 200,
                       params={'__filter': [
                           {'val': True, 'name': 'admin', 'op': 'eq'}]})
        assert ret['objects'][0]['username'] == 'admin'

    def test_query_filter_field(self):
        # TODO: Write a positive test for this
        ret = self.get('/api/user', 200,
                       params={'__filter': [
                           {'field': 'created_at', 'name': 'admin', 'op': 'eq'}]})
        assert len(ret['objects']) == 0

    def test_query_bad_param_filter(self):
        self.get('/api/user', 400,
                 params={'__filter': [
                     {'val': True, 'name': 'dsflgjsdflgk', 'op': 'eq'}]})

    def test_query_bad_param_op(self):
        self.get('/api/user', 400,
                 params={'__filter': [
                     {'val': True, 'name': 'username', 'op': 'fake'}]})

    def test_query_missing_param(self):
        self.get('/api/user', 400,
                 params={'__filter': [
                     {'val': True, 'name': 'username', 'op2': 'fake'}]})

    def test_query_bad_param_count(self):
        self.get('/api/user', 400,
                 params={'__filter': [{'name': 'username', 'op': '=='}]})

    def test_order_by(self):
        ret = self.get('/api/user', 200, params={'__order_by': ['id']})
        assert len(ret['objects']) >= 5
        assert ret['objects'][0]['id'] < ret['objects'][1]['id']
        assert ret['objects'][2]['id'] < ret['objects'][3]['id']

    def test_order_by_desc(self):
        ret = self.get('/api/user', 200, params={'__order_by': ['-id']})
        assert len(ret['objects']) >= 5
        assert ret['objects'][0]['id'] > ret['objects'][1]['id']
        assert ret['objects'][2]['id'] > ret['objects'][3]['id']

    def test_order_by_bad_key(self):
        self.get('/api/user', 400, params={'__order_by': ['dflgjksdfgl']})

    # Patch Methods
    #########################################################################
    def test_login(self, person=None):
        """ can we login with a patch action """
        if person is None:
            person = self.people[0]
        p = {'__action': 'login', 'id': person.id, 'password': "testing"}
        self.patch('/api/user', 200, params=p)

    def test_cant_find_patch(self):
        p = {'id': 342095823405982345, '__action': 'dsflgjksdfglk'}
        self.patch('/api/user', 404, params=p)

    # Post Methods
    #########################################################################
    def test_create_new(self):
        """ try creating a new user """
        p = {'username': 'testing_this', 'password': 'testing'}
        p = self.post('/api/user', 200, params=p)
        assert 'new user' in p['objects'][0]['description']
        p = self.test_get_user('testing_this')
        assert p['objects'][0]['password'] == 'testing'

    def test_create_duplicate(self):
        """ try creating a new user """
        p = {'username': 'mary', 'password': 'testing'}
        p = self.post('/api/user', 409, params=p)

    # Put Methods
    #########################################################################
    def test_update(self):
        """ can we change an object """
        person = self.people[0]
        self.test_login(person)
        self.db.session.add(person)
        test_string = "testing this thing"
        p = {'id': person.id, 'description': test_string}
        self.put('/api/user', 200, params=p)
        self.db.session.add(person)
        test_string = "testing this thing"
        p = self.test_get_user(person.username)
        assert p['objects'][0]['description'] == test_string

    # Delete Methods
    #########################################################################
    def test_delete(self):
        """ can we delete an object """
        person = self.admin
        p = {'id': self.people[2].id}
        username = self.people[2].username
        self.test_login(person)
        self.db.session.add(person)
        self.delete('/api/user', 200, params=p)
        self.get('/api/user', 404,
                 {'__filter_by': {'username': username}, '__one': True})

    def test_delete_fail(self):
        """ will delete fail with bad permissions? """
        person = self.people[0]
        p = {'id': self.people[2].id}
        username = self.people[2].username
        self.test_login(person)
        self.db.session.add(person)
        self.delete('/api/user', 403, params=p)
        self.get('/api/user', 200,
                 {'__filter_by': {'username': username}, '__one': True})

    def test_cant_find_put_delete(self):
        for method in ['put', 'delete']:
            p = {'id': 342095823405982345}
            getattr(self, method)('/api/user', 404, params=p)

    def test_cant_find_put_delete_wrong_key(self):
        for method in ['put', 'delete']:
            p = {'tid': 342095823405982345}
            getattr(self, method)('/api/user', 404, params=p)

    # Negative Tests
    #########################################################################
    def test_nothing_syntax(self):
        for method in ['put', 'delete', 'patch', 'post']:
            ret = getattr(self, method)('/api/user', 400)
            assert 'be specified' in ret['message']
