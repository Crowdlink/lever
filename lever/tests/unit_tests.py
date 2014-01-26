import unittest
import types

from lever import API, preprocess, postprocess


class ProcessTests(unittest.TestCase):
    """ Ensures our metaclasses and decorators operate as we want for assigning
    preprocessors """
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

    def test_none(self):
        class APIAwesome(API):
            pass

        assert APIAwesome._pre_method == {}
        assert APIAwesome._pre_action == {}
