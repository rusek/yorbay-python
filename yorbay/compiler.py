from __future__ import division

import sys

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
    def __init__(self, entries, vars, globals, this):
        self.entries = entries
        self.vars = vars
        self.globals = globals
        self.this = this

    def _get_entity(self, entity_name):
        try:
            entry = self.entries[entity_name]
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


class CompiledL20n(object):
    def __init__(self, entries):
        self._entries = entries
        self.direct_queries = {}
        for entry in entries.itervalues():
            entry.populate_direct_queries(self.direct_queries)

    def make_env(self, vars=None):
        if vars is None:
            vars = {}
        return L20nEnv(self._entries, vars, {}, None)


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
        while val is Tail:
            val = self._macro._expr.evaluate(env)
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
    def evaluate(self, env):
        try:
            return env.parent.entries[self._name].bind(env.parent)
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
            return env.parent.globals[self._name]
        except KeyError:
            raise NameError('Global "{0}" is not defined'.format(self._name))


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


class CircularDependencyError(Exception):
    pass


class CompilerState(object):
    def __init__(self):
        self.entry_name = None
        self.local_names = None
        self.entries = {}
        self.import_uris = []
        self.import_cstates = []
        self._collecting = False

    def collect(self, entries):
        if self._collecting:
            raise CircularDependencyError

        self._collecting = True
        try:
            for icstate in self.import_cstates:
                icstate.collect(entries)
            entries.update(self.entries)
        finally:
            self._collecting = False

    def begin_macro(self, macro_name, local_names):
        assert self.entry_name is None
        self.entry_name = macro_name
        self.local_names = local_names

    def begin_entity(self, entity_name):
        assert self.entry_name is None
        self.entry_name = entity_name
        self.local_names = ()

    def finish_entry(self, compiled_entry):
        self.entries[self.entry_name] = compiled_entry
        self.entry_name = None
        self.local_names = None


def compile_syntax(l20n):
    cstate = CompilerState()
    for entry in l20n.entries:
        compile_entry(cstate, entry)
    return cstate, cstate.import_uris, cstate.import_cstates


def link(cstate):
    entries = {}
    cstate.collect(entries)
    return CompiledL20n(entries)


def compile_entity(cstate, entity):
    cstate.begin_entity(entity.id.name)

    attrs = {}
    for attr in entity.attrs or ():
        if attr.index is None:
            index = ()
        else:
            index = [compile_expression(cstate, index_item) for index_item in attr.index]
        attrs[attr.key.name] = compile_value(cstate, attr.value, index)

    if entity.value is not None:
        if entity.index is None:
            index = ()
        else:
            index = [compile_expression(cstate, index_item) for index_item in entity.index]

        content = compile_value(cstate, entity.value, index)
    else:
        content = CompiledNull()

    cstate.finish_entry(CompiledEntity(entity.id.name, content, attrs))


def compile_macro(cstate, macro):
    arg_names = [arg.id.name for arg in macro.args]
    cstate.begin_macro(macro.id.name, arg_names)

    has_tail, expr = compile_tail_expression(cstate, macro.expression)
    if has_tail:
        compiled_macro = CompiledTailMacro(macro.id.name, arg_names, expr)
    else:
        compiled_macro = CompiledMacro(macro.id.name, arg_names, expr)

    cstate.finish_entry(compiled_macro)


def compile_import_statement(cstate, node):
    cstate.import_uris.append(node.uri.content)


entry_dispatch = {
    'Comment': lambda cstate, node: None,
    'Entity': compile_entity,
    'Macro': compile_macro,
    'ImportStatement': compile_import_statement,
}


def compile_entry(cstate, node):
    return entry_dispatch[node.__class__.__name__](cstate, node)


def compile_hash(cstate, node, index):
    if index:
        index_item, index_tail = index[0], index[1:]
    else:
        index_item, index_tail = None, ()
    default = None
    items = {}
    for item_node in node.content:
        value = compile_value(cstate, item_node.value, index_tail)
        if item_node.default:
            default = value
        items[item_node.key.name] = value
    return CompiledHash(items, index_item, default)


def compile_property_expression(cstate, node):
    expr = compile_expression(cstate, node.expression)
    if node.computed:
        prop = compile_expression(cstate, node.property)
    else:
        prop = CompiledString(node.property.name)
    return CompiledPropertyAccess(expr, prop)


def compile_attribute_expression(cstate, node):
    expr = compile_expression(cstate, node.expression)
    if node.computed:
        attr = compile_expression(cstate, node.attribute)
    else:
        attr = CompiledString(node.attribute.name)
    return CompiledAttributeAccess(expr, attr)


def compile_variable(cstate, node):
    var_name = node.id.name
    try:
        return CompiledLocalAccess(cstate.local_names.index(var_name))
    except ValueError:
        return CompiledVariableAccess(var_name)


expression_dispatch = {
    'Number': lambda cstate, node: CompiledNumber(node.value),
    'Identifier': lambda cstate, node: CompiledEntryAccess(node.name),
    'Variable': compile_variable,
    'GlobalsExpression': lambda cstate, node: CompiledGlobalAccess(node.id.name),
    'ConditionalExpression': lambda cstate, node: CompiledConditional(
        compile_expression(cstate, node.test),
        compile_expression(cstate, node.consequent),
        compile_expression(cstate, node.alternate)
    ),
    'BinaryExpression': lambda cstate, node: binary_operators[node.operator.token](
        compile_expression(cstate, node.left),
        compile_expression(cstate, node.right)
    ),
    'LogicalExpression': lambda cstate, node: logical_operators[node.operator.token](
        compile_expression(cstate, node.left),
        compile_expression(cstate, node.right)
    ),
    'UnaryExpression': lambda cstate, node: unary_operators[node.operator.token](
        compile_expression(cstate, node.argument)
    ),
    'ParenthesisExpression': lambda cstate, node: compile_expression(cstate, node.expression),
    'CallExpression': lambda cstate, node: CompiledCall(
        compile_expression(cstate, node.callee),
        [compile_expression(cstate, arg) for arg in node.arguments]
    ),
    'PropertyExpression': compile_property_expression,
    'AttributeExpression': compile_attribute_expression,
    'ThisExpression': lambda cstate, node: CompiledEntryAccess(cstate.entry_name),
}

value_dispatch = {
    'String': lambda cstate, node, index: CompiledString(node.content),
    'ComplexString': lambda cstate, node, index: CompiledComplexString(
        [compile_expression(cstate, item) for item in node.content], node.source),
    'Hash': compile_hash,
}


def is_this_access(cstate, node):
    node_type = node.__class__.__name__
    if node_type == 'ThisExpression':
        return True
    elif node_type == 'Identifier':
        return cstate.entry_name == node.name
    else:
        return False


def compile_tail_expression(cstate, node):
    node_type = node.__class__.__name__
    if node_type == 'ConditionalExpression':
        test = compile_expression(cstate, node.test)
        consequent_has_tail, consequent = compile_tail_expression(cstate, node.consequent)
        alternate_has_tail, alternate = compile_tail_expression(cstate, node.alternate)
        return consequent_has_tail or alternate_has_tail, CompiledConditional(test, consequent, alternate)
    elif node_type == 'CallExpression':
        if is_this_access(cstate, node.callee) and len(node.arguments) == len(cstate.local_names):
            return True, CompiledTailCall([compile_expression(cstate, arg) for arg in node.arguments])

    return False, compile_expression(cstate, node)


def compile_expression(cstate, node):
    name = node.__class__.__name__
    if name in expression_dispatch:
        return expression_dispatch[name](cstate, node)
    else:
        return value_dispatch[name](cstate, node, ())


def compile_value(cstate, node, index):
    return value_dispatch[node.__class__.__name__](cstate, node, index)


binary_operators = {
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


logical_operators = {
    '&&': CompiledAnd,
    '||': CompiledOr,
}


unary_operators = {
    '!': CompiledNot,
    '-': CompiledNegative,
    '+': CompiledPositive,
}
