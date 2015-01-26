from . import syntax

import re


_token_re = re.compile(r'''
    ([ \n\r\t]+)|  # group 1: whitespace
    (/\*)|  # group 2: comment start
    ([@$]?[a-zA-Z_][a-zA-Z0-9_]*)|  # group 3: identifiers
    (::|==|!=|<=|>=|&&|\|\||[?!:<>(){}[\]+\-*/%~,\.])|  # group 4: symbols
    ("(?:"")?|'(?:'')?)|  # group 5: string start
    (\d+)  # group 6: number
''', re.VERBOSE)

_safe_str_chars_re = re.compile(r'''[^{'"\\]+''')


class ParseError(Exception):
    pass


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
    def __init__(self, s):
        self._s = s
        self._pos = 0
        self._size = len(s)

    def get_offset(self):
        return self._pos

    def get_source(self, start, end):
        return self._s[start:end]

    def next_token(self):
        if self._pos == self._size:
            return Token('eof', None)

        match = _token_re.match(self._s, self._pos)
        if not match:
            raise ParseError('Invalid token ' + self._s[self._pos])

        self._pos = match.end()
        if match.start(1) != -1:
            type, value = 'ws', None
        elif match.start(2) != -1:
            comment_end = self._s.find('*/', self._pos)
            if comment_end == -1:
                raise ParseError('Unclosed comment')
            type, value = 'comment', self._s[self._pos: comment_end]
            self._pos = comment_end + 2
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
            type, value = 'num', int(match.group(6))  # xxxxxxxxxx num followed by _ a-z A-Z

        # print '<NEXT TOKEN>', type, value
        return Token(type, value)

    def next_text_token(self, delim):
        if self._pos == self._size:
            return Token('eof', None)

        if self._s[self._pos: self._pos + len(delim)] == delim:
            type, value, size = 'str_end', None, len(delim)
        elif self._s[self._pos: self._pos + 2] == '{{':
            type, value, size = 'expr_start', None, 2
        elif self._s[self._pos] == '\\':
            type = 'str'
            value, size = self._parse_escape()
        else:
            type, value, size = 'str', self._s[self._pos], 1
            match = _safe_str_chars_re.match(self._s, self._pos + 1)
            if match:
                extra = match.group()
                value += extra
                size += len(extra)

        self._pos += size
        # print '<NEXT TEXT TOKEN>', type, value
        return Token(type, value)

    def _parse_escape(self):
        if self._size - self._pos < 2:
            raise ParseError('Invalid escape')
        c = self._s[self._pos + 1]
        if c == 'u':
            uarg = self._parse_u_escape_arg(2)
            if 0xd800 <= uarg <= 0xdbff:  # lead surrogate
                if self._s[self._pos + 6, self._pos + 8] != '\\u':
                    raise ParseError('Invalid escape - missing trail surrogate')
                uarg2 = self._parse_u_escape_arg(8)
                if 0xdc00 <= uarg <= 0xdfff:  # trail surrogate
                    return chr(0x10000 + (((uarg - 0xd800) << 10) | (uarg2 - 0xdc00))), 12
                else:
                    ParseError('Invalid escape - not a trail surrogate')
            elif 0xdc00 <= uarg <= 0xdfff:  # trail surrogate
                raise ParseError('Invalid escape - trail surrogate')
            else:
                return chr(uarg), 6
        else:
            return c, 2

    def _parse_u_escape_arg(self, shift):
        cs = self._s[self._pos + shift: self._pos + shift + 4]
        if len(cs) == 4 and cs[1] not in 'xX':
            try:
                return int(cs, 16)
            except ValueError:
                pass
        raise ParseError('Invalid escape')


class Parser(object):
    def __init__(self, s):
        self._tokenizer = Tokenizer(s)
        self.token = None
        self.ws_before = False
        self.next_token()

    def next_token(self):
        token = self._tokenizer.next_token()
        if token.type == 'ws':
            ws_before = True
            token = self._tokenizer.next_token()
        else:
            ws_before = False
        self.token = token
        self.ws_before = ws_before

    def next_text_token(self, delim):
        self.token = self._tokenizer.next_text_token(delim)
        self.ws_before = False

    def error(self, msg):
        # print '<CURRENT TOKEN>', self.token.type, self.token.value  # xxxxxxxxxxxx
        return ParseError(msg)

    def error_expected(self, desc):
        # str_start
        if self.token.type == 'comment':
            return self.error('Comments can be used only as top-level entries')
        elif self.token.type == 'eof':
            return self.error('Expected {0}, but end of input reached'.format(desc))
        else:
            if self.token.type in ('ident', 'num'):
                cur_desc = '"{0}"'.format(self.token.value)
            elif self.token.type == 'var':
                cur_desc = '"${0}"'.format(self.token.value)
            elif self.token.type == 'glob':
                cur_desc = '"@{0}"'.format(self.token.value)
            elif self.token.type == 'str_start':
                cur_desc = 'string'
            else:
                cur_desc = '"{0}"'.format(self.token.type)

            return self.error('Expected ' + desc + ', but got ' + cur_desc + ' instead')

    def skip_token(self, type):
        if self.token.type == type:
            self.next_token()
        else:
            raise self.error_expected('"' + type + '"')

    def try_skip_token(self, type):
        if self.token.type == type:
            self.next_token()
            return True
        else:
            return False

    def parse_l20n(self):
        entries = []

        while self.token.type != 'eof':
            entries.append(self.parse_entry())

        return syntax.L20n(entries)

    def parse_entry(self):
        # we know that self.offset < self.size
        if self.token.type == '<':
            self.next_token()
            if self.token.type == 'ident' and self.ws_before:
                raise self.error('Unexpected white space between "<" and entity/macro name')
            ident = self.parse_identifier()
            if self.token.type == '(':
                if self.ws_before:
                    raise self.error('Unexpected white space between macro name and "("')
                self.next_token()
                return self.parse_macro(ident)
            if self.token.type == '[':
                if self.ws_before:
                    raise self.error('Unexpected white space between entity name and "["')
                self.next_token()
                index = self.parse_item_list(self.parse_expression, ']')
                return self.parse_entity(ident, index)
            return self.parse_entity(ident, None)

        if self.token.type == 'comment':
            content = self.token.value
            self.next_token()
            return syntax.Comment(content)

        if self.token.type == 'ident' and self.token.value == 'import':
            self.next_token()
            return self.parse_import()

        raise self.error_expected('entry')

    def parse_identifier(self):
        if self.token.type != 'ident':
            raise self.error_expected('identifier')
        name = self.token.value
        self.next_token()
        return syntax.Identifier(name)

    def parse_macro(self, ident):
        if ident.name[0] == '_':
            raise self.error('Macro identifier cannot start with "_"')
        args = self.parse_item_list(self.parse_variable, ')')
        self.skip_token('{')
        exp = self.parse_expression()
        self.skip_token('}')
        self.skip_token('>')
        return syntax.Macro(ident, args, exp)

    def parse_expression(self):
        exp = self.parse_or_expression()
        if self.token.type != '?':
            return exp
        self.next_token()
        consequent = self.parse_expression()
        self.skip_token(':')
        return syntax.ConditionalExpression(exp, consequent, self.parse_expression())

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
            self.next_token()
            return syntax.UnaryExpression(syntax.UnaryOperator(type), self.parse_unary_expression())
        else:
            return self.parse_member_expression()

    def parse_member_expression(self):
        exp = self.parse_parenthesis_expression()
        while True:
            if self.try_skip_token('.'):
                exp = self.parse_property_expression(exp, False)
            elif self.try_skip_token('['):
                exp = self.parse_property_expression(exp, True)
            elif self.try_skip_token('::'):
                if self.token.type == '[':
                    if self.ws_before:
                        raise self.error('Unexpected white space between "::" and "["')
                    self.next_token()
                    exp = self.parse_attribute_expression(exp, True)
                else:
                    exp = self.parse_attribute_expression(exp, False)
            elif self.try_skip_token('('):
                exp = self.parse_call_expression(exp)
            else:
                return exp

    def parse_parenthesis_expression(self):
        if self.try_skip_token('('):
            exp = self.parse_expression()
            self.skip_token(')')
            return syntax.ParenthesisExpression(exp)
        else:
            return self.parse_primary_expression()

    def parse_property_expression(self, expression, computed):
        if computed:
            property = self.parse_expression()
            self.skip_token(']')
        else:
            if self.token.type == 'ident' and self.ws_before:
                raise self.error('Unexpected white space between "." and property name')
            property = self.parse_identifier()
        return syntax.PropertyExpression(expression, property, computed)

    def parse_attribute_expression(self, expression, computed):
        if not isinstance(expression, (syntax.ParenthesisExpression, syntax.Identifier, syntax.ThisExpression)):
            raise self.error('AttributeExpression must have Identifier, This or Parenthesis as left node')  # xxxxxxxxx
        if computed:
            attribute = self.parse_expression()
            self.skip_token(']')
        else:
            if self.token.type == 'ident' and self.ws_before:
                raise self.error('Unexpected white space between "::" and attribute name')
            attribute = self.parse_identifier()
        return syntax.AttributeExpression(expression, attribute, computed)

    def parse_call_expression(self, callee):
        return syntax.CallExpression(callee, self.parse_item_list(self.parse_expression, ')'))

    def parse_primary_expression(self):
        if self.token.type == 'num':
            value = self.token.value
            self.next_token()
            return syntax.Number(value)
        elif self.token.type == 'ident':
            return self.parse_identifier()
        elif self.try_skip_token('~'):
            return syntax.ThisExpression()
        elif self.token.type == 'glob':
            name = self.token.value
            self.next_token()
            return syntax.GlobalsExpression(syntax.Identifier(name))
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
            self.next_token()
            exp = exp_cls(op_cls(type), exp, callback())

    def parse_variable(self):
        if self.token.type != 'var':
            raise self.error_expected('variable')
        name = self.token.value
        self.next_token()
        return syntax.Variable(syntax.Identifier(name))

    def parse_entity(self, ident, index):
        if not self.ws_before:
            raise self.error('Expected white space')  # xxxxxxxxxxxxxxxxxxxxxxxxxxxx
        value = self.parse_optional_value()
        attrs = None
        if value is None:
            if self.token.type == '>':
                raise self.error('Expected ">"')  # xxxxxxxxxx maybe attributes expected ?
            attrs = self.parse_attributes()
        else:
            if self.token.type != '>':
                if self.ws_before:
                    raise self.error('Expected white space')  # xxxxxxxxxxxxxxxxx
                attrs = self.parse_attributes()
            else:
                self.next_token()

        return syntax.Entity(ident, value, index, attrs)

    def parse_optional_value(self):
        if self.token.type == 'str_start':
            return self.parse_string()

        if self.try_skip_token('{'):
            return self.parse_hash()

        return None

    def parse_value(self):
        value = self.parse_optional_value()
        if value is None:
            raise self.error_expected('value')  # xxxxxxxxxxxxxxxxxx
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
            key, value = self.parse_kvp()
            content.append(syntax.HashItem(key, value, def_item))
            if self.try_skip_token(','):
                pass
            elif self.try_skip_token('}'):
                return syntax.Hash(content)

    def parse_kvp(self):
        key = self.parse_identifier()
        self.skip_token(':')
        value = self.parse_value()
        return key, value

    def parse_attributes(self):
        attrs = []

        while True:
            key, value, index = self.parse_kvp_with_index()
            attrs.append(syntax.Attribute(key, value, index))
            if self.try_skip_token('>'):
                return attrs
            elif not self.ws_before:
                raise self.error('Expected whitespace')  # xxxxxxxxxxxxxxxxxxxxxxxx

    def parse_kvp_with_index(self):
        key = self.parse_identifier()
        index = []
        if self.token.type == '[':
            if not self.ws_before:
                raise self.error('Expected white space before "["')  # xxxxxxxxxxxxxxxxxxxxxx
            self.next_token()
            index = self.parse_item_list(self.parse_expression, ']')
        self.skip_token(':')
        value = self.parse_value()
        return key, value, index

    def parse_import(self):
        if self.token.type != '(':
            raise self.error_expected('"("')
        if self.ws_before:
            raise self.error('Unexpected white space between "import" and "("')
        self.next_token()
        uri = self.parse_string()  # xxxxxxxxxxxxxxxxxxx POSSIBLE BUG
        self.skip_token(')')
        return syntax.ImportStatement(uri)

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
                buf.append(self.token.value)
                self.next_text_token(delim)
            elif self.token.type == 'expr_start':
                self.next_token()
                if buf:
                    body.append(syntax.String(''.join(buf)))
                    buf = []
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
                    return syntax.String(''.join(buf))
                if buf:
                    body.append(syntax.String(''.join(buf)))
                return syntax.ComplexString(body, self._tokenizer.get_source(start, end))
            elif self.token.type == 'eof':
                raise self.error('Unclosed string')
            else:
                raise Exception('Invalid token type: %s' % self.token.type)

    def parse_item_list(self, callback, close_type):
        if self.try_skip_token(close_type):
            return []

        items = []
        while True:
            items.append(callback())
            if self.try_skip_token(','):
                pass
            elif self.try_skip_token(close_type):
                return items
            else:
                raise self.error_expected('"," or "' + close_type + '"')


def loads(s):
    return Parser(s).parse_l20n()
