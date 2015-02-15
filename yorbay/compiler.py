from __future__ import division

import sys

from .exceptions import BuildError
from . import syntax

NULL = object()
BOOL = object()
NUMBER = object()
STRING = object()
OBJECT = object()


class TailType(object):
    pass

Tail = TailType()


def get_type(val):
    # Caution: compiler expects that val[str] raises TypeError if get_type(val) is not OBJECT.
    # If this assumption ever becomes false, the compiler should check if get_type(val is OBJECT
    # prior to calling val[str].

    if val is None:
        return NULL
    if isinstance(val, bool):
        return BOOL
    if isinstance(val, basestring):
        return STRING
    if isinstance(val, (int, long, float)):
        return NUMBER
    return OBJECT


class ErrorWithSource(Exception):
    def __init__(self, cause, source):
        self.cause = cause
        self.source = source

    def __str__(self):
        return str(self.cause)


class L20nEnv(object):
    def __init__(self, entries, vars, globals):
        self._entries = entries
        self.vars = vars
        self.globals = globals
        self.accessed_globals = {}

    def _get_entity(self, entity_name):
        try:
            entry = self._entries[entity_name]
        except KeyError:
            raise NameError('Entity "{0}" is not defined'.format(entity_name))

        if isinstance(entry, CompiledEntity):
            return entry.bind(self)
        else:
            raise TypeError('Not an entity: {0}'.format(type(entry)))

    def resolve_entity(self, entity_name):
        return self._get_entity(entity_name).resolve()

    def resolve_attribute(self, entity_name, attr_name):
        return self._get_entity(entity_name).resolve_attribute(attr_name)


class ExprEnv(object):
    __slots__ = ('parent', 'locals')

    def __init__(self, parent, locals):
        self.parent = parent
        self.locals = locals


class LazyCompiledL20n(object):
    def get(self):
        raise NotImplementedError


class CompiledL20n(object):
    def __init__(self, entries):
        self._entries = entries
        self.direct_queries = {}
        for entry in entries.itervalues():
            entry.populate_direct_queries(self.direct_queries)

    def make_env(self, vars=None, globals=None):
        if vars is None:
            vars = {}
        if globals is None:
            globals = {}
        return L20nEnv(self._entries, vars, globals)


class Resolvable(object):
    def resolve_once(self):
        raise NotImplementedError


class CompiledEntry(object):
    def bind(self, lenv):
        raise NotImplementedError

    def populate_direct_queries(self, queries):
        raise NotImplementedError


class BoundEntity(Resolvable):
    def __init__(self, entity, lenv):
        self._entity = entity
        self._env = ExprEnv(lenv, ())

    def resolve(self):
        return self._entity._content.evaluate_resolved(self._env)

    resolve_once = resolve

    def __getitem__(self, key):
        return self._entity._content.evaluate(self._env)[key]

    def get_attribute(self, name):
        try:
            attr = self._entity._attrs[name]
        except KeyError:
            raise NameError('Attribute "{0}" is not defined'.format(name))
        return attr.evaluate(self._env)

    def resolve_attribute(self, name):
        try:
            attr = self._entity._attrs[name]
        except KeyError:
            raise NameError('Attribute "{0}" is not defined'.format(name))
        return attr.evaluate_resolved(self._env)


class CompiledEntity(CompiledEntry):
    def __init__(self, name, content, attrs):
        self._name = name
        self._content = content
        self._attrs = attrs

    def bind(self, lenv):
        return BoundEntity(self, lenv)

    def populate_direct_queries(self, queries):
        direct_string = self._content.get_direct_string()
        if direct_string is not None:
            queries[self._name] = direct_string
        for attr_name, attr_expr in self._attrs.iteritems():
            direct_string = attr_expr.get_direct_string()
            if direct_string is not None:
                queries['{0}::{1}'.format(self._name, attr_name)] = direct_string


class BoundMacro(object):
    def __init__(self, macro, lenv):
        self._macro = macro
        self._lenv = lenv

    def invoke(self, args):
        if len(args) != len(self._macro._arg_names):
            raise TypeError('Required {0} argument(s), got {1}'.format(len(self._macro._arg_names), len(args)))
        return self._macro._expr.evaluate(ExprEnv(self._lenv, args))


class CompiledMacro(CompiledEntry):
    def __init__(self, name, arg_names, expr):
        self._name = name
        self._arg_names = arg_names
        self._expr = expr

    def bind(self, lenv):
        return BoundMacro(self, lenv)

    def populate_direct_queries(self, queries):
        pass


class BoundTailMacro(BoundMacro):
    def invoke(self, args):
        if len(args) != len(self._macro._arg_names):
            raise TypeError('Required {0} argument(s), got {1}'.format(len(self._macro._arg_names), len(args)))
        env = ExprEnv(self._lenv, args)
        val = Tail
        rem_repeats = 1000  # default value of sys.getrecursionlimit() on my machine
        while val is Tail:
            val = self._macro._expr.evaluate(env)
            rem_repeats -= 1
            if not rem_repeats:
                raise RuntimeError('Maximum tail recursion depth exceeded')
        return val


class CompiledTailMacro(CompiledMacro):
    def bind(self, lenv):
        return BoundTailMacro(self, lenv)


class CompiledExpr(object):
    def evaluate(self, env):
        raise NotImplementedError

    def evaluate_resolved(self, env):
        val = self.evaluate(env)

        while isinstance(val, Resolvable):
            val = val.resolve_once()

        if get_type(val) is OBJECT:
            raise TypeError('Required primitive type, got {0}'.format(type(val)))

        return val

    def evaluate_bool(self, env):
        val = self.evaluate_resolved(env)
        if get_type(val) is not BOOL:
            raise TypeError('Required boolean, got {0}'.format(type(val)))
        return val

    def evaluate_string(self, env):
        val = self.evaluate_resolved(env)
        if get_type(val) is not STRING:
            raise TypeError('Required string, got {0}'.format(type(val)))
        return val

    def evaluate_number(self, env):
        val = self.evaluate_resolved(env)
        if get_type(val) is not NUMBER:
            raise TypeError('Required number, got {0}'.format(type(val)))
        return val

    def evaluate_placeable(self, env, buf):
        value = self.evaluate_resolved(env)
        value_type = get_type(value)
        if value_type is NUMBER:
            value = str(value)
            if value.endswith('.0'):
                value = value[:-2]
        elif value_type is not STRING:
            raise TypeError('Required number or string, got {0}'.format(type(value)))
        buf.append(value)

    def get_direct_string(self):
        return None


class CompiledConditional(CompiledExpr):
    def __init__(self, test, consequent, alternate):
        self._test = test
        self._consequent = consequent
        self._alternate = alternate

    def evaluate(self, env):
        return self._consequent.evaluate(env) if self._test.evaluate_bool(env) else self._alternate.evaluate(env)

    def evaluate_placeable(self, env, buf):
        if self._test.evaluate_bool(env):
            self._consequent.evaluate_placeable(env, buf)
        else:
            self._alternate.evaluate_placeable(env, buf)


class CompiledLiteral(CompiledExpr):
    def __init__(self, value):
        self._value = value


class CompiledNumber(CompiledLiteral):
    def evaluate(self, env):
        return self._value

    evaluate_number = evaluate


class CompiledNull(CompiledExpr):
    def evaluate(self, env):
        return None


class CompiledString(CompiledLiteral):
    def evaluate(self, env):
        return self._value

    evaluate_string = evaluate

    def evaluate_placeable(self, env, buf):
        buf.append(self._value)

    def get_direct_string(self):
        return self._value


class CompiledBinary(CompiledExpr):
    def __init__(self, left, right):
        self._left = left
        self._right = right


class CompiledEquals(CompiledBinary):
    def evaluate(self, env):
        left, right = self._left.evaluate_resolved(env), self._right.evaluate_resolved(env)
        left_type, right_type = get_type(left), get_type(right)
        if left_type is not right_type or (left_type is not NUMBER and left_type is not STRING):
            raise TypeError('Required either numbers or strings, got {0} and {1}'.format(type(left), type(right)))
        return left == right

    evaluate_bool = evaluate


class CompiledNotEqual(CompiledBinary):
    def evaluate(self, env):
        left, right = self._left.evaluate_resolved(env), self._right.evaluate_resolved(env)
        left_type, right_type = get_type(left), get_type(right)
        if left_type is not right_type or (left_type is not NUMBER and left_type is not STRING):
            raise TypeError('Required either numbers or strings, got {0} and {1}'.format(type(left), type(right)))
        return left != right

    evaluate_bool = evaluate


class CompiledLessThan(CompiledBinary):
    def evaluate(self, env):
        return self._left.evaluate_number(env) < self._right.evaluate_number(env)

    evaluate_bool = evaluate


class CompiledLessEqual(CompiledBinary):
    def evaluate(self, env):
        return self._left.evaluate_number(env) <= self._right.evaluate_number(env)

    evaluate_bool = evaluate


class CompiledGreaterThan(CompiledBinary):
    def evaluate(self, env):
        return self._left.evaluate_number(env) > self._right.evaluate_number(env)

    evaluate_bool = evaluate


class CompiledGreaterEqual(CompiledBinary):
    def evaluate(self, env):
        return self._left.evaluate_number(env) >= self._right.evaluate_number(env)

    evaluate_bool = evaluate


class CompiledAdd(CompiledBinary):
    def evaluate(self, env):
        left, right = self._left.evaluate_resolved(env), self._right.evaluate_resolved(env)
        left_type, right_type = get_type(left), get_type(right)
        if left_type is not right_type or (left_type is not NUMBER and left_type is not STRING):
            raise TypeError('Required either numbers or strings, got {0} and {1}'.format(type(left), type(right)))
        return left + right


class CompiledSubtract(CompiledBinary):
    def evaluate(self, env):
        return self._left.evaluate_number(env) - self._right.evaluate_number(env)

    evaluate_number = evaluate


class CompiledMultiply(CompiledBinary):
    def evaluate(self, env):
        return self._left.evaluate_number(env) * self._right.evaluate_number(env)

    evaluate_number = evaluate


class CompiledDivide(CompiledBinary):
    def evaluate(self, env):
        return self._left.evaluate_number(env) / self._right.evaluate_number(env)

    evaluate_number = evaluate


class CompiledModulo(CompiledBinary):
    def evaluate(self, env):
        return self._left.evaluate_number(env) % self._right.evaluate_number(env)

    evaluate_number = evaluate


class CompiledAnd(CompiledBinary):
    def evaluate(self, env):
        return self._left.evaluate_bool(env) and self._right.evaluate_bool(env)

    evaluate_bool = evaluate


class CompiledOr(CompiledBinary):
    def evaluate(self, env):
        return self._left.evaluate_bool(env) or self._right.evaluate_bool(env)

    evaluate_bool = evaluate


class CompiledNamed(CompiledExpr):
    def __init__(self, name):
        self._name = name


class CompiledEntryAccess(CompiledNamed):
    def __init__(self, entries, name):
        super(CompiledEntryAccess, self).__init__(name)
        self._entries = entries

    def evaluate(self, env):
        try:
            return self._entries[self._name].bind(env.parent)
        except KeyError:
            raise NameError('Entry "{0}" is not defined'.format(self._name))


class CompiledVariableAccess(CompiledNamed):
    def evaluate(self, env):
        try:
            return env.parent.vars[self._name]
        except KeyError:
            raise NameError('Variable "{0}" is not defined'.format(self._name))


class CompiledLocalAccess(CompiledExpr):
    def __init__(self, index):
        self._index = index

    def evaluate(self, env):
        return env.locals[self._index]


class CompiledGlobalAccess(CompiledNamed):
    def evaluate(self, env):
        try:
            return env.parent.accessed_globals[self._name]
        except KeyError:
            try:
                glob = env.parent.globals[self._name]
            except KeyError:
                raise NameError('Global "{0}" is not defined'.format(self._name))
            glob = glob.get()
            env.parent.accessed_globals[self._name] = glob
            return glob


class CompiledComplexString(CompiledExpr):
    def __init__(self, content, source):
        self._content = content
        self._source = source

    def evaluate(self, env):
        buf = []

        try:
            for item in self._content:
                item.evaluate_placeable(env, buf)
        except ErrorWithSource as e:
            raise ErrorWithSource(e.cause, self._source), None, sys.exc_info()[2]
        except StandardError as e:
            raise ErrorWithSource(e, self._source), None, sys.exc_info()[2]

        return ''.join(buf)

    evaluate_string = evaluate

    def evaluate_placeable(self, env, buf):
        # No need to annotate exceptions with source here - this function is called
        # only from other CompiledComplexString, which will override source annotation
        # anyway
        for item in self._content:
            item.evaluate_placeable(env, buf)


class CompiledUnary(CompiledExpr):
    def __init__(self, arg):
        self._arg = arg


class CompiledNot(CompiledUnary):
    def evaluate(self, env):
        return not self._arg.evaluate_bool(env)

    evaluate_bool = evaluate


class CompiledNegative(CompiledUnary):
    def evaluate(self, env):
        return -self._arg.evaluate_number(env)

    evaluate_number = evaluate


class CompiledPositive(CompiledUnary):
    def evaluate(self, env):
        return self._arg.evaluate_number(env)

    evaluate_number = evaluate


class CompiledCall(CompiledExpr):
    def __init__(self, callee, args):
        self._callee = callee
        self._args = args

    def evaluate(self, env):
        callee_val = self._callee.evaluate(env)
        if not isinstance(callee_val, BoundMacro):
            raise TypeError('Required macro, got {0}'.format(type(callee_val)))
        args = [arg.evaluate(env) for arg in self._args]
        return callee_val.invoke(args)


class CompiledTailCall(CompiledExpr):
    def __init__(self, args):
        self._args = args

    def evaluate(self, env):
        env.locals = [arg.evaluate(env) for arg in self._args]
        return Tail


class CompiledPropertyAccess(CompiledExpr):
    def __init__(self, expr, prop):
        self._expr = expr
        self._prop = prop

    def evaluate(self, env):
        expr_val = self._expr.evaluate(env)
        prop_val = self._prop.evaluate_string(env)

        return expr_val[prop_val]


class CompiledAttributeAccess(CompiledExpr):
    def __init__(self, expr, attr):
        self._expr = expr
        self._attr = attr

    def evaluate(self, env):
        expr_val = self._expr.evaluate(env)
        attr_val = self._attr.evaluate_string(env)

        if not isinstance(expr_val, BoundEntity):
            raise TypeError('Required entity, got {0}'.format(type(expr_val)))
        return expr_val.get_attribute(attr_val)


class LazyHash(Resolvable):
    def __init__(self, env, items, index_item, default):
        self._env = ExprEnv(env.parent, env.locals)
        self._items = items
        self._index_item = index_item
        self._default = default

    def __getitem__(self, key):
        try:
            value = self._items[key]
        except KeyError:
            return self.resolve_once()
        return value.evaluate(self._env)

    def resolve_once(self):
        if self._index_item is not None:
            try:
                key = self._index_item.evaluate_string(self._env)
            except ErrorWithSource as e:
                raise e.cause, None, sys.exc_info()[2]
            try:
                value = self._items[key]
            except KeyError:
                pass
            else:
                return value.evaluate(self._env)

        if self._default is not None:
            return self._default.evaluate(self._env)

        raise KeyError('Hash key lookup failed')


class CompiledHash(CompiledExpr):
    def __init__(self, items, index_item, default):
        self._items = items
        self._index_item = index_item
        self._default = default

    def evaluate(self, env):
        return LazyHash(env, self._items, self._index_item, self._default)


class CompilerError(BuildError):
    pass


class CircularDependencyError(CompilerError):
    pass


class CompilerState(object):
    def __init__(self):
        self.entries = {}
        self.collected_entries = {}
        self.import_uris = []
        self.import_cstates = []
        self._collecting = False
        self._collected = False

    def collect(self):
        if self._collected:
            return

        if self._collecting:
            raise CircularDependencyError

        self._collecting = True
        try:
            for icstate in self.import_cstates:
                icstate.collect()
                self.collected_entries.update(icstate.collected_entries)
            self.collected_entries.update(self.entries)
            self._collected = True
        finally:
            self._collecting = False


def compile_syntax(l20n):
    compiler = Compiler()

    for entry in l20n.entries:
        compiler.compile_entry(entry)

    cstate = compiler.cstate
    return cstate, cstate.import_uris, cstate.import_cstates


def link(cstate):
    cstate.collect()
    return CompiledL20n(cstate.collected_entries)


class Handlers(object):
    def __init__(self, handler_mapping=None, instance=None):
        self._handler_mapping = {} if handler_mapping is None else handler_mapping
        self._instance = instance

    def register(self, cls):
        def decor(func):
            self._handler_mapping[cls.__name__] = func.__name__
            return func

        return decor

    def __get__(self, instance, owner):
        if self._instance is not None:
            raise AssertionError('Cannot call __get__ on bound handler')

        if instance is None:
            return self
        else:
            return Handlers(self._handler_mapping, instance)

    def select(self, node):
        if self._instance is None:
            raise AssertionError('Cannot call __get__ on unbound handler')

        attr = self._handler_mapping.get(node.__class__.__name__)
        if attr is None:
            return None
        else:
            return getattr(self._instance, attr)


class Compiler(object):
    def __init__(self):
        self.entry_type = None
        self.entry_name = None
        self.local_names = None
        self.cstate = CompilerState()
        self.entries = self.cstate.entries
        self.collected_entries = self.cstate.collected_entries
        self.import_uris = self.cstate.import_uris

    # Entry enter/exit routines

    def begin_macro(self, macro_name, local_names):
        assert self.entry_name is None
        self.entry_type = 'macro'
        self.entry_name = macro_name
        self.local_names = local_names

    def begin_entity(self, entity_name):
        assert self.entry_name is None
        self.entry_type = 'entity'
        self.entry_name = entity_name
        self.local_names = ()

    def finish_entry(self, compiled_entry):
        self.entries[self.entry_name] = compiled_entry
        self.entry_name = None
        self.local_names = None

    # Entry handlers

    entry_handlers = Handlers()

    @entry_handlers.register(syntax.Comment)
    def compile_comment(self, node):
        pass

    @entry_handlers.register(syntax.Entity)
    def compile_entity(self, node):
        self.begin_entity(node.id.name)

        attrs = self.compile_attributes(node.attrs)
        content = self.compile_value_with_index(node.value, node.index)
        entity = CompiledEntity(node.id.name, content, attrs)

        self.finish_entry(entity)

    @entry_handlers.register(syntax.ImportStatement)
    def compile_import_statement(self, node):
        self.import_uris.append(node.uri.content)

    @entry_handlers.register(syntax.Macro)
    def compile_macro(self, node):
        arg_names = [arg.id.name for arg in node.args]
        self.begin_macro(node.id.name, arg_names)

        has_tail, expr = self.compile_tail_expression(node.expression)
        cls = CompiledTailMacro if has_tail else CompiledMacro
        macro = cls(node.id.name, arg_names, expr)

        self.finish_entry(macro)

    def compile_entry(self, node):
        handler = self.entry_handlers.select(node)
        if handler is not None:
            return handler(node)

        raise AssertionError('Invalid entry node: {0!r}'.format(node))

    # Value handlers

    value_handlers = Handlers()

    @value_handlers.register(syntax.ComplexString)
    def compile_complex_string(self, node, index):
        return CompiledComplexString(
            [self.compile_expression(item) for item in node.content],
            node.source
        )

    @value_handlers.register(syntax.Hash)
    def compile_hash(self, node, index):
        if index:
            index_item, index_tail = index[0], index[1:]
        else:
            index_item, index_tail = None, ()
        default = None
        items = {}
        for item_node in node.content:
            value = self.compile_value(item_node.value, index_tail)
            if item_node.default:
                default = value
            items[item_node.key.name] = value
        return CompiledHash(items, index_item, default)

    @value_handlers.register(syntax.String)
    def compile_string(self, node, index):
        return CompiledString(node.content)

    def compile_value(self, node, index):
        if node is None:
            return CompiledNull()

        handler = self.value_handlers.select(node)
        if handler is not None:
            return handler(node, index)

        raise AssertionError('Not a value node: {0!r}'.format(node))

    # Expression handlers

    expression_handlers = Handlers()

    @expression_handlers.register(syntax.AttributeExpression)
    def compile_attribute_expression(self, node):
        expr = self.compile_expression(node.expression)
        if node.computed:
            attr = self.compile_expression(node.attribute)
        else:
            attr = CompiledString(node.attribute.name)
        return CompiledAttributeAccess(expr, attr)

    binary_operator_classes = {
        '==': CompiledEquals,
        '!=': CompiledNotEqual,
        '<': CompiledLessThan,
        '<=': CompiledLessEqual,
        '>': CompiledGreaterThan,
        '>=': CompiledGreaterEqual,
        '+': CompiledAdd,
        '-': CompiledSubtract,
        '*': CompiledMultiply,
        '/': CompiledDivide,
        '%': CompiledModulo,
    }

    @expression_handlers.register(syntax.BinaryExpression)
    def compile_binary_expression(self, node):
        return self.binary_operator_classes[node.operator.token](
            self.compile_expression(node.left),
            self.compile_expression(node.right)
        )

    @expression_handlers.register(syntax.CallExpression)
    def compile_call_expression(self, node):
        return CompiledCall(
            self.compile_expression(node.callee),
            [self.compile_expression(arg) for arg in node.arguments]
        )

    @expression_handlers.register(syntax.ConditionalExpression)
    def compile_conditional_expression(self, node):
        return CompiledConditional(
            self.compile_expression(node.test),
            self.compile_expression(node.consequent),
            self.compile_expression(node.alternate)
        )

    @expression_handlers.register(syntax.GlobalsExpression)
    def compile_globals_expression(self, node):
        return CompiledGlobalAccess(node.id.name)

    @expression_handlers.register(syntax.Identifier)
    def compile_identifier(self, node):
        return CompiledEntryAccess(self.collected_entries, node.name)

    logical_operator_classes = {
        '&&': CompiledAnd,
        '||': CompiledOr,
    }

    @expression_handlers.register(syntax.LogicalExpression)
    def compile_logical_expression(self, node):
        return self.logical_operator_classes[node.operator.token](
            self.compile_expression(node.left),
            self.compile_expression(node.right)
        )

    @expression_handlers.register(syntax.Number)
    def compile_number(self, node):
        return CompiledNumber(node.value)

    @expression_handlers.register(syntax.ParenthesisExpression)
    def compile_parenthesis_expression(self, node):
        return self.compile_expression(node.expression)

    @expression_handlers.register(syntax.PropertyExpression)
    def compile_property_expression(self, node):
        expr = self.compile_expression(node.expression)
        if node.computed:
            prop = self.compile_expression(node.property)
        else:
            prop = CompiledString(node.property.name)
        return CompiledPropertyAccess(expr, prop)

    @expression_handlers.register(syntax.ThisExpression)
    def compile_this_expression(self, node):
        return CompiledEntryAccess(self.collected_entries, self.entry_name)

    unary_operator_classes = {
        '!': CompiledNot,
        '-': CompiledNegative,
        '+': CompiledPositive,
    }

    @expression_handlers.register(syntax.UnaryExpression)
    def compile_unary_expression(self, node):
        return self.unary_operator_classes[node.operator.token](
            self.compile_expression(node.argument)
        )

    @expression_handlers.register(syntax.Variable)
    def compile_variable(self, node):
        var_name = node.id.name
        try:
            return CompiledLocalAccess(self.local_names.index(var_name))
        except ValueError:
            return CompiledVariableAccess(var_name)

    def compile_expression(self, node):
        handler = self.expression_handlers.select(node)
        if handler is not None:
            return handler(node)

        handler = self.value_handlers.select(node)
        if handler is not None:
            return handler(node, ())

        raise AssertionError('Not an expression node: {0!r}'.format(node))

    # Current (this) entity access detection handlers

    is_this_access_handlers = Handlers()

    @is_this_access_handlers.register(syntax.ThisExpression)
    def is_this_access_this_expression(self, node):
        return True

    @is_this_access_handlers.register(syntax.Identifier)
    def is_this_access_identifier(self, node):
        return self.entry_name == node.name

    @is_this_access_handlers.register(syntax.ParenthesisExpression)
    def is_this_access_parenthesis_expression(self, node):
        return self.is_this_access(node)

    def is_this_access(self, node):
        handler = self.is_this_access_handlers.select(node)
        if handler is not None:
            return handler(node)

        return False

    # Tail expression handlers

    tail_expression_handlers = Handlers()

    @tail_expression_handlers.register(syntax.CallExpression)
    def compile_tail_call_expression(self, node):
        if self.is_this_access(node.callee) and len(node.arguments) == len(self.local_names):
            return True, CompiledTailCall([self.compile_expression(arg) for arg in node.arguments])
        else:
            return False, self.compile_expression(node)

    @tail_expression_handlers.register(syntax.ConditionalExpression)
    def compile_tail_conditional_expression(self, node):
        test = self.compile_expression(node.test)
        consequent_has_tail, consequent = self.compile_tail_expression(node.consequent)
        alternate_has_tail, alternate = self.compile_tail_expression(node.alternate)
        return consequent_has_tail or alternate_has_tail, CompiledConditional(test, consequent, alternate)

    @tail_expression_handlers.register(syntax.ParenthesisExpression)
    def compile_tail_parenthesis_expression(self, node):
        return self.compile_tail_expression(node.expression)

    def compile_tail_expression(self, node):
        handler = self.tail_expression_handlers.select(node)
        if handler is not None:
            return handler(node)

        return False, self.compile_expression(node)

    # Helper methods

    def compile_value_with_index(self, node, index_nodes):
        index = [self.compile_expression(index_item_node) for index_item_node in index_nodes or ()]
        return self.compile_value(node, index)

    def compile_attributes(self, nodes):
        attrs = {}
        for node in nodes or ():
            attrs[node.key.name] = self.compile_value_with_index(node.value, node.index)
        return attrs
