#!/usr/bin/env python

import os
import sys
import unittest

DIR = os.path.dirname(os.path.abspath(__file__))

sys.path[0] = os.path.dirname(DIR)

from yorbay.builder import build_from_path, build_from_standalone_source
from yorbay.compiler import ErrorWithSource
from yorbay.loader import SimpleLoader, LoaderError


class DictLoader(SimpleLoader):
    def __init__(self, d):
        super(DictLoader, self).__init__()
        self._d = d

    def load_source(self, path):
        try:
            return self._d[path]
        except KeyError:
            raise LoaderError('Not found: {0}'.format(path))


def resources_to_env(d):
    return build_from_path('main.l20n', loader=DictLoader(d)).make_env()


def string_to_env(s):
    return build_from_standalone_source(s).make_env()


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
                import("third.l20n")
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


class TestUserResolutionMethods(unittest.TestCase):
    def setUp(self):
        self.env = string_to_env("""
            <entity "entityVal"
                attr1: "attr1Val"
                attr2: {*key: "attr2Val", other: "oops!"}
            >
            <onlyAttrs a:"">

            <macro() { "oops!" }>
        """)

    def test_entity_resolution(self):
        self.assertEqual(self.env.resolve_entity('entity'), 'entityVal')
        self.assertEqual(self.env.resolve_entity('onlyAttrs'), None)
        self.assertRaises(TypeError, self.env.resolve_entity, 'macro')
        self.assertRaises(NameError, self.env.resolve_entity, 'noSuchEntity')

    def test_attribute_resolution(self):
        self.assertEqual(self.env.resolve_attribute('entity', 'attr1'), 'attr1Val')
        self.assertEqual(self.env.resolve_attribute('entity', 'attr2'), 'attr2Val')
        self.assertRaises(TypeError, self.env.resolve_attribute, 'macro', 'attr1')
        self.assertRaises(NameError, self.env.resolve_attribute, 'entity', 'attr3')


class TestHashLookupError(unittest.TestCase):
    def test_hash_lookup(self):
        env = string_to_env('<entity["a"] {b: "b"}>')
        try:
            env.resolve_entity('entity')
        except Exception as error:
            self.assertTrue(isinstance(error, KeyError), msg=type(error))
            for msg in [str(error), error.message]:
                self.assertTrue(msg.startswith('Hash key lookup failed'), msg=repr(msg))
        else:
            self.fail()


class TestErrorSource(unittest.TestCase):
    def setUp(self):
        self.env = string_to_env("""
            <entity "{{ $noSuchVar }}!">
        """)

    def test_error_with_source(self):
        error = None
        try:
            self.env.resolve_entity('entity')
        except ErrorWithSource as error:
            pass

        self.assertTrue(error is not None)
        self.assertEqual(error.source, '{{ $noSuchVar }}!')
        self.assertTrue(str(error).endswith(str(error.cause)))


if __name__ == '__main__':
    unittest.main()
