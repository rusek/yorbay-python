#!/usr/bin/env python

import os
import sys
import unittest

DIR = os.path.dirname(os.path.abspath(__file__))

sys.path[0] = os.path.dirname(DIR)

from yorbay.builder import build_from_path, build_from_standalone_source
from yorbay.compiler import CircularDependencyError
from yorbay.loader import FsLoader, SimpleLoader, LoaderError


class DictLoader(SimpleLoader):
    def __init__(self, files):
        super(DictLoader, self).__init__()
        self.files = files
        self.load_count = 0

    def load_source(self, path):
        try:
            self.load_count += 1
            return self.files[path]
        except KeyError:
            raise LoaderError('Not found: {0}'.format(path))


class TestBuildFromStandaloneSource(unittest.TestCase):
    def test_standalone_source(self):
        cl20n = build_from_standalone_source('<hello "Hello, sailor!">')
        self.assertEqual(cl20n.direct_queries['hello'], 'Hello, sailor!')

    def test_source_with_imports_should_produce_error(self):
        self.assertRaises(StandardError, build_from_standalone_source, 'import("goodies.l20n")')


class TestCircularDependencies(unittest.TestCase):
    def setUp(self):
        self.loader = FsLoader(os.path.join(DIR, 'samples'))

    def test_module_depends_on_itself(self):
        self.assertRaises(CircularDependencyError, build_from_path, 'depends-on-itself.l20n', loader=self.loader)

    def test_cycle_of_several_modules(self):
        self.assertRaises(CircularDependencyError, build_from_path, 'a-depends-on-b.l20n', loader=self.loader)


class TestCache(unittest.TestCase):
    def setUp(self):
        self.files = {
            'main.l20n': 'import("first.l20n") import("second.l20n") import("third.l20n") '
                         '<main "{{ first }} {{ second }} {{ third }}">',
            'first.l20n': '<first "first">',
            'second.l20n': '<second "second">',
            'third.l20n': '<third "third">',
        }
        self.loader = DictLoader(self.files)
        self.cache = {}

    def build(self):
        return build_from_path('main.l20n', loader=self.loader, cache=self.cache)

    def build_success(self):
        env = self.build().make_env()
        self.assertEqual(env.resolve_entity('main'), 'first second third')

    def test_served_from_cache(self):
        self.build_success()
        self.assertEqual(self.loader.load_count, 4)
        self.build_success()
        self.assertEqual(self.loader.load_count, 4)

    def test_cache_integrity(self):
        second_data = self.files.pop('second.l20n')
        self.assertRaises(LoaderError, self.build)
        self.files['second.l20n'] = second_data
        self.build_success()


if __name__ == '__main__':
    unittest.main()
