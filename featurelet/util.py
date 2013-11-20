def flatten_dict(dct):
    """ Used to make building ACL lists convenient. Create infinitely nested
    keys that will just precipitate keys joined with _. Ex:
        ('edit', ['this',
                  'that',
                  'those']
                  )
        will make:
        ['edit_this',
         'edit_that',
         'edit_those']
    Recursively safe so nesting tuples works as expected.
    """
    def flatten(tpl):
        if isinstance(tpl, tuple):
            keys = []
            for key in tpl[1]:
                keys += [flatten(key)]
            return [tpl[0] + "_" + x for x in keys]
        else:
            return tpl

    return {key: flatten(value) for (key, value) in dct.iteritems()}

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
