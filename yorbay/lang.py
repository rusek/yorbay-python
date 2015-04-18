from __future__ import unicode_literals

import locale


def get_lang_chain(lang):
    chain = []
    if lang != 'root':
        pos = len(lang)
        while pos != -1:
            chain.append(lang[:pos])
            pos = lang.rfind('_', 0, pos)
    chain.append('root')
    return chain


_default_lang_cache = None


def get_default_lang():
    global _default_lang_cache

    lang = _default_lang_cache
    if lang is None:
        lang = locale.getlocale()[0] or locale.getdefaultlocale()[0] or 'root'
        _default_lang_cache = lang
    return lang


def reset_default_lang_cache():
    global _default_lang_cache

    _default_lang_cache = None


def prepare_lang_lazy(lang):
    if lang is None:
        return get_default_lang
    elif isinstance(lang, basestring):
        return lambda: lang
    elif callable(lang):
        return lang
    else:
        raise TypeError('Invalid lang type: {0!r}'.format(lang))
