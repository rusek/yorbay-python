from __future__ import unicode_literals

import codecs
import os.path

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


class SimpleLoader(Loader):
    """
    Base class for loaders that use URI-like paths. Such paths are suitable for use e.g. with
    pkgutil.get_data function.

    Path components are separated by '/'. Prepared paths never start with '/' and do not contain
    '.' and '..'. Multiple successive slashes are compressed to a single slash, which is not the
    case for URI paths. Prepared path may be empty. It can also contain a trailing slash.
    """

    def __init__(self, base=''):
        self._base = resolve_simple_path('', base)

    def prepare_path(self, path):
        return resolve_simple_path(self._base, path)

    def prepare_import_path(self, base, path):
        return resolve_simple_path(base, path)

    def format_path(self, path):
        return path


def resolve_simple_path(base, path):
    if not path:
        return base

    if path.startswith('/'):
        segs = path.split('/')
    else:
        segs = base.split('/')[:-1] + path.split('/')

    out = []

    for seg in segs:
        if seg == '..':
            if out:
                out.pop()
        elif seg not in ('', '.'):
            out.append(seg)

    if segs[-1] in ('.', '', '..'):
        out.append('')

    return '/'.join(out)
