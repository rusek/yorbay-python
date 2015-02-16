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


def format_exception(exc):
    if isinstance(exc, ErrorWithSource):
        exc = exc.cause

    buf = []
    stack = getattr(exc, 'yorbay_stack', None)

    if stack:
        buf.append('Traceback (most recent call last):\n')
        for frame in reversed(stack):
            buf.append('  File {0}, line {1} in {2} {3}\n'.format(
                frame.pos.origin.path,
                frame.pos.line + 1,
                frame.entry_type,
                frame.entry_name
            ))
            buf.append('    {0}\n'.format(frame.pos.origin.lines[frame.pos.line]))

    buf.append('{0}: {1}\n'.format(type(exc).__name__, exc))

    return ''.join(buf)


class Frame(object):
    def __init__(self, entry_type, entry_name, pos):
        self.entry_type = entry_type
        self.entry_name = entry_name
        self.pos = pos
