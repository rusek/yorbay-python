from . import syntax

import re


_token_re = re.compile(r'''
    ([ \n\r\t]+)|  # group 1: whitespace
    (/\*)|  # group 2: comment start
    ([@$]?[a-zA-Z_][a-zA-Z0-9_]*)|  # group 3: identifiers
    (::\[|::|==|!=|<=|>=|&&|\|\||[?!:<>(){}[\]+\-*/%~,\.])|  # group 4: symbols
    ("(?:"")?|'(?:'')?)|  # group 5: string start
    (\d+)  # group 6: number
''', re.VERBOSE)

_safe_str_chars_re = re.compile(r'''[^{'"\\]+''')


class ParserError(Exception):
    def __init__(self, msg, pos):
        super(ParserError, self).__init__('Line {0}: {1}'.format(pos.line + 1, msg))
        self.pos = pos


# Token types:
#   ? : < > ( ) { } + - * / % == != < > <= >= ! :: ~ && || , .
#   eof ident var str_start num glob ws comment
# Text token types:
#   eof {{ expr_start str_end str
class Token(object):
    def __init__(self, type, value):
        self.type = type
        self.value = value


class Tokenizer(object):
    def __init__(self, source, origin=None):
        self._s = source
        self._origin = origin
        self._pos = 0  # current position in input string
        self._line = 0  # current line (counting from zero)
        self._line_start = 0  # position where current line starts
        self._size = len(source)

    def get_offset(self):
        return self._pos

    def get_position(self):
        return syntax.Position(self._line, self._pos - self._line_start, self._origin)

    def get_source(self, start, end):
        return self._s[start:end]

    def _linescan(self):
        pos = self._s.rfind('\n', self._line_start, self._pos)
        if pos != -1:
            self._line += self._s.count('\n', self._line_start, pos) + 1
            self._line_start = pos + 1

    def next_token(self):
        if self._pos == self._size:
            return Token('eof', None)

        match = _token_re.match(self._s, self._pos)
        if not match:
            raise ParserError('Unrecognized character: "{0}"'.format(self._s[self._pos]), pos=self.get_position())

        self._pos = match.end()
        if match.start(1) != -1:
            type, value = 'ws', None
            self._linescan()
        elif match.start(2) != -1:
            comment_end = self._s.find('*/', self._pos)
            if comment_end == -1:
                self._pos = self._size
                self._linescan()
                raise ParserError('Unclosed comment', pos=self.get_position())
            type, value = 'comment', self._s[self._pos: comment_end]
            self._pos = comment_end + 2  # skip '*/'
            self._linescan()
        elif match.start(3) != -1:
            ident = match.group(3)
            if ident[0] == '@':
                type, value = 'glob', ident[1:]
            elif ident[0] == '$':
                type, value = 'var', ident[1:]
            else:
                type, value = 'ident', ident
        elif match.start(4) != -1:
            type, value = match.group(4), None
        elif match.start(5) != -1:
            type, value = 'str_start', match.group(5)
        else:
            type, value = 'num', int(match.group(6))

        return Token(type, value)

    def next_text_token(self, delim):
        if self._pos == self._size:
            return Token('eof', None)

        if self._s[self._pos: self._pos + len(delim)] == delim:
            type, value = 'str_end', None
            self._pos += len(delim)
        elif self._s[self._pos: self._pos + 2] == '{{':
            type, value = 'expr_start', None
            self._pos += 2
        elif self._s[self._pos] == '\\':
            type = 'str'
            value, size = self._parse_escape()
            self._pos += size
            self._linescan()
        else:
            type, value = 'str', self._s[self._pos]
            match = _safe_str_chars_re.match(self._s, self._pos + 1)
            if match:
                value += match.group()
                self._pos = match.end()
            else:
                self._pos += 1
            self._linescan()

        return Token(type, value)

    def _parse_escape(self):
        if self._size - self._pos < 2:
            raise ParserError('Invalid escape', pos=self.get_position())
        c = self._s[self._pos + 1]
        if c == 'u':
            uarg = self._parse_u_escape_arg(2)
            if 0xd800 <= uarg <= 0xdbff:  # high surrogate
                if self._s[self._pos + 6: self._pos + 8] != '\\u':
                    raise ParserError('Invalid escape - missing low surrogate', pos=self.get_position())
                uarg2 = self._parse_u_escape_arg(8)
                if 0xdc00 <= uarg2 <= 0xdfff:  # low surrogate
                    return unichr(0x10000 + (((uarg - 0xd800) << 10) | (uarg2 - 0xdc00))), 12
                else:
                    raise ParserError(
                        'Invalid escape - not a low surrogate',
                        pos=syntax.Position(self._line, self._pos + 6 - self._line_start, self._origin)
                    )
            elif 0xdc00 <= uarg <= 0xdfff:  # low surrogate
                raise ParserError('Invalid escape - low surrogate', pos=self.get_position())
            else:
                return unichr(uarg), 6
        else:
            return c, 2

    def _parse_u_escape_arg(self, shift):
        cs = self._s[self._pos + shift: self._pos + shift + 4]
        if len(cs) == 4 and cs[1] not in 'xX':
            try:
                return int(cs, 16)
            except ValueError:
                pass
        raise ParserError('Invalid escape', pos=self.get_position())


def describe_token(token):
    if token.type in ('ident', 'num'):
        return '"{0}"'.format(token.value)
    elif token.type == 'var':
        return '"${0}"'.format(token.value)
    elif token.type == 'glob':
        return '"@{0}"'.format(token.value)
    elif token.type == 'str_start':
        return 'string'
    else:
        return '"{0}"'.format(token.type)


def describe_token_type(type):
    return '"{0}"'.format(type)


class Parser(object):
    # A few notes on tracking position for constructed nodes:
    #   - positions for constructed nodes are kept on stack (in DebugParser, this class actually do not record
    #     the positionf for nodes)
    #   - each parse_* method (except for parse_*_tail methods, which behave a lit differently) assumes
    #     that the position of the current token is pushed onto the stack and is responsible for poping it
    #     before returning
    #   - parse_*_tail methods assume that there are at least two positions pushed onto the stack: the top
    #     position should belong to the current token while the second one should become the position of the
    #     returned node
    def __init__(self, tokenizer):
        self._tokenizer = tokenizer
        self.token = None
        self.pos = self._tokenizer.get_position()
        self.push_pos()
        self.ws_before = False
        self.next_token()

    def next_token(self):
        pos = self._tokenizer.get_position()
        token = self._tokenizer.next_token()
        if token.type == 'ws':
            ws_before = True
            pos = self._tokenizer.get_position()
            token = self._tokenizer.next_token()
        else:
            ws_before = False
        self.pos = pos
        self.token = token
        self.ws_before = ws_before

    next_token_pp = next_token
    pp_next_token_pp = next_token

    def next_text_token(self, delim):
        self.pos = self._tokenizer.get_position()
        self.token = self._tokenizer.next_text_token(delim)
        self.ws_before = False

    def error(self, msg):
        return ParserError(msg, pos=self.pos)

    def error_expected(self, desc):
        if self.token.type == 'comment':
            return self.error('Comments can be used only as top-level entries')
        elif self.token.type == 'eof':
            return self.error('Expected {0}, but end of input reached'.format(desc))
        else:
            cur_desc = describe_token(self.token)

            return self.error('Expected ' + desc + ', but got ' + cur_desc + ' instead')

    def skip_token(self, type):
        if self.token.type == type:
            self.next_token()
        else:
            raise self.error_expected(describe_token_type(type))

    skip_token_pp = skip_token

    def try_skip_token(self, type, allow_ws_before=True):
        if self.token.type == type:
            if not allow_ws_before and self.ws_before:
                raise self.error('Unexpected white space before ' + describe_token(self.token))
            self.next_token()
            return True
        else:
            return False

    try_skip_token_pp = try_skip_token
    pp_try_skip_token_pp = try_skip_token

    def push_pos(self):
        pass

    def put_pos(self, node, shift=0):
        return node

    def pop_pos(self, node):
        return node

    def drop_pos(self):
        pass

    def parse_l20n(self):
        entries = []

        while self.token.type != 'eof':
            self.push_pos()
            entries.append(self.parse_entry())

        return self.pop_pos(syntax.L20n(entries))

    def parse_entry(self):
        if self.token.type == '<':
            self.next_token_pp()
            if self.token.type == 'ident' and self.ws_before:
                raise self.error('Unexpected white space between "<" and entity/macro name')
            ident = self.parse_identifier()
            if self.token.type == '(':
                if self.ws_before:
                    raise self.error('Unexpected white space between macro name and "("')
                self.next_token_pp()
                return self.parse_macro_tail(ident)
            else:
                if self.token.type == '[':
                    if self.ws_before:
                        raise self.error('Unexpected white space between entity name and "["')
                    self.next_token_pp()
                    index = self.parse_item_list(self.parse_expression, ']')
                else:
                    index = None
                self.push_pos()
                return self.parse_entity_tail(ident, index)

        if self.token.type == 'comment':
            content = self.token.value
            self.next_token()
            return self.pop_pos(syntax.Comment(content))

        if self.token.type == 'ident' and self.token.value == 'import':
            self.next_token()
            return self.parse_import()

        raise self.error_expected('entry')

    def parse_identifier(self):
        if self.token.type != 'ident':
            raise self.error_expected('identifier')
        name = self.token.value
        self.next_token()
        return self.pop_pos(syntax.Identifier(name))

    def parse_macro_tail(self, ident):
        if ident.name[0] == '_':
            raise self.error('Macro identifier cannot start with "_"')
        args = self.parse_item_list(self.parse_variable, ')')
        self.skip_token_pp('{')
        exp = self.parse_expression()
        self.skip_token('}')
        self.skip_token('>')
        return self.pop_pos(syntax.Macro(ident, args, exp))

    def parse_expression(self):
        exp = self.parse_or_expression()
        if self.token.type != '?':
            return exp
        self.pp_next_token_pp()
        consequent = self.parse_expression()
        self.skip_token_pp(':')
        alternate = self.parse_expression()
        return self.pop_pos(syntax.ConditionalExpression(exp, consequent, alternate))

    def parse_or_expression(self):
        return self.parse_prefix_expression(('||', ), syntax.LogicalExpression,
                                            syntax.LogicalOperator, self.parse_and_expression)

    def parse_and_expression(self):
        return self.parse_prefix_expression(('&&', ), syntax.LogicalExpression,
                                            syntax.LogicalOperator, self.parse_equality_expression)

    def parse_equality_expression(self):
        return self.parse_prefix_expression(('==', '!='), syntax.BinaryExpression,
                                            syntax.BinaryOperator, self.parse_relational_expression)

    def parse_relational_expression(self):
        return self.parse_prefix_expression(('<', '<=', '>', '>='), syntax.BinaryExpression,
                                            syntax.BinaryOperator, self.parse_additive_expression)

    def parse_additive_expression(self):
        return self.parse_prefix_expression(('+', '-'), syntax.BinaryExpression,
                                            syntax.BinaryOperator, self.parse_modulo_expression)

    def parse_modulo_expression(self):
        return self.parse_prefix_expression(('%', ), syntax.BinaryExpression,
                                            syntax.BinaryOperator, self.parse_multiplicative_expression)

    def parse_multiplicative_expression(self):
        return self.parse_prefix_expression(('*', ), syntax.BinaryExpression,
                                            syntax.BinaryOperator, self.parse_dividive_expression)

    def parse_dividive_expression(self):
        return self.parse_prefix_expression(('/', ), syntax.BinaryExpression,
                                            syntax.BinaryOperator, self.parse_unary_expression)

    def parse_unary_expression(self):
        if self.token.type in ('+', '-', '!'):
            type = self.token.type
            self.next_token_pp()
            exp = self.parse_unary_expression()
            return self.pop_pos(syntax.UnaryExpression(self.put_pos(syntax.UnaryOperator(type)), exp))
        else:
            return self.parse_member_expression()

    def parse_member_expression(self):
        exp = self.parse_parenthesis_expression()
        while True:
            if self.pp_try_skip_token_pp('.', allow_ws_before=False):
                exp = self.parse_property_expression_tail(exp, False)
            elif self.pp_try_skip_token_pp('[', allow_ws_before=False):
                exp = self.parse_property_expression_tail(exp, True)
            elif self.pp_try_skip_token_pp('::', allow_ws_before=False):
                exp = self.parse_attribute_expression_tail(exp, False)
            elif self.pp_try_skip_token_pp('::[', allow_ws_before=False):
                exp = self.parse_attribute_expression_tail(exp, True)
            elif self.pp_try_skip_token_pp('(', allow_ws_before=False):
                exp = self.parse_call_expression_tail(exp)
            else:
                return exp

    def parse_parenthesis_expression(self):
        if self.try_skip_token_pp('('):
            exp = self.parse_expression()
            self.skip_token(')')
            return self.pop_pos(syntax.ParenthesisExpression(exp))
        else:
            return self.parse_primary_expression()

    def parse_property_expression_tail(self, expression, computed):
        if computed:
            property = self.parse_expression()
            self.skip_token(']')
        else:
            if self.token.type == 'ident' and self.ws_before:
                raise self.error('Unexpected white space between "." and property name')
            property = self.parse_identifier()
        return self.pop_pos(syntax.PropertyExpression(expression, property, computed))

    def parse_attribute_expression_tail(self, expression, computed):
        if not isinstance(expression, (syntax.ParenthesisExpression, syntax.Identifier, syntax.ThisExpression)):
            raise self.error('The left expression of attribute access must be entity name, this ("~") or parentheses')
        if computed:
            attribute = self.parse_expression()
            self.skip_token(']')
        else:
            if self.token.type == 'ident' and self.ws_before:
                raise self.error('Unexpected white space between "::" and attribute name')
            attribute = self.parse_identifier()
        return self.pop_pos(syntax.AttributeExpression(expression, attribute, computed))

    def parse_call_expression_tail(self, callee):
        args = self.parse_item_list(self.parse_expression, ')')
        return self.pop_pos(syntax.CallExpression(callee, args))

    def parse_primary_expression(self):
        if self.token.type == 'num':
            value = self.token.value
            self.next_token()
            return self.pop_pos(syntax.Number(value))
        elif self.token.type == 'ident':
            return self.parse_identifier()
        elif self.try_skip_token('~'):
            return self.pop_pos(syntax.ThisExpression())
        elif self.token.type == 'glob':
            name = self.token.value
            self.next_token()
            return self.pop_pos(syntax.GlobalsExpression(self.put_pos(syntax.Identifier(name), shift=1)))
        elif self.token.type == 'var':
            return self.parse_variable()
        else:
            value = self.parse_optional_value()
            if value is None:
                raise self.error_expected('expression')
            return value

    def parse_prefix_expression(self, types, exp_cls, op_cls, callback):
        exp = callback()
        while True:
            if self.token.type not in types:
                return exp
            type = self.token.type
            self.pp_next_token_pp()
            right = callback()
            exp = self.pop_pos(exp_cls(self.put_pos(op_cls(type)), exp, right))

    def parse_variable(self):
        if self.token.type != 'var':
            raise self.error_expected('variable')
        name = self.token.value
        self.next_token()
        return self.pop_pos(syntax.Variable(self.put_pos(syntax.Identifier(name), 1)))

    def parse_entity_tail(self, ident, index):
        if not self.ws_before:
            if index is not None:
                raise self.error('Expected white space after index')
            else:
                raise self.error('Expected white space after entity name')
        value = self.parse_optional_value()
        if self.token.type == '>':
            if value is None:
                raise self.error('Entity may not be empty')
            self.next_token()
            attrs = None
        else:
            if not self.ws_before:
                raise self.error('Expected white space after entity value')
            self.push_pos()
            attrs = self.parse_attributes()

        return self.pop_pos(syntax.Entity(ident, value, index, attrs))

    def parse_optional_value(self):
        if self.token.type == 'str_start':
            return self.parse_string()

        if self.try_skip_token('{'):
            return self.parse_hash()

        self.drop_pos()
        return None

    def parse_value(self):
        value = self.parse_optional_value()
        if value is None:
            raise self.error_expected('value')
        return value

    def parse_hash(self):
        has_def_item = False
        content = []
        while True:
            def_item = False
            if self.try_skip_token('*'):
                if has_def_item:
                    raise self.error('Default item redefinition')
                def_item = True
                has_def_item = True
            self.push_pos()
            self.push_pos()
            key, value = self.parse_kvp()
            content.append(self.pop_pos(syntax.HashItem(key, value, def_item)))
            if self.try_skip_token(','):
                pass
            elif self.try_skip_token('}'):
                return self.pop_pos(syntax.Hash(content))
            else:
                raise self.error_expected('"," or "}"')

    def parse_kvp(self):
        key = self.parse_identifier()
        self.skip_token_pp(':')
        value = self.parse_value()
        return key, value

    def parse_attributes(self):
        attrs = []

        while True:
            self.push_pos()
            key, value, index = self.parse_kvp_with_index()
            attrs.append(self.pop_pos(syntax.Attribute(key, value, index)))
            if self.try_skip_token('>'):
                return attrs
            elif not self.ws_before:
                raise self.error('Expected white space after attribute value')
            else:
                self.push_pos()

    def parse_kvp_with_index(self):
        key = self.parse_identifier()
        index = None
        if self.try_skip_token_pp('[', allow_ws_before=False):
            index = self.parse_item_list(self.parse_expression, ']')
        self.skip_token_pp(':')
        value = self.parse_value()
        return key, value, index

    def parse_import(self):
        if self.token.type != '(':
            raise self.error_expected('"("')
        if self.ws_before:
            raise self.error('Unexpected white space between "import" and "("')
        self.next_token_pp()
        uri = self.parse_string()
        if not isinstance(uri, syntax.String):
            raise self.error('Import URI must not contain placeables')
        self.skip_token(')')
        return self.pop_pos(syntax.ImportStatement(uri))

    def parse_string(self):
        if self.token.type != 'str_start':
            raise self.error_expected('string')
        delim = self.token.value
        start = self._tokenizer.get_offset()  # past string start
        self.next_text_token(delim)

        buf = []
        body = []
        while True:
            if self.token.type == 'str':
                if not buf:
                    self.push_pos()
                buf.append(self.token.value)
                self.next_text_token(delim)
            elif self.token.type == 'expr_start':
                if buf:
                    body.append(self.pop_pos(syntax.String(''.join(buf))))
                    buf = []
                self.next_token_pp()
                body.append(self.parse_expression())
                if self.token.type != '}':
                    raise self.error_expected('"}}"')
                self.next_token()
                if self.token.type != '}' or self.ws_before:
                    raise self.error_expected('"}}"')
                self.next_text_token(delim)
            elif self.token.type == 'str_end':
                end = self._tokenizer.get_offset() - len(delim)
                self.next_token()
                if not body:
                    if buf:
                        self.drop_pos()
                    return self.pop_pos(syntax.String(''.join(buf)))
                if buf:
                    body.append(self.pop_pos(syntax.String(''.join(buf))))
                return self.pop_pos(syntax.ComplexString(body, self._tokenizer.get_source(start, end)))
            elif self.token.type == 'eof':
                raise self.error('Unclosed string')
            else:
                raise AssertionError('Invalid text token type: %s' % self.token.type)

    def parse_item_list(self, callback, close_type):
        if self.try_skip_token(close_type):
            self.drop_pos()
            return []

        items = []
        while True:
            items.append(callback())
            if self.try_skip_token_pp(','):
                pass
            elif self.try_skip_token(close_type):
                return items
            else:
                raise self.error_expected('"," or "' + close_type + '"')


def parse_source(source, path=None, debug=False):
    if debug:
        from .debug.parser import DebugTokenizer, DebugParser

        parser = DebugParser(DebugTokenizer(source, path))
    else:
        parser = Parser(Tokenizer(source))
    return parser.parse_l20n()
