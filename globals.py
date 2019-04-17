
# The dictionary of render targets and a decorator to add those
TARGETS = {}


def target_function(fun, name=None):
    if name is None:
        name = fun.__name__
    TARGETS[name] = fun
    return fun
