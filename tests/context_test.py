#!/usr/bin/env python

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


if __name__ == '__main__':
    unittest.main()
