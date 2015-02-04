#!/usr/bin/env python

import os
import sys
import unittest

DIR = os.path.dirname(os.path.abspath(__file__))

sys.path[0] = os.path.dirname(DIR)

from yorbay.loader import FsLoader, PosixPathLoader


class TestFsLoader(unittest.TestCase):
    def setUp(self):
        self.dir1 = os.path.join('a', 'b')
        self.path1 = os.path.join(self.dir1, 'path1')
        self.path2 = os.path.join('c', 'path2')

    def test_prepared_paths_are_absolute(self):
        loader = FsLoader()

        prep_path1 = loader.prepare_path(self.path1)
        self.assertTrue(os.path.isabs(prep_path1))
        self.assertEqual(prep_path1, os.path.join(os.getcwd(), self.path1))

        prep_path2 = loader.prepare_import_path(prep_path1, self.path2)
        self.assertTrue(os.path.isabs(prep_path2))
        self.assertEqual(prep_path2, os.path.join(os.getcwd(), self.dir1, self.path2))

    def test_prepared_paths_are_not_affected_by_chdir(self):
        cwd = os.getcwd()
        os.chdir(DIR)
        try:
            loader = FsLoader()
            os.chdir(os.path.dirname(DIR))

            prep_path1 = loader.prepare_path(self.path1)
            self.assertEqual(prep_path1, os.path.join(DIR, self.path1))

            prep_path2 = loader.prepare_import_path(prep_path1, self.path2)
            self.assertEqual(prep_path2, os.path.join(DIR, self.dir1, self.path2))
        finally:
            os.chdir(cwd)

    def test_prepared_paths_starting_with_empty_path(self):
        loader = FsLoader()

        prep_path1 = loader.prepare_path('')
        self.assertTrue(prep_path1.endswith(os.path.sep), msg=prep_path1)

        prep_path2 = loader.prepare_import_path(prep_path1, self.path2)
        self.assertEqual(prep_path2, os.path.join(os.getcwd(), self.path2))


class TestPosixPathLoader(unittest.TestCase):
    def setUp(self):
        self.loader = PosixPathLoader()

    def test_prepare_path(self):
        self.assertEqual(self.loader.prepare_path('aaa'), '/aaa')
        self.assertEqual(self.loader.prepare_path('/xyz'), '/xyz')
        self.assertEqual(self.loader.prepare_path('/a/b/../c/./d'), '/a/c/d')
        self.assertEqual(self.loader.prepare_path('..'), '/')

    def test_prepare_import_path(self):
        self.assertEqual(self.loader.prepare_import_path('/f1.l20n', 'f2.l20n'), '/f2.l20n')
        self.assertEqual(self.loader.prepare_import_path('/a/f1.l20n', '../f2.l20n'), '/f2.l20n')
        self.assertEqual(self.loader.prepare_import_path('/a/f1.l20n', '../../f2.l20n'), '/f2.l20n')
        self.assertEqual(self.loader.prepare_import_path('/a/f1.l20n', 'b/f2.l20n'), '/a/b/f2.l20n')


if __name__ == '__main__':
    unittest.main()
