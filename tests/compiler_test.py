#!/usr/bin/env python

import os
import sys
import unittest

DIR = os.path.dirname(os.path.abspath(__file__))

sys.path[0] = os.path.dirname(DIR)

from yorbay.builder import build_from_path
from yorbay.loader import PosixPathLoader


class DictLoader(PosixPathLoader):
    def __init__(self, d):
        self._d = d

    def load_source(self, path):
        return self._d[path[1:]]


def resources_to_env(d):
    return build_from_path('main.l20n', loader=DictLoader(d)).make_env()


class TestImports(unittest.TestCase):
    def test_modules_have_independent_scopes(self):
        env = resources_to_env({
            'main.l20n': '''
                import("helper.l20n")
                <value "from main">
                <main "{{ helper }} / {{ value }}">
            ''',
            'helper.l20n': '''
                <value "from helper">
                <helper "{{ value }}">
            '''
        })
        self.assertEqual(env.resolve_entity('main'), 'from helper / from main')

    def test_imports_are_transitive(self):
        env = resources_to_env({
            'main.l20n': '''
                import("first.l20n")
                <a "A">
                <all "{{ a }}{{ b }}{{ c }}{{ d }}">
            ''',
            'first.l20n': '''
                import("second.l20n")
                <b "B">
            ''',
            'second.l20n': '''
                import("third.l20n")
                <c "C">
            ''',
            'third.l20n': '''
                <d "D">
            '''
        })
        self.assertEqual(env.resolve_entity('all'), 'ABCD')

if __name__ == '__main__':
    unittest.main()
