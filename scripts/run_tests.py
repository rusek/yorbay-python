#!/usr/bin/env python

import json
import os
import sys
import traceback

sys.path[0] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from yorbay import loads_syntax, ParseError
from yorbay.compiler import compile_l20n


def tokenize_header(header):
    pos, size = 0, len(header)
    while pos != size:
        c = header[pos]
        if c.isspace():
            pos += 1
        elif c in '(),=':
            pos += 1
            yield c, None
        elif c.isdigit():
            startpos = pos
            pos += 1
            while pos != size and header[pos].isdigit():
                pos += 1
            yield 'num', int(header[startpos:pos])
        elif c.isalpha():
            startpos = pos
            pos += 1
            while pos != size and header[pos].isalnum():
                pos += 1
            yield 'ident', header[startpos:pos]
        else:
            raise Exception('Invalid character: ' + c)


class BadSourceSection(object):
    def __init__(self, name, source):
        self.name = name
        self.source = source

    def run(self, env):
        try:
            print ' * running {0}...'.format(self.name)
            loads_syntax(self.source)
        except ParseError:
            pass
        else:
            raise Exception('Section ' + str(self.name) + ': Bad source parsed: ' + self.source)


class Env(object):
    def __init__(self):
        self._sects = []
        self._sect_mapping = {}

    def add_section(self, sect):
        if sect.name in self._sect_mapping:
            raise Exception('Duplicate section ' + sect.name)
        self._sects.append(sect)
        self._sect_mapping[sect.name] = sect

    def get_section(self, name):
        return self._sect_mapping[name]

    def run_sections(self):
        for sect in self._sects:
            sect.run(self)


class SourceSection(object):
    def __init__(self, name, source, syntax_name):
        self.name = name
        self._source = source
        self._syntax_name = syntax_name
        self.syntax = None

    def run(self, env):
        try:
            print ' * running {0}...'.format(self.name)
            syntax = loads_syntax(self._source)
            self.syntax = syntax
            if self._syntax_name is not None:
                syntax = syntax.to_json()
                syntax_sect = env.get_section(self._syntax_name)
                expected_syntax = syntax_sect.get_json()
                if syntax != expected_syntax:
                    raise Exception('Section ' + self.name + ': source is invalid, got ' + repr(syntax) +
                                    ', should be ' + repr(expected_syntax))
        except ParseError:
            traceback.print_exc()
            raise Exception('Section ' + str(self.name) + ': source not parsed: ' + self._source)


class SyntaxSection(object):
    def __init__(self, name, body):
        self.name = name
        self._body = json.loads(body)

    def run(self, env):
        pass

    def get_json(self):
        return self._body


class CheckSection(object):
    def __init__(self, name, body, syntax_name):
        self.name = name
        self._body = json.loads(body)
        self._syntax_name = syntax_name

    def run(self, env):
        print ' * running {0}...'.format(self.name)
        compiled_l20n = compile_l20n(env.get_section(self._syntax_name).syntax)
        for entry_name, expectation in self._body.iteritems():
            print '    * checking {0}...'.format(entry_name)
            try:
                result = compiled_l20n.get(entry_name).invoke(compiled_l20n.make_env({}))
            except:
                if expectation is not False:
                    traceback.print_exc()
                    raise Exception('Section ' + self.name + ': error in entity ' + entry_name)
            else:
                if result != expectation:
                    raise Exception('Section ' + self.name + ': error in entity ' + entry_name + ', expecting ' +
                                    repr(expectation) + ', got ' + repr(result))


class HeaderParser(object):
    def __init__(self, header):
        self._toks = tokenize_header(header)
        self.type, self.value = None, None
        self.next()

    def next(self):
        self.type, self.value = next(self._toks, ('eof', None))

    def skip(self, type):
        if self.type != type:
            raise Exception('Expected ' + type)
        value = self.value
        self.next()
        return value

    def try_skip(self, type):
        if self.type != type:
            return False
        else:
            self.next()
            return True

    def parse(self, body):
        sect = self.parse_header(body)
        if self.type != 'eof':
            raise Exception('eof not reached')
        return sect

    def parse_header(self, body):
        sect_type = self.skip('ident')
        if sect_type == 'badSource':
            return self.parse_bad_source(body)
        if sect_type == 'source':
            return self.parse_source(body)
        if sect_type == 'syntax':
            return self.parse_syntax(body)
        if sect_type == 'check':
            return self.parse_check(body)
        raise Exception('Invalid section type ' + sect_type)

    def parse_syntax(self, body):
        self.skip('(')
        name = self.skip('ident')
        self.skip(')')
        return SyntaxSection(name, body)

    def parse_bad_source(self, body):
        self.skip('(')
        name = self.skip('ident')
        self.skip(')')
        return BadSourceSection(name, body)

    def parse_source(self, body):
        self.skip('(')
        name = self.skip('ident')
        syntax_name = None
        if self.try_skip(','):
            param_name = self.skip('ident')
            if param_name == 'syntax':
                if syntax_name is not None:
                    raise Exception('Duplicate parameter syntax')
                self.skip('=')
                syntax_name = self.skip('ident')
            else:
                raise Exception('Invalid parameter name ' + param_name)
        self.skip(')')
        return SourceSection(name, body, syntax_name)

    def parse_check(self, body):
        self.skip('(')
        name = self.skip('ident')
        syntax_name = None
        if self.try_skip(','):
            param_name = self.skip('ident')
            if param_name == 'syntax':
                if syntax_name is not None:
                    raise Exception('Duplicate parameter syntax')
                self.skip('=')
                syntax_name = self.skip('ident')
            else:
                raise Exception('Invalid parameter name ' + param_name)
        if syntax_name is None:
            raise Exception('Missing parameter syntax')
        self.skip(')')
        return CheckSection(name, body, syntax_name)


def build_section(header, body):
    return HeaderParser(header).parse(body)

section_prefix = '=' * 42 + ' '


def run_file(test_def):
    with open(test_def) as test_file:
        header = None
        body = None
        env = Env()
        for line in test_file:
            if line.startswith(section_prefix):
                if header is not None:
                    env.add_section(build_section(header, ''.join(body)))
                header = line[len(section_prefix):]
                body = []
            else:
                if body is None:
                    raise Exception('Section body without header')
                body.append(line)
        if header is not None:
            env.add_section(build_section(header, ''.join(body)))
        env.run_sections()


def main():
    test_defs = sys.argv[1:]
    if test_defs:
        for test_def in test_defs:
            print 'Opening test file {0}...'.format(test_def)
            run_file(test_def)
    else:
        print 'No input files'

if __name__ == '__main__':
    main()
