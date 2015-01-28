#!/usr/bin/env python

import copy
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


class StepCounter(object):
    def __init__(self):
        self._counter = 0

    def next_label(self):
        self._counter += 1
        return '[{0:>4}]'.format(self._counter)


class Env(object):
    def __init__(self, step_counter):
        self._sects = []
        self._sect_mapping = {}
        self._step_counter = step_counter
        self._results = {}

    def step(self):
        return self._step_counter.next_label()

    def add_section(self, sect):
        if sect.name in self._sect_mapping:
            raise Exception('Duplicate section ' + sect.name)
        self._sects.append(sect)
        self._sect_mapping[sect.name] = sect

    def get_section(self, name, type=None):
        try:
            sect = self._sect_mapping[name]
        except KeyError:
            raise Exception('Section not found: {0}'.format(name))

        if type is not None and not isinstance(sect, type):
            raise Exception('Invalid section type: expecting {0}, got{1}', type, sect.__class__)

        return sect

    def run_section(self, name, type=None):
        sect = self.get_section(name, type)
        if sect.name not in self._results:
            self._results[sect.name] = sect.run(self)
        return self._results[sect.name]

    def run_sections(self):
        for sect in self._sects:
            if sect.name not in self._results:
                self._results[sect.name] = sect.run(self)


class Section(object):
    def __init__(self, name):
        self.name = name

    def run(self, env):
        pass


class BadSourceSection(Section):
    def __init__(self, name, source):
        super(BadSourceSection, self).__init__(name)
        self._source = source

    def run(self, env):
        try:
            print '{0} * running {1}...'.format(env.step(), self.name)
            loads_syntax(self._source)
        except ParseError:
            pass
        else:
            raise Exception('Section ' + str(self.name) + ': Bad source parsed: ' + self._source)


class SourceSection(Section):
    def __init__(self, name, source, syntax_name):
        super(SourceSection, self).__init__(name)
        self._source = source
        self._syntax_name = syntax_name

    def run(self, env):
        try:
            print '{0} * running {1}...'.format(env.step(), self.name)
            syntax = loads_syntax(self._source)
            if self._syntax_name is not None:
                json_syntax = syntax.to_json()
                expected_syntax = env.run_section(self._syntax_name, type=SyntaxSection)
                if json_syntax != expected_syntax:
                    raise Exception('Section ' + self.name + ': source is invalid, got ' + repr(json_syntax) +
                                    ', should be ' + repr(expected_syntax))
            return syntax
        except ParseError:
            traceback.print_exc()
            raise Exception('Section ' + str(self.name) + ': source not parsed: ' + self._source)


class SyntaxSection(Section):
    def __init__(self, name, body, wrapper_name):
        super(SyntaxSection, self).__init__(name)
        self._body = json.loads(body)
        self._wrapper_name = wrapper_name

    def run(self, env):
        # This should be AST, but for now only JSON representation is used anyway
        if self._wrapper_name is not None:
            return env.run_section(self._wrapper_name, type=WrapperSection).wrap(self._body)
        else:
            return self._body


class CheckSection(Section):
    def __init__(self, name, body, syntax_name):
        super(CheckSection, self).__init__(name)
        self._body = json.loads(body)
        self._syntax_name = syntax_name

    def run(self, env):
        print '{0} * running {1}...'.format(env.step(), self.name)
        # Should accept either SyntaxSection or SourceSection, but currently SyntaxSection returns JSON and there's
        # no way to convert it to AST
        compiled_l20n = compile_l20n(env.run_section(self._syntax_name, type=SourceSection))
        for entry_name, expectation in self._body.iteritems():
            print '{0}    * checking {1}...'.format(env.step(), entry_name)
            try:
                result = compiled_l20n.make_env({}).entries[entry_name].resolve()
            except:
                if expectation is not False:
                    traceback.print_exc()
                    raise Exception('Section ' + self.name + ': error in entity ' + entry_name)
            else:
                if result != expectation:
                    raise Exception('Section ' + self.name + ': error in entity ' + entry_name + ', expecting ' +
                                    repr(expectation) + ', got ' + repr(result))


class Wrapper(object):
    def __init__(self, wrapper, here):
        self._wrapper = wrapper
        self._path = None
        self._key = None
        self._setup_path([], self._wrapper, here)
        if self._path is None:
            raise Exception('HERE not found')

    def _setup_path(self, path_key, haystack, needle):
        if haystack == needle:
            if self._path is None:
                self._path, self._key = path_key[:-1], path_key[-1]
                return
            else:
                raise Exception('Duplicate HERE')

        if isinstance(haystack, dict):
            it = haystack.iteritems()
        elif isinstance(haystack, list):
            it = enumerate(haystack)
        else:
            return

        path_key.append(None)
        for k, v in it:
            path_key[-1] = k
            self._setup_path(path_key, v, needle)
        path_key.pop()

    def wrap(self, value):
        wrapper = copy.deepcopy(self._wrapper)
        reduce(lambda acc, key: acc[key], self._path, wrapper)[self._key] = value
        return wrapper


class WrapperSection(Section):
    def __init__(self, name, body):
        super(WrapperSection, self).__init__(name)
        self._wrapper = Wrapper(json.loads(body), '<HERE>')

    def run(self, env):
        return self._wrapper


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
        if sect_type == 'wrapper':
            return self.parse_wrapper(body)
        raise Exception('Invalid section type ' + sect_type)

    def parse_wrapper(self, body):
        self.skip('(')
        name = self.skip('ident')
        self.skip(')')
        return WrapperSection(name, body)

    def parse_syntax(self, body):
        self.skip('(')
        name = self.skip('ident')
        param_values = self.parse_params(
            optional=dict(
                wrapper=lambda: self.skip('ident')
            )
        )
        self.skip(')')
        return SyntaxSection(name, body, param_values.get('wrapper'))

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

    def parse_params(self, optional):
        values = {}

        while self.try_skip(','):
            param_name = self.skip('ident')
            if param_name in optional:
                if param_name in values:
                    raise Exception('Duplicate parameter: {0}'.format(param_name))
                self.skip('=')
                values[param_name] = optional[param_name]()
            else:
                raise Exception('Invalid parameter: ' + param_name)

        return values

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


def run_file(test_def, step_counter):
    with open(test_def) as test_file:
        header = None
        body = None
        env = Env(step_counter)
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
        step_counter = StepCounter()
        for test_def in test_defs:
            print 'Opening test file {0}...'.format(test_def)
            run_file(test_def, step_counter)
    else:
        print 'No input files'

if __name__ == '__main__':
    main()
