#!/usr/bin/env python
# coding=utf-8

import os
import sys
import unittest

DIR = os.path.dirname(os.path.abspath(__file__))

sys.path[0] = os.path.dirname(DIR)

from yorbay.parser import parse_source


def parse(source):
    return parse_source(source, debug=True)


class TestPositionAnnotations(unittest.TestCase):
    def test_l20n(self):
        syntax = parse('\n\n  <hello "">')
        self.assertAtPos(syntax, 0, 0)

    def test_identifier(self):
        syntax = parse('<hello() {\n\n   here\n\n}>')
        self.assertAtPos(syntax.body[0].expression, 2, 3)

    def test_macro(self):
        syntax = parse('\n\n    <here() { 1 }>')
        self.assertAtPos(syntax.body[0], 2, 4)

    def test_variable(self):
        syntax = parse('<hello() {\n\n   $here\n\n}>')
        self.assertAtPos(syntax.body[0].expression, 2, 3)
        self.assertAtPos(syntax.body[0].expression.id, 2, 4)

    def test_globals_expression(self):
        syntax = parse('<hello() {\n\n   @here\n\n}>')
        self.assertAtPos(syntax.body[0].expression, 2, 3)
        self.assertAtPos(syntax.body[0].expression.id, 2, 4)

    def test_comment(self):
        syntax = parse('\n\n  /* aaa \n   */\n  ')
        self.assertAtPos(syntax.body[0], 2, 2)

    def test_import_statement(self):
        syntax = parse('\n\n import(\n "aaa")')
        self.assertAtPos(syntax.body[0], 2, 1)

    def test_entity(self):
        syntax = parse('\n  <here "">')
        self.assertAtPos(syntax.body[0], 1, 2)
        self.assertAtPos(syntax.body[0].id, 1, 3)

    def test_attribute(self):
        syntax = parse('<hello \n\n\n  here : "">')
        self.assertAtPos(syntax.body[0].attrs[0], 3, 2)
        self.assertAtPos(syntax.body[0].attrs[0].key, 3, 2)

    def test_hash(self):
        syntax = parse('<hello \n {\nx:""}>')
        self.assertAtPos(syntax.body[0].value, 1, 1)

    def test_hash_item(self):
        syntax = parse('<hello {\n   x \n: ""}>')
        self.assertAtPos(syntax.body[0].value.content[0], 1, 3)
        self.assertAtPos(syntax.body[0].value.content[0].key, 1, 3)

    def test_conditional_expression(self):
        syntax = parse('<hello() { 1 \n\n ? 2 : 3}>')
        self.assertAtPos(syntax.body[0].expression, 2, 1)

    def test_logical_expression(self):
        syntax = parse('<hello() { 1 \n\n &&\n\n 2 }>')
        self.assertAtPos(syntax.body[0].expression, 2, 1)

    def test_binary_expression(self):
        syntax = parse('<hello() { 1 \n\n   +\n\n 2 }>')
        self.assertAtPos(syntax.body[0].expression, 2, 3)

    def test_logical_operator(self):
        syntax = parse('<hello() { 1 \n\n &&\n\n 2 }>')
        self.assertAtPos(syntax.body[0].expression.operator, 2, 1)

    def test_binary_operator(self):
        syntax = parse('<hello() { 1 \n\n   +\n\n 2 }>')
        self.assertAtPos(syntax.body[0].expression.operator, 2, 3)

    def test_unary_expression(self):
        syntax = parse('<hello() { \n    !\n 123 }>')
        self.assertAtPos(syntax.body[0].expression, 1, 4)

    def test_unary_operator(self):
        syntax = parse('<hello() { \n    !\n 123 }>')
        self.assertAtPos(syntax.body[0].expression.operator, 1, 4)

    def test_parenthesis_expression(self):
        syntax = parse('<hello() { \n(\n123\n\n  ) }>')
        self.assertAtPos(syntax.body[0].expression, 1, 0)

    def test_property_expression_static(self):
        syntax = parse('<hello() { \n x.y }>')
        self.assertAtPos(syntax.body[0].expression, 1, 2)
        self.assertAtPos(syntax.body[0].expression.property, 1, 3)

    def test_property_expression_computed(self):
        syntax = parse('<hello() { \n x[ y ] }>')
        self.assertAtPos(syntax.body[0].expression, 1, 2)
        self.assertAtPos(syntax.body[0].expression.property, 1, 4)

    def test_attribute_expression_static(self):
        syntax = parse('<hello() { \n x::y }>')
        self.assertAtPos(syntax.body[0].expression, 1, 2)
        self.assertAtPos(syntax.body[0].expression.attribute, 1, 4)

    def test_attribute_expression_computed(self):
        syntax = parse('<hello() { \n x::[ y ] }>')
        self.assertAtPos(syntax.body[0].expression, 1, 2)
        self.assertAtPos(syntax.body[0].expression.attribute, 1, 6)

    def test_this_expression(self):
        syntax = parse('<hello() { \n  ~\n }>')
        self.assertAtPos(syntax.body[0].expression, 1, 2)

    def test_call_expression(self):
        syntax = parse('<hello() { \n\n\nf(\n1) }>')
        self.assertAtPos(syntax.body[0].expression, 3, 1)

    def test_number(self):
        syntax = parse('<hello() { \n\n\n 3 }>')
        self.assertAtPos(syntax.body[0].expression, 3, 1)

    def test_string(self):
        syntax = parse('<hello() { \n\n\n  """aa\n""" }>')
        self.assertAtPos(syntax.body[0].expression, 3, 2)

    def test_complex_string(self):
        syntax = parse('<hello \n"""\n a\n  {{\n  b\n   \n }}\n     c""" >')
        self.assertAtPos(syntax.body[0].value, 1, 0)
        self.assertAtPos(syntax.body[0].value.content[0], 1, 3)
        self.assertAtPos(syntax.body[0].value.content[1], 4, 2)
        self.assertAtPos(syntax.body[0].value.content[2], 6, 3)

    def assertAtPos(self, node, line, column):
        self.assertEqual(node.pos.line, line)
        self.assertEqual(node.pos.column, column)


if __name__ == '__main__':
    unittest.main()
