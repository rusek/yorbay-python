#!/usr/bin/env python
# coding=utf-8

import os
import sys
import unittest

DIR = os.path.dirname(os.path.abspath(__file__))

sys.path[0] = os.path.dirname(DIR)

from yorbay.debug.similarity import osa_distance


class TestOsaDistance(unittest.TestCase):
    def test_equal(self):
        self.assertEqual(osa_distance('abcdef', 'abcdef'), 0)

    def test_character_removed(self):
        s = 'abcdef'
        for i in xrange(len(s)):
            self.assertEqual(osa_distance(s, s[:i] + s[i + 1:]), 1)

    def test_character_added(self):
        s = 'abcdef'
        for i in xrange(len(s)):
            self.assertEqual(osa_distance(s, s[:i] + 'z' + s[i:]), 1)

    def test_characters_swapped(self):
        s = 'abcdef'
        for i in xrange(len(s) - 1):
            self.assertEqual(osa_distance(s, s[:i] + s[i + 1] + s[i] + s[i + 1:]), 1)

    def test_multiple_changes(self):
        self.assertEqual(osa_distance('abc', 'cba'), 2)
        self.assertEqual(osa_distance('abcdef', 'bacdf'), 2)

    def test_unicode(self):
        self.assertEqual(osa_distance(u'a', 'a'), 0)
        self.assertEqual(osa_distance(u'aęą', u'aąę'), 1)


if __name__ == '__main__':
    unittest.main()
