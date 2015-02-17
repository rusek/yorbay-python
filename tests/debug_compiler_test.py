#!/usr/bin/env python
# coding=utf-8

import os
import sys
import unittest

DIR = os.path.dirname(os.path.abspath(__file__))

sys.path[0] = os.path.dirname(DIR)

from yorbay.builder import build_from_standalone_source
from yorbay.compiler import ErrorWithSource
from yorbay.globals import Global
from yorbay.debug.stacktrace import get_stack


class DummyGlobal(Global):
    def get(self):
        return ''


class TestStackTrace(unittest.TestCase):
    def setUp(self):
        self.path = '/some/path.l20n'
        self.l20n = None

    def build(self, source):
        self.l20n = build_from_standalone_source(source, path=self.path, debug=True)

    def resolve_exc(self, entity_name):
        try:
            self.l20n.make_env().resolve_entity(entity_name)
        except ErrorWithSource as e:
            return e.cause
        except StandardError as e:
            return e
        self.fail()

    def test_lazy_hash(self):
        self.build(
            '\n'
            '<myhash {key: "value"}>\n'
            '\n'
            '<show "{{ myhash.noSuchKey }}">'
        )
        exc = self.resolve_exc('show')
        self.assertTrue(isinstance(exc, KeyError))
        stack = get_stack(exc)
        self.assertEqual(len(stack), 2)
        self.assertFrameEqual(stack[0], 'entity', 'myhash', 1, 8)
        self.assertFrameEqual(stack[1], 'entity', 'show', 3, 16)

    def test_nested_expressions(self):
        self.build(
            '<show "{{\n'
            '  5\n'
            '    /\n'
            '  0 \n'
            '    +\n'
            '  1 }}">'
        )
        exc = self.resolve_exc('show')
        self.assertTrue(isinstance(exc, ArithmeticError), msg=(type(exc), exc))
        stack = get_stack(exc)
        self.assertEqual(len(stack), 1)
        self.assertFrameEqual(stack[0], 'entity', 'show', 2, 4)

    def assertFrameEqual(self, frame, entry_type, entry_name, line, column):
        self.assertEqual(
            (frame.entry_type, frame.entry_name, frame.pos.line, frame.pos.column),
            (entry_type, entry_name, line, column)
        )


class TestSimilarity(unittest.TestCase):
    def setUp(self):
        self.l20n = build_from_standalone_source("""
        <withVar "{{ $varName }}">
        <withEntry "{{ entryName }}">
        <withEntryNotSimilar "{{ entryNameWhichIsSeriouslyWrong }}">
        <withGlobal "{{ @globalName }}">

        <entryname "">
        <entname "">

        <macroWithVar($macroVarName) { $macrovarname }>
        <withMacroVar "{{ macroWithVar(12) }}">
        """, debug=True)

    def resolve_exc(self, entity_name, vars=None, globals=None):
        try:
            self.l20n.make_env(vars=vars, globals=globals).resolve_entity(entity_name)
        except ErrorWithSource as e:
            return e.cause
        except StandardError as e:
            return e
        self.fail()

    def test_entry_similar(self):
        exc = self.resolve_exc('withEntry')
        self.assertTrue(isinstance(exc, NameError))
        self.assertTrue('Did you mean "entryname"' in str(exc), msg=str(exc))

    def test_entry_not_similar(self):
        exc = self.resolve_exc('withEntryNotSimilar')
        self.assertTrue(isinstance(exc, NameError))
        self.assertTrue('Did you mean' not in str(exc), msg=str(exc))

    def test_variable_similar(self):
        exc = self.resolve_exc('withVar', vars={
            'vrName': 1, 'vaarNme': 2,
        })
        self.assertTrue(isinstance(exc, NameError))
        self.assertTrue('Did you mean "vrName"' in str(exc), msg=str(exc))

    def test_macro_variable_similar(self):
        exc = self.resolve_exc('withMacroVar', vars={
            'maakroVarName': 1, 'x': 2,
        })
        self.assertTrue(isinstance(exc, NameError))
        self.assertTrue('Did you mean "macroVarName"' in str(exc), msg=str(exc))

        exc = self.resolve_exc('withMacroVar', vars={
            'marcovarname': 1, 'x': 2,
        })
        self.assertTrue(isinstance(exc, NameError))
        self.assertTrue('Did you mean "marcovarname"' in str(exc), msg=str(exc))

    def test_variable_not_similar(self):
        exc = self.resolve_exc('withVar', vars={
            'first': 1, 'second': 2,
        })
        self.assertTrue(isinstance(exc, NameError))
        self.assertTrue('Did you mean' not in str(exc), msg=str(exc))

    def test_global_similar(self):
        exc = self.resolve_exc('withGlobal', globals={
            'cookies': DummyGlobal(), 'globbbName': DummyGlobal(), 'globlalName': DummyGlobal()
        })
        self.assertTrue(isinstance(exc, NameError))
        self.assertTrue('Did you mean "globlalName"' in str(exc), msg=str(exc))

    def test_global_not_similar(self):
        exc = self.resolve_exc('withGlobal', globals={
            'what': DummyGlobal(), 'terrible': DummyGlobal(), 'failure': DummyGlobal()
        })
        self.assertTrue(isinstance(exc, NameError))
        self.assertTrue('Did you mean' not in str(exc), msg=str(exc))


if __name__ == '__main__':
    unittest.main()
