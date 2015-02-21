from __future__ import unicode_literals

import locale


class Generation(object):
    pass


_state = None, None


def reset():
    global _state
    _state = None, None


def get_lang():
    return get_fallback_chain_with_generation()[0][0]


def get_lang_with_generation():
    langs, gen = get_fallback_chain_with_generation()
    return langs[0], gen


def get_fallback_chain():
    return get_fallback_chain_with_generation()[0]


def get_fallback_chain_with_generation():
    global _state

    langs, gen = _state
    if gen is None:
        langs, gen = _default()
        _state = langs, gen

    return langs, gen


def _default():
    lang = locale.getlocale()[0] or locale.getdefaultlocale()[0] or 'en'

    parts = lang.split('_')
    langs = ['_'.join(parts[:i]) for i in reversed(xrange(1, len(parts) + 1))]
    if langs[-1] != 'en':
        langs.append('en')

    return langs, Generation()
