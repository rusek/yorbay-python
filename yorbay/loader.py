import codecs
import os.path
import posixpath

from .exceptions import BuildError


class LoaderError(BuildError):
    pass


class Loader(object):
    """
    Class implementing resource loading and path manipulation.

    For maximum flexibility, loader interface introduces a notion of "prepared paths". A prepared
    path may be of any hashable type chosen by the loader implementation.

    To obtain human-readable representation of the prepared path, format_path method must be called.
    Formatted paths are needed merely for displaying errors / warnings and cannot be used for retrieving
    further resources (even if passed first to prepare_path method).
    """
    def prepare_path(self, path):
        """
        Prepare an external path before calling prepare_import_path with the given path as base argument
        or loading the resource.

        If a resource is compiled directly from source string, then its unprepared path is an empty string.
        """
        raise NotImplementedError

    def prepare_import_path(self, base, path):
        """
        Prepare a path obtained from an import statement.

        The value of base argument must be a prepared path.
        """
        raise NotImplementedError

    def load_source(self, path):
        """
        Load a resource referenced by a given (prepared) path.

        Raises LoaderError if resource could not be retrieved or does not exist.
        """
        raise NotImplementedError

    def format_path(self, path):
        """
        Return a human-readable representation of a path.
        """
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
        try:
            with codecs.open(path, encoding=self._encoding) as f:
                return f.read()
        except IOError as e:
            raise LoaderError(str(e))
        except UnicodeDecodeError as e:
            raise LoaderError(str(e))

    def format_path(self, path):
        return path


class PosixPathLoader(Loader):
    def prepare_path(self, path):
        return posixpath.normpath(posixpath.join('/', path))

    def prepare_import_path(self, base, path):
        return posixpath.normpath(posixpath.join(posixpath.dirname(base), path))

    def format_path(self, path):
        return path
