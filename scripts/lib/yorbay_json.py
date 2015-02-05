import inspect
from types import NoneType

try:
    from collections import OrderedDict as SyntaxDict
except ImportError:
    SyntaxDict = dict

from yorbay import syntax

syntax_module = syntax.__name__
syntax_node_args = {}


def syntax_to_json(obj):
    if obj.__class__.__module__ == syntax_module:
        class_name = obj.__class__.__name__
        arg_names = syntax_node_args.get(class_name)
        if arg_names is None:
            arg_names = inspect.getargspec(getattr(syntax, class_name).__init__).args[1:]
            syntax_node_args[class_name] = arg_names

        ret = SyntaxDict()
        ret['type'] = class_name
        for arg_name in arg_names:
            ret[arg_name] = syntax_to_json(getattr(obj, arg_name))
        return ret
    elif isinstance(obj, list):
        return map(syntax_to_json, obj)
    elif isinstance(obj, (NoneType, int, float, basestring)):  # bool is a subclass of int
        return obj
    else:
        raise TypeError('Unexpected object: {0!r}'.format(obj))
