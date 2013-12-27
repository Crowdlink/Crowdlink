import yaml
from . import root


def inherit_dict(*args):
    """ Joines together multiple dictionaries left to right """
    ret = {}
    for arg in args:
        ret.update(arg)
    return ret


def inherit_lst(*args):
    """ Joines together multiple lists left to right """
    ret = []
    for arg in args:
        for val in arg:
            if val not in ret:
                ret.append(val)
    return ret


acl_yaml = yaml.load(file(root + '/crowdlink/acl.yaml').read())
acl = {}
# do a run to compile all dictionaries into lists and merge the lists to
# createa a role list of keys
for typ, roles in acl_yaml.iteritems():
    acl.setdefault(typ, {})  # set the key to a dict
    for role, keys in roles.iteritems():
        if role in ['inherit', 'virtual']:  # skip inherit commands
            continue
        acl[typ].setdefault(role, set())
        if isinstance(keys, list):
            acl[typ][role] |= set(keys)
        elif isinstance(keys, dict):
            for key, val in keys.iteritems():
                if key == "inherit":  # skip inheritence clauses, handled later
                    continue
                if isinstance(val, list):  # if its a list, prepend
                    acl[typ][role] |= set([key + "_" + v for v in val])
                elif isinstance(val, basestring):
                    acl[typ][role].add(key + "_" + val)
                else:
                    raise Exception("Type {} not supported".format(type(val)))

def compile(typ, stack, compiled=[]):
    """ Compiles a specific type, but calls itself recursively to compile it's
    own dependencies. Detects inheritence loops by checking the stack.
    Intentionally keeps a common memory compiled list """
    if typ in compiled:
        return

    for role, keys in acl_yaml[typ].iteritems():
        if role == 'inherit':
            if not isinstance(keys, list):  # allow single entry, or list
                keys = [keys]
            for inh_type in keys:
                # run inheritence from another type
                if inh_type not in acl_yaml:
                    raise KeyError(
                        "Unable to inherit from type {} for type {}, doesn't exist"
                        .format(inh_type, typ))
                if inh_type in stack:
                    raise Exception(
                        "Looping inheritence detected! Type {0} tried to "
                        "inherit from type {1} which was called to compile {0}!"
                        .format(typ, inh_type))
                if inh_type not in compiled:
                    compile(inh_type, stack + [inh_type])
                for inh_role in acl[inh_type]:
                    acl[typ].setdefault(inh_role, set())
                    acl[typ][inh_role] |= acl[inh_type][inh_role]

    for role, keys in acl_yaml[typ].iteritems():
        if isinstance(keys, dict):
            for key, val in keys.iteritems():
                if key == "inherit":
                    if not isinstance(val, list):  # allow single entry or list
                        val = [val]
                    for inh in val:
                        try:
                            acl[typ][role] |= acl[typ][inh]
                        except KeyError:
                            print acl[typ]
                            raise KeyError(
                                "Unable to inherit from role {} for role {} on type {}"
                                .format(inh, role, typ))
    compiled.append(typ)


for typ in acl_yaml:
    compile(typ, [typ])

# inheritence pass. Allows a type to inherit from another type
for typ, roles in acl_yaml.iteritems():
    for role, keys in roles.iteritems():
        if role == 'virtual':  # remove virtual types
            del acl[typ]
