"""
acl_test
~~~~~~~~~~~~~
Tests the pre-processor that constructs a dictionary of ACL keys from a YAML
file.
"""
from lever import build_acl

import yaml
import unittest


class TestACLContrstruction(unittest.TestCase):
    def test_virtual_removal(self):
        struct = yaml.load("""
        testing:
            virtual: true""")
        acl = build_acl(struct)
        assert 'testing' not in acl

    def test_inherit_virtual(self):
        struct = yaml.load("""
        testing:
            virtual: true
            user:
                key: exists
        testing2:
            inherit: testing
            admin:
                inherit: user""")
        acl = build_acl(struct)
        assert 'testing' not in acl
        assert 'key_exists' in acl['testing2']['admin']

    def test_basic_key(self):
        struct = yaml.load("""
        testing:
            user:
                key: exists""")
        acl = build_acl(struct)
        assert 'key_exists' in acl['testing']['user']

    def test_basic_key_list(self):
        struct = yaml.load("""
        testing:
            user:
                key:
                    - exists""")
        acl = build_acl(struct)
        assert 'key_exists' in acl['testing']['user']

    def test_basic_inherit_role(self):
        struct = yaml.load("""
        testing:
            admin:
                inherit: user
            user:
                key:
                    - exists""")
        acl = build_acl(struct)
        assert 'key_exists' in acl['testing']['admin']

    def test_basic_inherit_list_role(self):
        struct = yaml.load("""
        testing:
            admin:
                inherit:
                    - user
                    - mod
            mod:
                key:
                    - also_exists
            user:
                key:
                    - exists""")
        acl = build_acl(struct)
        assert 'key_exists' in acl['testing']['admin']
        assert 'key_also_exists' in acl['testing']['admin']

    def test_inherit_failure_role(self):
        struct = yaml.load("""
        testing:
            admin:
                inherit:
                    - broken""")
        self.assertRaises(KeyError, build_acl, struct)

    def test_inherit_failure_type(self):
        struct = yaml.load("""
        testing2:
            inherit: doesnt_exist""")
        self.assertRaises(KeyError, build_acl, struct)

    def test_looping_inherit(self):
        struct = yaml.load("""
        testing0:
            inherit: testing3
        testing1:
            inherit: testing0
        testing2:
            inherit: testing1
        testing3:
            inherit: testing2""")
        self.assertRaises(Exception, build_acl, struct)

    def test_key_dict_unsupport(self):
        struct = yaml.load("""
        testing:
            admin:
                key:
                    wont:
                        work""")
        self.assertRaises(Exception, build_acl, struct)
        try:
            build_acl(struct)
        except Exception as e:
            assert 'not supported' in str(e)

    def test_basic_inherit_type(self):
        struct = yaml.load("""
        testing:
            user:
                key: exists
        testing2:
            inherit: testing
            user:
                key: also_exists""")
        acl = build_acl(struct)
        assert 'key_exists' in acl['testing2']['user']

    def test_basic_inherit_list_type(self):
        struct = yaml.load("""
        testing:
            user:
                key: exists
        testing3:
            user:
                key: super_exists
        testing2:
            inherit:
                - testing
                - testing3
            user:
                key: also_exists""")
        acl = build_acl(struct)
        assert 'key_super_exists' in acl['testing2']['user']
