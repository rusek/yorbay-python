#!/usr/bin/env python

import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

DIR = os.path.dirname(os.path.abspath(__file__))

sys.path[:0] = [os.path.dirname(DIR)]

from yorbay.discovery import DiscoveryError


# Taken from locale.getdefaultlocale
locale_envvars = ('LC_ALL', 'LC_CTYPE', 'LANG', 'LANGUAGE')

_sample_zip_path = None


def get_sample_zip_path():
    global _sample_zip_path
    if _sample_zip_path is None:
        fd, _sample_zip_path = tempfile.mkstemp('.zip', dir=os.path.dirname(DIR))
        os.close(fd)

        zipdir = os.path.join(DIR, 'samples', 'discovery')
        arch = zipfile.ZipFile(_sample_zip_path, 'w')
        try:
            for root, dirs, files in os.walk(zipdir):
                if root != zipdir:
                    rel = os.path.relpath(root, zipdir)
                else:
                    rel = ''
                for file in files:
                    if file.endswith('.py') or file.endswith('.l20n'):
                        arch.write(os.path.join(root, file), os.path.join(rel, file).replace(os.sep, '/'))
        finally:
            arch.close()

    return _sample_zip_path


def clean_sample_zip():
    global _sample_zip_path
    if _sample_zip_path is not None:
        os.remove(_sample_zip_path)
        _sample_zip_path = None


class ExecutionError(Exception):
    pass


class TestStandardModuleLoader(unittest.TestCase):
    def test_exact_discovery(self):
        self.assertEqual(
            self.execute('tr', 'hello', lang='pl_PL'),
            'PL hello from discovery/locale'
        )
        self.assertEqual(
            self.execute('sub_mod1_tr', 'hello', lang='pl_PL'),
            'pl_PL hello from discovery/sub/locale/pl_PL'
        )
        self.assertEqual(
            self.execute('sub_mod2_tr', 'hello', lang='pl_PL'),
            'pl_PL hello from discovery/sub/locale/pl_PL'
        )
        self.assertEqual(
            self.execute('sub_sub3_tr', 'hello', lang='en'),
            'en hello from discovery/sub/sub3/locale'
        )
        self.assertEqual(
            self.execute('sub_sub3_mod_tr', 'hello', lang='en'),
            'en hello from discovery/sub/sub3/locale'
        )

    def test_root_lookup(self):
        self.assertEqual(
            self.execute('tr', 'hello', lang=None),
            'ROOT hello from discovery/locale',
        )
        self.assertRaises(DiscoveryError, self.execute, 'sub_mod1_tr', 'hello', lang='de_DE')

    def execute(self, *args, **kwargs):
        return self._vexecute(args, **kwargs)

    def _prog(self):
        return '__main__.py'

    def _vexecute(self, args, lang=None):
        env = {}
        for k, v in os.environ.iteritems():
            if k not in locale_envvars:
                env[k] = v
        if lang:
            env['LANG'] = lang
        env['PYTHONPATH'] = os.path.dirname(DIR)

        process = subprocess.Popen(
            ('python', self._prog()) + args,
            stdout=subprocess.PIPE,
            cwd=os.path.join(DIR, 'samples', 'discovery'),
            env=env,
        )
        out, _ = process.communicate()
        if process.poll():
            raise ExecutionError('Process returned non-zero exit code')

        err, arg = out.split(':', 1)
        if err:
            mod, cls = err.rsplit('.', 1)
            __import__(mod)
            raise getattr(sys.modules[mod], cls)(arg)
        else:
            return arg.strip()


class TestZipModuleLoader(TestStandardModuleLoader):
    def _prog(self):
        return get_sample_zip_path()


if __name__ == '__main__':
    try:
        unittest.main()
    finally:
        clean_sample_zip()
