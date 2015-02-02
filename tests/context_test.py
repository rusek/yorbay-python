#!/usr/bin/env python

from collections import defaultdict
import os
import sys
import unittest
from StringIO import StringIO

DIR = os.path.dirname(os.path.abspath(__file__))

sys.path[0] = os.path.dirname(DIR)

from yorbay.context import Context


def delete_item(obj, item):
    del obj[item]


def set_item(obj, key, value):
    obj[key] = value


class MyError(Exception):
    pass


def raise_my_error(*args, **kwargs):
    raise MyError()


class TestContext(unittest.TestCase):
    def setUp(self):
        self.context = Context.from_source("""
            <one 'eins'>

            <types {
                str: "string",
                num: "number",
                bool: "boolean",
                *other: "other"
            }>

            <typesIndexed[$type] {
                str: "string",
                num: "number",
                bool: "boolean",
                *other: "other"
            }>

            <type "{{ types[$type] }}">

            <withAttribs
                'Me have attributes!'
                color:'red'
            >

            <withBadAttribs
                error:'{{ $noSuchVar }}'
                indexError[$noSuchVar]:{k1: "v1", k2: "v2"}
            >

            <withoutContent dummy:"dummy">

            <accessObjKeyProp "{{ $obj.key }}">

            <luckyNum "Your lucky number is {{ $num }}">
        """)

    def test_entity_query(self):
        self.assertEqual(self.context('one'), 'eins')
        self.assertEqual(self.context('types'), 'other')
        self.assertEqual(self.context('type', type='num'), 'number')

    def test_graceful_errors_in_entity_query(self):
        self.assertEqual(self.context('type'), '{{ types[$type] }}')
        self.assertEqual(self.context('typesIndexed'), 'typesIndexed')

    def test_attribute_query(self):
        self.assertEqual(self.context('withAttribs::color'), 'red')

    def test_graceful_errors_in_attribute_query(self):
        self.assertEqual(self.context('withBadAttribs::error'), '{{ $noSuchVar }}')
        self.assertEqual(self.context('withBadAttribs::indexError'), 'withBadAttribs::indexError')

    def test_variable_overrides(self):
        self.context['num'] = 42
        self.assertEqual(self.context('luckyNum'), 'Your lucky number is 42')
        self.assertEqual(self.context('luckyNum', num=13), 'Your lucky number is 13')

    def test_context_variable_access(self):
        self.assertEqual(self.context.get('missing'), None)
        self.assertEqual(self.context.get('missing', '?'), '?')
        self.assertFalse('missing' in self.context)
        self.assertRaises(KeyError, lambda: self.context['missing'])

        self.context['found'] = True
        self.assertTrue(self.context['found'])
        self.assertTrue(self.context.get('found'))
        self.assertTrue('found' in self.context)

        del self.context['found']
        self.assertRaises(KeyError, lambda: self.context['found'])
        self.assertRaises(KeyError, delete_item, self.context, 'found')

    def test_context_variable_must_be_string(self):
        self.assertRaises(TypeError, set_item, self.context, 1, 'val')

    def test_entity_without_content_should_resolve_to_empty_string(self):
        self.assertEqual(self.context('withoutContent'), '')

    def test_direct_exception_subclasses_are_not_supressed(self):
        self.assertRaises(MyError, self.context, 'accessObjKeyProp', obj=defaultdict(raise_my_error))


class TestFromFile(unittest.TestCase):
    def test_load_by_path(self):
        tr = Context.from_file(os.path.join(DIR, 'samples', 'numbers.l20n'))
        self.assertEqual(tr('thousand'), '1000')

    def test_invalid_path_raises_io_error(self):
        self.assertRaises(IOError, Context.from_file, os.path.join(DIR, 'samples', 'no-such-file'))

    def test_load_by_open_file(self):
        with open(os.path.join(DIR, 'samples', 'numbers.l20n')) as f:
            tr = Context.from_file(f)
        self.assertEqual(tr('pi'), '3.14')

    def test_load_by_file_like(self):
        f = StringIO('<entity "some value">')
        tr = Context.from_file(f)
        self.assertEqual(tr('entity'), "some value")


class TestErrorHook(unittest.TestCase):
    def setUp(self):
        self.error = None

    def test_error_hook_on_missing_entity(self):
        tr = Context.from_source('', error_hook=self.store_error)
        tr('noSuchEntity')
        self.assertTrue(isinstance(self.error, NameError))

    def test_error_hook_on_missing_variable(self):
        tr = Context.from_file(StringIO('<a "{{ $missing }}">'), error_hook=self.store_error)
        self.assertTrue(tr('a'), '{{ $missing }}')
        self.assertTrue(isinstance(self.error, NameError))

    def test_raise_error_hook(self):
        tr = Context.from_file(os.path.join(DIR, 'samples', 'numbers.l20n'), error_hook=self.raise_error)
        self.assertRaises(NameError, tr, 'noSuchEntity')

    def store_error(self, exc_type, exc_value, traceback):
        self.assertTrue(isinstance(exc_value, exc_type))
        self.error = exc_value

    def raise_error(self, exc_type, exc_value, traceback):
        raise exc_type, exc_value, traceback

if __name__ == '__main__':
    unittest.main()
