from flask import current_app
from flask.ext.login import current_user
from flask.ext.sqlalchemy import BaseQuery

import six


class BaseMapper(object):
    """ The base model instance for all model. Provides lots of useful
    utilities in addition to access control logic and serialization helpers """

    # Allows us to run query on the class directly, instead of through a
    # session
    query_class = BaseQuery
    query = None

    # Access Control Methods
    # =========================================================================
    def roles(self, user=current_user):
        """ This should be overriden to use logic for determining roles on an
        instance of the class. This should include inheriting parent roles from
        p_roles function. """
        return []

    @classmethod
    def p_roles(self):
        """ Determines roles to be gained from parent objects. Usually uses the
        _inherit_roles helper function to prefix all parent roles with their
        class name """
        return []

    def can(self, action, user=current_user):
        """ Can the user perform the action needed on this object instance?
        Checks for the desired key in a list of allowed action keys. """
        keys = self.user_acl(user=user)
        return action in keys

    @classmethod
    def can_cls(cls, action, user=current_user, **parents):
        """ Similar to can, except does not include instance specific roles.
        Intended to be used to determine if pre-creation events can occur, such
        as create or create_other. Requires the data on parents to be passed in
        via keyword arguments to determine parent roles"""
        return action in cls._role_mix(cls.p_roles(**parents) + user.global_roles())

    def user_acl(self, user=current_user):
        """ A list of access keys the user has with context to the current
        object """
        roles = self.roles(user=user) + user.global_roles()
        return self._role_mix(roles)

    @classmethod
    def _role_mix(cls, roles):
        """ A utility that takes a list of roles and returns a set of allowed
        actions that was determined by those roles """
        allowed = set()
        for role in roles:
            allowed |= cls.acl.get(role, set())
        current_app.logger.debug((roles, allowed))
        return allowed

    @classmethod
    def _inherit_roles(cls, user=current_user, **kwargs):
        """ a utility method that prefixes the roles of parents """
        r = []
        for prefix, obj in six.iteritems(kwargs):
            r += [prefix + "_" + i for i in obj.roles(user=user)]
        return r
