import codecs
import collections
import os
import pkgutil
import posixpath
import sys
import zipimport

pkg_resources = None  # lazily loaded, as it is not a part of standard library

from .builder import build_from_path
from .compiler import LazyCompiledL20n
from .exceptions import BuildError
from .lang import get_fallback_chain, get_fallback_chain_with_generation
from .loader import LoaderError, PosixPathLoader


class DiscoveryError(BuildError):
    pass


def get_module(module_name):
    try:
        return sys.modules[module_name]
    except KeyError:
        __import__(module_name)
        return sys.modules[module_name]


def get_discovery_loader(module_name):
    path = 'locale'
    discoverer = PkgResourcesDiscoverer()

    while True:
        discovery_loader = discoverer.get_discovery_loader(module_name, path)
        if discovery_loader is not None:
            return discovery_loader

        pos = module_name.rfind('.')
        if pos == -1:
            return None

        module_name = module_name[:pos]


def get_path(loader, langs):
    for lang in langs:
        for path in ('{0}.l20n'.format(lang), '{0}/main.l20n'.format(lang)):
            if loader.exists(path):
                return path
    return None


def build_from_module(name, langs=None):
    if langs is None:
        langs = get_fallback_chain()

    loader = get_discovery_loader(name)
    if loader is None:
        raise DiscoveryError('Could not find suitable discovery loader for {0}'.format(name))

    path = get_path(loader, langs)
    if path is None:
        raise DiscoveryError('Could not find translations for module {0}, tried languages: {1}'.format(name, langs))

    return build_from_path(path, loader, cache=loader.cache)


class LazyBuilder(LazyCompiledL20n):
    def __init__(self, loader):
        self._loader = loader
        self._cache = None, None

    def get(self):
        langs, gen = get_fallback_chain_with_generation()

        l20n, cached_gen = self._cache
        if cached_gen is gen:
            return l20n

        path = get_path(self._loader, langs)
        if path is None:
            raise DiscoveryError('Could not find translations, tried languages: {0}'.format(langs))

        l20n = build_from_path(path, self._loader, cache=self._loader.cache)
        self._cache = l20n, gen

        return l20n


def build_from_module_lazy(name):
    loader = get_discovery_loader(name)
    if loader is None:
        raise DiscoveryError('Could not find suitable discovery loader for {0}'.format(name))

    return LazyBuilder(loader)


class PkgResourcesDiscoverer(object):
    def __init__(self):
        global pkg_resources

        if pkg_resources is None:
            import pkg_resources as pkg_resources_module
            pkg_resources = pkg_resources_module

    def get_discovery_loader(self, module_name, path):
        if pkg_resources.resource_exists(module_name, path):
            return PkgResourceLoader(module_name, path)


def get_resource_key(module_name):
    """
    Return a key (hashable object) that uniquely identifies resources linked to the specified
    module. For example, modules coming from a single package may share the same resources,
    so their resource keys should be equal.
    """
    module = get_module(module_name)
    module_loader = getattr(module, '__loader__', None)

    # These loaders provide same resources for all modules coming from a single package
    # (or at least the seem to provide) - it would be a waste of space to keep multiple
    # instances of identical translation files in memory.
    if isinstance(module_loader, (type(None), zipimport.zipimporter, pkgutil.ImpLoader)):
        # __file__ is not set for interactive session
        return 'f:' + os.path.dirname(getattr(module, '__file__', ''))
    # Otherwise, let's assume that each module has independent resources
    else:
        return 'n:' + module.__name__


_builder_cache = collections.defaultdict(dict)


class PkgResourceLoader(PosixPathLoader):
    def __init__(self, module_name, prefix):
        self._module_name = module_name
        self._prefix = prefix
        self.cache = _builder_cache[(get_resource_key(module_name), prefix)]

    def exists(self, path):
        return pkg_resources.resource_exists(self._module_name, posixpath.join(self._prefix, path))

    def load_source(self, path):
        try:
            return codecs.decode(pkg_resources.resource_string(self._module_name, self._prefix + path), 'UTF-8')
        except StandardError as e:
            raise LoaderError(str(e))
