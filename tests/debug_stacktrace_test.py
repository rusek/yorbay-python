#!/usr/bin/env python
# coding=utf-8

from __future__ import unicode_literals

import os
from StringIO import StringIO
import sys
import traceback
import unittest

DIR = os.path.dirname(os.path.abspath(__file__))

sys.path[0] = os.path.dirname(DIR)

from yorbay.debug.stacktrace import format_exception, Frame, attach_stack, get_stack, format_exc_info, print_exc_info
from yorbay.debug.parser import Origin
from yorbay.syntax import Position
from yorbay.compiler import ErrorWithSource


def flatten(args):
    out = []
    for arg in args:
        out.extend(arg)
    return out


def value_error_exc_info(msg):
    try:
        raise ValueError(msg)
    except ValueError:
        return sys.exc_info()


class TestFormatting(unittest.TestCase):
    def setUp(self):
        source = 'line1\nline2\nline3\nline4\nline5\nline6'
        origin_no_path = Origin(source, '')
        origin_with_path = Origin(source, 'path.l20n')
        self.stack = reversed([
            Frame('entity', 'entity1', Position(0, 10, origin_with_path)),
            Frame('entity', 'entity2', Position(1, 11, origin_with_path)),
            Frame('entity', 'entity3', Position(2, 12, origin_no_path)),
            Frame('macro', 'macro4', None),
            Frame('entity', 'entity5', Position(4, 14, None)),
        ])
        self.out_header = ['Traceback (most recent call last):\n']
        self.out_frames = [
            ['  File path.l20n, line 1 in entity entity1\n', '    line1\n'],
            ['  File path.l20n, line 2 in entity entity2\n', '    line2\n'],
            ['  Line 3 in entity entity3\n', '    line3\n'],
            ['  In macro macro4\n'],
            ['  Line 5 in entity entity5\n'],
        ]
        msg = 'Sample error'
        self.exc_info = value_error_exc_info(msg)
        self.error = self.exc_info[1]
        attach_stack(self.error)[:] = self.stack
        self.out_error = ['ValueError: {0}\n'.format(msg)]

    def test_format_exception(self):
        out = format_exception(self.error)
        self.assertEqual(out.splitlines(True), self.out_header + flatten(self.out_frames) + self.out_error)

    def test_format_exception_truncated(self):
        out = format_exception(self.error, limit=3)
        self.assertEqual(out.splitlines(True), self.out_header + flatten(self.out_frames[-3:]) + self.out_error)

    def test_format_exception_without_stack(self):
        get_stack(self.error)[:] = []
        out = format_exception(self.error)
        self.assertEqual(out.splitlines(True), self.out_error)

    def test_format_exc_info(self):
        out = format_exc_info(*self.exc_info)
        self.assertEqual(out.splitlines(True), self.out_header + flatten(self.out_frames) + self.out_error)

    def test_format_exc_info_without_stack(self):
        get_stack(self.error)[:] = []
        out = format_exc_info(*self.exc_info)
        self.assertEqual(out, ''.join(traceback.format_exception(*self.exc_info)))

    def test_print_exc_info(self):
        out = StringIO()
        print_exc_info(*self.exc_info, file=out)
        self.assertEqual(out.getvalue().splitlines(True), self.out_header + flatten(self.out_frames) + self.out_error)

    def test_print_exc_info_to_stderr(self):
        stderr, errmock = sys.stderr, StringIO()
        sys.stderr = errmock
        try:
            print_exc_info(*self.exc_info)
        finally:
            sys.stderr = stderr
        self.assertEqual(
            errmock.getvalue().splitlines(True),
            self.out_header + flatten(self.out_frames) + self.out_error
        )

    def test_format_exception_error_with_source_unpacking(self):
        out = format_exception(ErrorWithSource(self.error, 'source'))
        self.assertEqual(out.splitlines(True), self.out_header + flatten(self.out_frames) + self.out_error)

    def test_print_exc_info_error_with_source_unpacking(self):
        out = format_exc_info(ErrorWithSource, ErrorWithSource(self.error, 'source'), self.exc_info[2])
        self.assertEqual(out.splitlines(True), self.out_header + flatten(self.out_frames) + self.out_error)

    def test_print_exc_info_without_stack_error_with_source_unpacking(self):
        get_stack(self.error)[:] = []
        out = format_exc_info(ErrorWithSource, ErrorWithSource(self.error, 'source'), self.exc_info[2])
        self.assertEqual(out, ''.join(traceback.format_exception(*self.exc_info)))

    def test_unicode(self):
        stack = [
            Frame('entity', 'entity', Position(0, 0, Origin('ęą', 'łł.l20n')))
        ]
        attach_stack(self.error)[:] = stack
        out = format_exception(self.error)
        self.assertTrue(isinstance(out, unicode))


class TestStackTraceAccess(unittest.TestCase):
    def setUp(self):
        self.stack = [Frame(10, 11, None)]
        self.error = ValueError('sample error')

    def test_get_stack_when_unattached(self):
        self.assertEqual(get_stack(self.error), [])
        self.assertFalse(get_stack(self.error) is get_stack(self.error))

    def test_get_stack_error_with_source_unpacking(self):
        attach_stack(self.error)[:] = self.stack
        self.assertEqual(get_stack(ErrorWithSource(self.error, 'source')), self.stack)


if __name__ == '__main__':
    unittest.main()
