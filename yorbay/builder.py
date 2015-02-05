from .compiler import compile_syntax, link
from .loader import FsLoader
from .parser import parse_source


class Goal(object):
    def __init__(self):
        self.cstate = None
        self.import_goals = None
        self.out_import_cstates = None


class Builder(object):
    def __init__(self, loader=None):
        if loader is None:
            loader = FsLoader()

        self._loader = loader
        self._all = []
        self._unprocessed = []
        self._cache = {}

    def get_goal(self, path):
        return self._get_goal(self._loader.prepare_path(path))

    def _get_goal(self, path):
        goal = self._cache.get(path)
        if goal is None:
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
        if exc_type is None:
            self.run()

    def run(self):
        while self._unprocessed:
            self._process(*self._unprocessed.pop())

        for goal in self._all:
            goal.out_import_cstates[:] = [igoal.cstate for igoal in goal.import_goals]

    def _process(self, goal, source, path):
        if source is None:
            source = self._loader.load_source(path)

        goal.cstate, import_paths, goal.out_import_cstates = compile_syntax(parse_source(source))
        goal.import_goals = [self._get_goal(self._loader.prepare_import_path(path, ipath)) for ipath in import_paths]


def build_from_source(source, path, loader=None):
    with Builder(loader) as builder:
        goal = builder.get_anonymous_goal(source, path)

    return link(goal.cstate)


def build_from_path(path, loader=None):
    builder = Builder(loader)
    goal = builder.get_goal(path)
    builder.run()

    return link(goal.cstate)


def build_from_standalone_source(source):
    cstate, import_paths, _ = compile_syntax(parse_source(source))
    if import_paths:
        raise ValueError('Encountered imports in standalone build')
    return link(cstate)
