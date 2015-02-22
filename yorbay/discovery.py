from __future__ import unicode_literals

import codecs
import collections
import os.path
import pkgutil
import sys

pkg_resources = None  # lazily loaded, as it is not a part of standard library

from .builder import build_from_path
from .exceptions import BuildError
from .lang import get_fallback_chain, get_fallback_chain_with_generation
from .loader import SimpleLoader, LoaderError, resolve_simple_path


class DiscoveryError(BuildError):
    pass


def is_package(module_name):
    module_loader = pkgutil.get_loader(module_name)
    if module_loader is None:
        raise DiscoveryError('Could not find or import module {0}'.format(module_name))
    if not hasattr(module_loader, 'is_package'):
        raise DiscoveryError('Module loader does not implement is_package method')

    return module_loader.is_package(module_name)


def get_discovery_loader(module_name):
    path = 'locale'
    discoverer = PkgResourcesDiscoverer()

    if not is_package(module_name):
        module_name = module_name.rsplit('.')[0]

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


class LazyBuilder(object):
    def __init__(self, loader, debug):
        self._loader = loader
        self._cache = None, None
        self._debug = debug

    def __call__(self):
        langs, gen = get_fallback_chain_with_generation()

        l20n, cached_gen = self._cache
        if cached_gen is gen:
            return l20n

        path = get_path(self._loader, langs)
        if path is None:
            raise DiscoveryError('Could not find translations, tried languages: {0}'.format(langs))

        l20n = build_from_path(path, self._loader, cache=self._loader.cache, debug=self._debug)
        self._cache = l20n, gen

        return l20n


def build_from_module_lazy(name, debug=False):
    loader = get_discovery_loader(name)
    if loader is None:
        raise DiscoveryError('Could not find suitable discovery loader for {0}'.format(name))

    return LazyBuilder(loader, debug=debug)


class PkgResourcesDiscoverer(object):
    def __init__(self):
        global pkg_resources

        if pkg_resources is None:
            import pkg_resources as pkg_resources_module
            pkg_resources = pkg_resources_module

    def get_discovery_loader(self, module_name, path):
        if pkg_resources.resource_exists(module_name, path):
            return PkgResourceLoader(module_name, path)


_builder_cache = collections.defaultdict(dict)


def get_module_format_path_prefix(module_name):
    try:
        module = sys.modules[module_name]
    except KeyError:
        __import__(module_name)
        module = sys.modules[module_name]
    module_dir = os.path.dirname(getattr(module, '__file__', ''))
    return module_dir + os.sep if module_dir else ''


class PkgResourceLoader(SimpleLoader):
    def __init__(self, module_name, prefix):
        super(PkgResourceLoader, self).__init__()
        prefix = resolve_simple_path('', prefix + '/')

        self._module_name = module_name
        self._prefix = prefix
        self._format_prefix = get_module_format_path_prefix(module_name) + prefix.replace('/', os.sep)
        self.cache = _builder_cache[(module_name, prefix)]

    def exists(self, path):
        return pkg_resources.resource_exists(self._module_name, self._prefix + path)

    def load_source(self, path):
        try:
            return codecs.decode(pkg_resources.resource_string(self._module_name, self._prefix + path), 'UTF-8')
        except StandardError as e:
            raise LoaderError(str(e))

    def format_path(self, path):
        return self._format_prefix + path.replace('/', os.sep)
