import sys

from .loader import default_loader
from .parser import parse_source
from .compiler import compile_syntax, ErrorWithSource


class Context(object):
    def __init__(self, l20n, error_hook=None):
        self._vars = {}
        self._l20n = l20n
        self._error_hook = error_hook

    @classmethod
    def from_source(cls, source, **kwargs):
        return Context(compile_syntax(parse_source(source)), **kwargs)

    @classmethod
    def from_file(cls, f, **kwargs):
        if isinstance(f, basestring):
                return Context(compile_syntax(parse_source(default_loader.load_source(f))), **kwargs)
        else:
            return Context(compile_syntax(parse_source(f.read())), **kwargs)

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
        # Fast path: if the content of an entity or an attribute is a simple string, then
        # we do not have to create execution environment - we can use direct_queries mapping
        # instead
        value = self._l20n.direct_queries.get(query)
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

        env = self._l20n.make_env(vars)
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
