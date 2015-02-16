from .compiler import compile_syntax, link
from .exceptions import BuildError
from .loader import FsLoader
from .parser import parse_source


class BuilderError(BuildError):
    pass


class Goal(object):
    def __init__(self):
        self.cstate = None
        self.import_goals = None
        self.out_import_cstates = None


class Builder(object):
    def __init__(self, loader=None, cache=None, debug=False):
        if loader is None:
            loader = FsLoader()

        self._loader = loader
        self._all = []
        self._unprocessed = []
        self._cache = {} if cache is None else cache
        self._debug = debug

    def get_goal(self, path):
        return self._get_goal(self._loader.prepare_path(path))

    def _get_goal(self, path):
        try:
            return self._cache[path]
        except KeyError:
            goal = Goal()
            self._cache[path] = goal
            self._unprocessed.append((goal, None, path))
            self._all.append(goal)
            return goal

    def get_anonymous_goal(self, source, path):
        goal = Goal()
        self._unprocessed.append((goal, source, self._loader.prepare_path(path)))
        self._all.append(goal)
        return goal

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:  # pragma: no branch
            self.run()

    def run(self):
        while self._unprocessed:
            self._process(*self._unprocessed.pop())

        for goal in self._all:
            goal.out_import_cstates[:] = [igoal.cstate for igoal in goal.import_goals]

    def _process(self, goal, source, path):
        if source is None:
            source = self._loader.load_source(path)

        goal.cstate, import_paths, goal.out_import_cstates = compile_syntax(
            parse_source(source, path=path, debug=self._debug),
            debug=self._debug
        )
        goal.import_goals = [self._get_goal(self._loader.prepare_import_path(path, ipath)) for ipath in import_paths]


def build_from_source(source, path, loader=None, cache=None, debug=False):
    with Builder(loader, cache, debug) as builder:
        goal = builder.get_anonymous_goal(source, path)

    return link(goal.cstate)


def build_from_path(path, loader=None, cache=None, debug=False):
    with Builder(loader, cache, debug) as builder:
        goal = builder.get_goal(path)

    return link(goal.cstate)


def build_from_standalone_source(source, path=None, debug=False):
    cstate, import_paths, _ = compile_syntax(parse_source(source, path=path, debug=debug), debug=debug)
    if import_paths:
        raise BuilderError('Encountered imports in standalone build')
    return link(cstate)
