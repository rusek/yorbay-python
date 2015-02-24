from __future__ import unicode_literals

import sys
import traceback

from ..compiler import ErrorWithSource


def get_stack(exc):
    if isinstance(exc, ErrorWithSource):
        exc = exc.cause

    try:
        return exc.yorbay_stack
    except AttributeError:
        return []


def attach_stack(exc):
    if isinstance(exc, ErrorWithSource):
        exc = exc.cause

    try:
        return exc.yorbay_stack
    except AttributeError:
        stack = exc.yorbay_stack = []
        return stack


def format_exc_info(exc_type, exc_value, exc_tb, limit=None):
    if isinstance(exc_value, ErrorWithSource):
        exc_value = exc_value.cause
        exc_type = type(exc_value)

    if get_stack(exc_value):
        return format_exception(exc_value, limit)
    else:
        return ''.join(traceback.format_exception(exc_type, exc_value, exc_tb, limit))


def print_exc_info(exc_type, exc_value, exc_tb, limit=None, file=None):
    if file is None:
        file = sys.stderr
    file.write(format_exc_info(exc_type, exc_value, exc_tb, limit))


def format_exception(exc, limit=None):
    if isinstance(exc, ErrorWithSource):
        exc = exc.cause

    buf = []
    stack = getattr(exc, 'yorbay_stack', None)

    if stack:
        if limit is not None:
            stack = stack[:limit]

        buf.append('Traceback (most recent call last):\n')
        for frame in reversed(stack):
            pos = frame.pos
            if pos is None:
                buf.append('  In {0} {1}\n'.format(
                    frame.entry_type,
                    frame.entry_name
                ))
            else:
                origin = pos.origin
                if origin is None or not origin.path:
                    buf.append('  Line {0} in {1} {2}\n'.format(
                        pos.line + 1,
                        frame.entry_type,
                        frame.entry_name
                    ))
                else:
                    buf.append('  File {0}, line {1} in {2} {3}\n'.format(
                        origin.path,
                        pos.line + 1,
                        frame.entry_type,
                        frame.entry_name
                    ))
                if origin is not None:
                    buf.append('    {0}\n'.format(origin.lines[pos.line]))

    buf.append('{0}: {1}\n'.format(type(exc).__name__, exc))

    return ''.join(buf)


class Frame(object):
    def __init__(self, entry_type, entry_name, pos):
        self.entry_type = entry_type
        self.entry_name = entry_name
        self.pos = pos

    def __repr__(self):
        return 'Frame({0!r}, {1!r}, {2!r}'.format(self.entry_type, self.entry_name, self.pos)
