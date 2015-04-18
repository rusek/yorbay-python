#!/usr/bin/env python

import os
import sys
import unittest

DIR = os.path.dirname(os.path.abspath(__file__))

sys.path[0] = os.path.dirname(DIR)

from yorbay.lang import get_lang_chain


class TestLangChain(unittest.TestCase):
    def test_get_lang_chain(self):
        self.assertEqual(get_lang_chain('root'), ['root'])
        self.assertEqual(get_lang_chain('en'), ['en', 'root'])
        self.assertEqual(get_lang_chain('en_US'), ['en_US', 'en', 'root'])
        self.assertEqual(get_lang_chain('en_US_POSIX'), ['en_US_POSIX', 'en_US', 'en', 'root'])


if __name__ == '__main__':
    unittest.main()
