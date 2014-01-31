""" This module allows you to build acl roles for various resources using
convenient tools like inheritence between roles and inheritence between
resources, as well as common prefix lists to prevent re-trying prefixes all
the time. For instance, I might have an object called Book that I want to make
ACL records for. Well we might do it like such:

book:
    user:
        view:
            - pages
            - contents
        add:
            - comments
    author:
        inherit: user
        edit:
            - pages
            - contents

This would all be compiled into a structure like this:
{'book':
    'user': ['view_pages', 'view_contents', 'add_comments'],
    'author': ['view_pages', 'view_contents', 'add_comments',
               'edit_pages', 'edit_contents']
}
This object is ready to be used in defining object ACL rules with lever """
import six
import itertools


def inherit_dict(*args):
    """ Joines together multiple dictionaries left to right """
    ret = {}
    for arg in args:
        ret.update(arg)
    return ret


def build_acl(structure):
    acl = {}
    # do a run to compile all dictionaries into lists and merge the lists to
    # createa a role list of keys
    for typ, roles in sorted(six.iteritems(structure)):
        acl.setdefault(typ, {})  # set the key to a dict
        for role, keys in sorted(six.iteritems(roles)):
            if role in ['inherit', 'virtual']:  # skip inherit commands
                continue
            acl[typ].setdefault(role, set())
            if isinstance(keys, list):
                acl[typ][role] |= set(keys)
            elif isinstance(keys, dict):
                for key, val in sorted(six.iteritems(keys)):
                    # skip inheritence clauses, handled later
                    if key == "inherit":
                        continue
                    if isinstance(val, list):  # if its a list, prepend
                        acl[typ][role] |= set([key + "_" + v for v in val])
                    elif isinstance(val, six.string_types):
                        acl[typ][role].add(key + "_" + val)
                    else:
                        raise Exception(
                            "Type {0} not supported".format(type(val)))

    def compile_type(acl, typ, stack, compiled):
        """ Compiles a specific type, but calls itself recursively to compile
        it's own dependencies. Detects inheritence loops by checking the stack.
        """
        if typ in compiled:
            return

        # we want to compile all its dependencies first, so find them and
        # run compile on them if they're not in the list of compiled assets
        for role, keys in sorted(six.iteritems(structure[typ])):
            if role == 'inherit':  # only look at inherit entries
                if not isinstance(keys, list):  # allow single entry, or list
                    keys = [keys]

                # for each type that this type is inheriting from
                for inh_type in keys:
                    # run inheritence from another type
                    if inh_type not in structure:  # type doesn't exist
                        raise KeyError(
                            "Unable to inherit from type {0} for type {1}, "
                            "doesn't exist".format(inh_type, typ))
                    if inh_type in stack:  # cyclic call stack
                        raise Exception(
                            "Looping inheritence detected! Type {0} tried to "
                            "inherit from type {1} which was called to compile"
                            "{0}!".format(typ, inh_type))
                    if inh_type not in compiled:  # compile if not compiled
                        compile_type(acl, inh_type, stack + [inh_type], compiled)

                    # pull in inherited role information
                    # for each role in the type that is being inherited
                    for inh_role in acl[inh_type]:
                        # join the keys on the roles of the inherited role
                        acl[typ].setdefault(inh_role, set())
                        acl[typ][inh_role] |= acl[inh_type][inh_role]

                        # now set the inheritence rules in the inheriting types
                        # role list for lookup later when role inheritence
                        # occurs
                        if 'inherit' in structure[inh_type][inh_role]:
                            structure[typ][inh_role] = {
                                'inherit':
                                structure[inh_type][inh_role]['inherit']}
                        else:
                            structure[typ][inh_role] = {'inherit': []}

        # now run the actual compilation of all the roles
        for role, keys in sorted(six.iteritems(structure[typ])):
            if isinstance(keys, dict):
                for key, val in sorted(six.iteritems(keys)):
                    if key == "inherit":
                        #print("inheriting role " + val + " for role " + role)
                        # allow single entry or list
                        if not isinstance(val, list):
                            val = [val]
                        # keep a list of keys we've inherited from
                        inherited = []
                        for inh in val:
                            # prevent infinite loops by keeping a traveled list
                            if inh not in inherited:
                                inherited.append(inh)
                                try:
                                    acl[typ][role] |= acl[typ][inh]
                                except KeyError:
                                    raise KeyError(
                                        "Unable to inherit from role {0} "
                                        "for role {1} on type {2}".
                                        format(inh, role, typ))

                                # check if what we're inheriting from inherits
                                other_inh = structure[typ][inh]
                                if 'inherit' in other_inh:
                                    if not isinstance(other_inh['inherit'], list):
                                        # add a scalar list of inherits
                                        val.append(other_inh['inherit'])
                                    else:
                                        # extend a list of inherits
                                        val.extend(other_inh['inherit'])

            elif not isinstance(keys, list):
                if role not in ('virtual', 'inherit'):
                    raise Exception(
                        "Contents of role must be dictionary, instead got {0}"
                        " of value {1} for role {2} in type {3}"
                        .format(type(keys), keys, role, typ))
        compiled.append(typ)

    compiled = []
    for typ in structure:
        compile_type(acl, typ, [typ], compiled)

    # inheritence pass. Allows a type to inherit from another type
    for typ, roles in sorted(six.iteritems(structure)):
        for role, keys in sorted(six.iteritems(roles)):
            if role == 'virtual':  # remove virtual types
                del acl[typ]

    return acl
