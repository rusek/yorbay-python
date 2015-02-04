import codecs
import os.path
import posixpath


class Loader(object):
    def prepare_path(self, path):
        raise NotImplementedError

    def prepare_import_path(self, base, path):
        raise NotImplementedError

    def load_source(self, path):
        raise NotImplementedError


class FsLoader(Loader):
    def __init__(self, base=None, encoding=None):
        self._base = os.path.abspath('' if base is None else base)
        self._encoding = 'UTF-8' if encoding is None else encoding

    def prepare_path(self, path):
        if path:
            return os.path.normpath(os.path.join(self._base, path))
        else:
            # Trailing os.path.sep is needed for prepare_import_path to work
            # properly (it always calls os.path.dirname on base path)
            return os.path.join(self._base, '')

    def prepare_import_path(self, base, path):
        return os.path.normpath(os.path.join(os.path.dirname(base), path))

    def load_source(self, path):
        with codecs.open(path, encoding=self._encoding) as f:
            return f.read()


class PosixPathLoader(Loader):
    def prepare_path(self, path):
        return posixpath.normpath(posixpath.join('/', path))

    def prepare_import_path(self, base, path):
        return posixpath.normpath(posixpath.join(posixpath.dirname(base), path))
