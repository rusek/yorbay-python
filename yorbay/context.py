import sys

from .builder import build_from_path, build_from_source
from .compiler import ErrorWithSource, CompiledL20n, LazyCompiledL20n
from .discovery import build_from_module_lazy
from .globals import default_globals


class Context(object):
    def __init__(self, obj, globals=None, extra_globals=None, error_hook=None):
        if isinstance(obj, CompiledL20n):
            get_l20n = lambda: obj
        elif isinstance(obj, LazyCompiledL20n):
            get_l20n = obj.get
        else:
            raise TypeError('Invalid argument: {0!r}'.format(obj))

        self._vars = {}
        self._get_l20n = get_l20n
        self._globals = default_globals if globals is None else globals
        if extra_globals:
            self._globals = dict(self._globals)
            self._globals.update(extra_globals)
        self._error_hook = error_hook

    @classmethod
    def from_string(cls, s, loader=None, debug=False, **kwargs):
        return cls(build_from_source(s, '', loader, debug=debug), **kwargs)

    @classmethod
    def from_file(cls, f, loader=None, debug=False, **kwargs):
        if isinstance(f, basestring):
                return cls(build_from_path(f, loader, debug=debug), **kwargs)
        else:
            return cls(build_from_source(f.read(), '', loader, debug=debug), **kwargs)

    @classmethod
    def from_module(cls, name, **kwargs):
        return cls(build_from_module_lazy(name), **kwargs)

    def __contains__(self, key):
        return key in self._vars

    def __getitem__(self, key):
        return self._vars[key]

    def get(self, key, default=None):
        return self._vars.get(key, default)

    def __setitem__(self, key, value):
        if not isinstance(key, basestring):
            raise TypeError('Key must be a string, not {0}'.format(type(key)))
        self._vars[key] = value

    def __delitem__(self, key):
        del self._vars[key]

    def __call__(self, query, **local_vars):
        l20n = self._get_l20n()

        # Fast path: if the content of an entity or an attribute is a simple string, then
        # we do not have to create execution environment - we can use direct_queries mapping
        # instead
        value = l20n.direct_queries.get(query)
        if value is not None:
            return value

        # Fast path is not available. Construct variable mapping, trying to avoid unnecessary
        # dict merging.
        if not local_vars:
            vars = self._vars
        elif not self._vars:
            vars = local_vars
        else:
            vars = {}
            vars.update(self._vars)
            vars.update(local_vars)

        env = l20n.make_env(vars, self._globals)
        pos = query.find('::')
        try:
            if pos == -1:
                # Entities without content resolve to None, but this function is supposed
                # to always return strings, so None should be replaced with ''
                return env.resolve_entity(query) or ''
            else:
                return env.resolve_attribute(query[:pos], query[pos + 2:])
        except ErrorWithSource as e:
            if self._error_hook is not None:
                self._error_hook(type(e.cause), e.cause, sys.exc_info()[2])
            return e.source
        except StandardError:
            if self._error_hook is not None:
                self._error_hook(*sys.exc_info())
            return query
