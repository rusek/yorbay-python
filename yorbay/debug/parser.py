from ..parser import Tokenizer, Parser
from .. import syntax


class Origin(object):
    def __init__(self, s, path):
        self.lines = s.splitlines()
        self.path = path


class DebugTokenizer(Tokenizer):
    def __init__(self, s, path):
        super(DebugTokenizer, self).__init__(s, Origin(s, path))


class DebugParser(Parser):
    def __init__(self, tokenizer):
        self._pos_stack = []
        super(DebugParser, self).__init__(tokenizer)

    def push_pos(self):
        self._pos_stack.append(self.pos)

    def put_pos(self, node, shift=0):
        pos = self._pos_stack[-1]
        if shift:
            pos = syntax.Position(pos.line, pos.column + shift, pos.origin)
        node.pos = pos
        return node

    def pop_pos(self, node):
        node.pos = self._pos_stack.pop()
        return node

    def next_token_pp(self):
        self.next_token()
        self.push_pos()

    def pp_next_token_pp(self):
        self.push_pos()
        self.next_token()
        self.push_pos()

    def skip_token_pp(self, type):
        self.skip_token(type)
        self.push_pos()

    def try_skip_token_pp(self, type, allow_ws_before=True):
        ret = self.try_skip_token(type, allow_ws_before)
        if ret:
            self.push_pos()
        return ret

    def pp_try_skip_token_pp(self, type, allow_ws_before=True):
        pos = self.pos
        ret = self.try_skip_token(type, allow_ws_before)
        if ret:
            self._pos_stack.append(pos)
            self.push_pos()
        return ret

    def drop_pos(self):
        self._pos_stack.pop()

    def parse_l20n(self):
        ret = super(DebugParser, self).parse_l20n()
        assert not self._pos_stack
        return ret
