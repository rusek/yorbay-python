#!/usr/bin/env python

import codecs
import copy
import json
import os
import sys
import traceback

sys.path[0] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from yorbay.parser import parse_source, ParseError
from yorbay.compiler import compile_syntax, ErrorWithSource


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


class Context(object):
    def __init__(self, vars):
        self.vars = vars


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
            raise Exception('Invalid section type: expecting {0}, got{1}'.format(type, sect.__class__))

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
    def __init__(self, name, body, trim):
        super(BadSourceSection, self).__init__(name)
        self._source = body.strip() if trim else body

    def run(self, env):
        try:
            print '{0} * running {1}...'.format(env.step(), self.name)
            parse_source(self._source)
        except ParseError:
            pass
        else:
            raise Exception('Section ' + str(self.name) + ': Bad source parsed: ' + self._source)


class SourceSection(Section):
    def __init__(self, name, source, syntax):
        super(SourceSection, self).__init__(name)
        self._source = source
        self._syntax_name = syntax

    def run(self, env):
        try:
            if self._syntax_name is None:
                expected_syntax = None
            else:
                expected_syntax = env.run_section(self._syntax_name, type=SyntaxSection)

            print '{0} * running {1}...'.format(env.step(), self.name)
            syntax = parse_source(self._source)
            if expected_syntax is not None:
                json_syntax = syntax.to_json()
                if json_syntax != expected_syntax:
                    print format_json_diff(expected_syntax, json_syntax),
                    raise Exception('Section ' + self.name + ': source is invalid, got ' + repr(json_syntax) +
                                    ', should be ' + repr(expected_syntax))
            return syntax
        except ParseError:
            traceback.print_exc()
            raise Exception('Section ' + str(self.name) + ': source not parsed: ' + self._source)


class SyntaxSection(Section):
    def __init__(self, name, body, wrapper):
        super(SyntaxSection, self).__init__(name)
        self._body = json.loads(body)
        self._wrapper_name = wrapper

    def run(self, env):
        # This should be AST, but for now only JSON representation is used anyway
        if self._wrapper_name is not None:
            return env.run_section(self._wrapper_name, type=WrapperSection).wrap(self._body)
        else:
            return self._body


def format_json_diff(expected, actual):
    path = []
    msg = None
    while msg is None:
        if isinstance(expected, dict) and isinstance(actual, dict):
            if set(expected.iterkeys()) != set(actual.iterkeys()):
                msg = '    expected keys: {0}\n    actual keys: {1}\n'.format(
                    sorted(expected.iterkeys()), sorted(actual.iterkeys()))
            else:
                for k, v in expected.iteritems():
                    if v != actual[k]:
                        path.append(k)
                        expected, actual = v, actual[k]
                        break
                else:
                    raise Exception('Impossible')
        elif isinstance(expected, list) and isinstance(actual, list):
            if len(expected) != len(actual):
                msg = '    expected length: {0}\n    actual length: {1}\n'.format(
                    len(expected), len(actual))
            else:
                for k, (v1, v2) in enumerate(zip(expected, actual)):
                    if v1 != v2:
                        path.append(k)
                        expected, actual = v1, v2
                        break
                else:
                    raise Exception('Impossible')
        else:
            msg = '    expected: {0}\n    actual: {1}\n'.format(expected, actual)
    if path:
        return 'Objects differ on {0}:\n'.format('.'.join(map(unicode, path))) + msg
    else:
        return 'Objects differ:\n'.format(path) + msg


class CheckSection(Section):
    def __init__(self, name, body, syntax, context, gracefulErrors):
        super(CheckSection, self).__init__(name)
        self._body = json.loads(body)
        self._syntax_name = syntax
        self._context_name = context
        self._graceful_errors = gracefulErrors

    def run(self, env):
        # Should accept either SyntaxSection or SourceSection, but currently SyntaxSection returns JSON and there's
        # no way to convert it to AST
        syntax = env.run_section(self._syntax_name, type=SourceSection)
        if self._context_name is None:
            context = Context({})
        else:
            context = env.run_section(self._context_name, type=ContextSection)

        print '{0} * running {1}...'.format(env.step(), self.name)
        compiled_l20n = compile_syntax(syntax)
        for entry_name, expectation in self._body.iteritems():
            print '{0}    * checking {1}...'.format(env.step(), entry_name)
            try:
                try:
                    result = compiled_l20n.make_env(context.vars).resolve_entity(entry_name)
                except Exception as e:
                    if self._graceful_errors:
                        if isinstance(e, ErrorWithSource):
                            result = e.source
                        else:
                            result = entry_name
                    else:
                        raise
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


class ContextSection(Section):
    def __init__(self, name, body):
        super(ContextSection, self).__init__(name)
        self._context = Context(json.loads(body))

    def run(self, env):
        return self._context


class ParamParser(object):
    def __init__(self, func, args, kwargs):
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def _call(self):
        return self._func(*self._args, **self._kwargs)

    def first(self, name):
        raise NotImplementedError

    def next(self, name, prev):
        raise NotImplementedError

    def none(self, name):
        raise NotImplementedError


class OptionalParam(ParamParser):
    def __init__(self, default, func, *args, **kwargs):
        super(OptionalParam, self).__init__(func, args, kwargs)
        self._default = default

    def first(self, name):
        return self._call()

    def next(self, name, prev):
        raise Exception('Duplicate parameter: {0}'.format(name))

    def none(self, name):
        return self._default


class RequiredParam(ParamParser):
    def __init__(self, func, *args, **kwargs):
        super(RequiredParam, self).__init__(func, args, kwargs)

    def first(self, name):
        return self._call()

    def next(self, name, prev):
        raise Exception('Duplicate parameter: {0}'.format(name))

    def none(self, name):
        raise Exception('Missing parameter: {0}'.format(name))


class ParamValues(object):
    def __init__(self, values):
        self._values = values

    def __getattr__(self, name):
        return self._values[name]


class SectionParser(object):
    def __init__(self, factory, **params):
        self.factory = factory
        self.params = params


class HeaderParser(object):
    def __init__(self, header):
        self._toks = tokenize_header(header)
        self.type, self.value = None, None
        self.next()

        self._sect_parsers = {
            'source': SectionParser(
                SourceSection,
                syntax=OptionalParam(None, self.skip, 'ident'),
            ),
            'badSource': SectionParser(
                BadSourceSection,
                trim=OptionalParam(False, self.parse_bool)
            ),
            'syntax': SectionParser(
                SyntaxSection,
                wrapper=OptionalParam(None, self.skip, 'ident'),
            ),
            'check': SectionParser(
                CheckSection,
                syntax=RequiredParam(self.skip, 'ident'),
                context=OptionalParam(None, self.skip, 'ident'),
                gracefulErrors=OptionalParam(False, self.parse_bool),
            ),
            'wrapper': SectionParser(
                WrapperSection,
            ),
            'context': SectionParser(
                ContextSection,
            ),
        }

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
        try:
            sect_parser = self._sect_parsers[sect_type]
        except KeyError:
            raise Exception('Invalid section type: {0}'.format(sect_type))
        self.skip('(')
        name = self.skip('ident')
        if sect_parser.params:
            param_values = self.parse_params(sect_parser.params)
        else:
            param_values = {}
        self.skip(')')
        return sect_parser.factory(name, body, **param_values)

    def parse_bool(self):
        value = self.skip('ident')
        if value == 'true':
            return True
        elif value == 'false':
            return False
        else:
            raise Exception('Not a boolean value: {0}'.format(value))

    def parse_params(self, params):
        values = {}

        while self.try_skip(','):
            param_name = self.skip('ident')
            if param_name in params:
                self.skip('=')
                if param_name in values:
                    values[param_name] = params[param_name].next(param_name, values[param_name])
                else:
                    values[param_name] = params[param_name].first(param_name)
            else:
                raise Exception('Invalid parameter: {0}'.format(param_name))

        for param_name, param in params.iteritems():
            if param_name not in values:
                values[param_name] = param.none(param_name)

        return values


def build_section(header, body):
    return HeaderParser(header).parse(body)

section_prefix = '=' * 42 + ' '


def run_file(test_def, step_counter):
    with codecs.open(test_def, encoding='UTF-8') as test_file:
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
