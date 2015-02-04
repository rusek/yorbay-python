#!/usr/bin/env python

import os
import sys
import unittest

DIR = os.path.dirname(os.path.abspath(__file__))

sys.path[0] = os.path.dirname(DIR)

from yorbay.builder import build_from_path, build_from_standalone_source
from yorbay.compiler import CircularDependencyError
from yorbay.loader import FsLoader


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


if __name__ == '__main__':
    unittest.main()
