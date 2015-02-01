from .parser import parse_source
from .compiler import compile_syntax, ErrorWithSource


class Context(object):
    def __init__(self, l20n):
        self._vars = {}
        self._l20n = l20n

    @classmethod
    def from_source(cls, source):
        return Context(compile_syntax(parse_source(source)))

    @classmethod
    def from_file(cls, f):
        if isinstance(f, basestring):
            with open(f) as f:
                return Context(compile_syntax(parse_source(f.read())))
        else:
            return Context(compile_syntax(parse_source(f.read())))

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
        if pos == -1:
            try:
                return env.resolve_entity(query)
            except ErrorWithSource as e:
                return e.source
            except:
                return query
        else:
            try:
                return env.resolve_attribute(query[:pos], query[pos + 2:])
            except ErrorWithSource as e:
                return e.source
            except:
                return query
