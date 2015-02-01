from __future__ import division

import sys

BOOL = object()
NUMBER = object()
STRING = object()
OBJECT = object()


def get_type(val):
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

    def resolve_entity(self, entity_name):
        entry = self.entries[entity_name]
        if isinstance(entry, BoundEntity):
            return entry.resolve()
        else:
            raise TypeError('Not an entity: {0}'.format(type(entry)))

    def resolve_attribute(self, entity_name, attribute_name):
        entry = self.entries[entity_name]
        if isinstance(entry, BoundEntity):
            return entry.resolve_attribute(attribute_name)
        else:
            raise TypeError('Not an entity: {0}'.format(type(entry)))

    def make_expr_env(self, this, locals):
        return ExprEnv(self, this, locals)


class ExprEnv(object):
    __slots__ = ('parent', 'this', 'locals')

    def __init__(self, parent, this, locals):
        self.parent = parent
        self.this = this
        self.locals = locals


class CompiledL20n(object):
    def __init__(self, entries):
        self._entries = entries

    def make_env(self, vars=None):
        if vars is None:
            vars = {}
        entries = {}
        env = L20nEnv(entries, vars, {}, None)
        for k, v in self._entries.iteritems():
            entries[k] = v.bind(env)
        return env


class Dispatcher(object):
    def __init__(self):
        self._dispatch_table = {}

    def register(self, type):
        def decor(func):
            self._dispatch_table[type] = func
            return func
        return decor

    def __call__(self, node, *args, **kwargs):
        return self._dispatch_table[node.__class__.__name__](node, *args, **kwargs)


class Resolvable(object):
    def resolve_once(self):
        raise NotImplementedError


class BoundEntity(Resolvable):
    def __init__(self, entity, lenv):
        self._entity = entity
        self._env = lenv.make_expr_env(self, {})

    def resolve(self):
        return self._entity._content.evaluate_resolved(self._env)

    resolve_once = resolve

    def __getitem__(self, key):
        return self._entity._content.evaluate(self._env)[key]  # xxxx should be consistent with PropertyAccess!

    def get_attribute(self, name):
        return self._entity._attrs[name].evaluate(self._env)

    def resolve_attribute(self, name):
        return self._entity._attrs[name].evaluate_resolved(self._env)


class CompiledEntity(object):
    def __init__(self, name, content, attrs):
        self._name = name
        self._content = content
        self._attrs = attrs

    def bind(self, lenv):
        return BoundEntity(self, lenv)


class BoundMacro(object):
    def __init__(self, macro, lenv):
        self._macro = macro
        self._lenv = lenv

    def invoke(self, args):
        if len(args) != len(self._macro._arg_names):
            raise TypeError('Required {0} argument(s), got {1}'.format(len(self._macro._arg_names), len(args)))
        return self._macro._expr.evaluate(self._lenv.make_expr_env(self, dict(zip(self._macro._arg_names, args))))


class CompiledMacro(object):
    def __init__(self, name, arg_names, expr):
        self._name = name
        self._arg_names = arg_names
        self._expr = expr

    def bind(self, lenv):
        return BoundMacro(self, lenv)


class CompiledExpr(object):
    def evaluate(self, env):
        raise NotImplementedError

    def evaluate_resolved(self, env):
        val = self.evaluate(env)
        while True:
            if isinstance(val, Resolvable):
                val = val.resolve_once()
            else:
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
        return self._left.evaluate_number(env) / self._right.evaluate_number(env)  # xxxx zero, truediv !!

    evaluate_number = evaluate


class CompiledModulo(CompiledBinary):
    def evaluate(self, env):
        return self._left.evaluate_number(env) % self._right.evaluate_number(env)  # xxxx zero

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
            return env.parent.entries[self._name]
        except KeyError:
            raise NameError('Entry "{0}" is not defined'.format(self._name))


class CompiledVariableAccess(CompiledNamed):
    def evaluate(self, env):
        try:
            try:
                return env.locals[self._name]
            except KeyError:
                return env.parent.vars[self._name]
        except KeyError:
            raise NameError('Variable "{0}" is not defined'.format(self._name))


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
        except Exception as e:
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


class CompiledPropertyAccess(CompiledExpr):
    def __init__(self, expr, prop):
        self._expr = expr
        self._prop = prop

    def evaluate(self, env):
        expr_val = self._expr.evaluate(env)
        prop_val = self._prop.evaluate_string(env)

        return expr_val[prop_val]  # xxxxxxx check if operation supported


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
        self._env = ExprEnv(env.parent, env.this, env.locals)
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


class CompiledThis(CompiledExpr):
    def evaluate(self, env):
        return env.this


def compile_syntax(l20n):
    entries = {}
    for entry in l20n.entries:
        compiled_entry = compile_entry(entry)
        if compiled_entry is not None:
            k, v = compiled_entry
            entries[k] = v
    return CompiledL20n(entries)


compile_entry = Dispatcher()
compile_entry.register(type='Comment')(lambda node: None)


@compile_entry.register(type='Entity')
def compile_entity(entity):
    attrs = {}
    for attr in entity.attrs or ():
        index = () if entity.index is None else [compile_expression(index_item) for index_item in entity.index]
        attrs[attr.key.name] = compile_value(attr.value, index)

    if entity.value is not None:
        content = compile_value(
            entity.value,
            () if entity.index is None else [compile_expression(index_item) for index_item in entity.index]
        )
    else:
        content = CompiledNull()

    return entity.id.name, CompiledEntity(
        entity.id.name,
        content,
        attrs
    )


@compile_entry.register(type='Macro')
def compile_macro(macro):
    arg_names = [arg.id.name for arg in macro.args]
    return macro.id.name, CompiledMacro(macro.id.name, arg_names, compile_expression(macro.expression))


def compile_hash(node, index):
    if index:
        index_item, index_tail = index[0], index[1:]
    else:
        index_item, index_tail = None, ()
    default = None
    items = {}
    for item_node in node.content:
        value = compile_value(item_node.value, index_tail)
        if item_node.default:
            default = value
        items[item_node.key.name] = value
    return CompiledHash(items, index_item, default)


def compile_property_expression(node):
    expr = compile_expression(node.expression)
    if node.computed:
        prop = compile_expression(node.property)
    else:
        prop = CompiledString(node.property.name)
    return CompiledPropertyAccess(expr, prop)


def compile_attribute_expression(node):
    expr = compile_expression(node.expression)
    if node.computed:
        attr = compile_expression(node.attribute)
    else:
        attr = CompiledString(node.attribute.name)
    return CompiledAttributeAccess(expr, attr)


expressions = {
    'Number': lambda node: CompiledNumber(node.value),
    'Identifier': lambda node: CompiledEntryAccess(node.name),
    'Variable': lambda node: CompiledVariableAccess(node.id.name),
    'GlobalsExpression': lambda node: CompiledGlobalAccess(node.id.name),
    'ConditionalExpression': lambda node: CompiledConditional(
        compile_expression(node.test), compile_expression(node.consequent), compile_expression(node.alternate)),
    'BinaryExpression': lambda node: binary_operators[node.operator.token](
        compile_expression(node.left), compile_expression(node.right)),
    'LogicalExpression': lambda node: logical_operators[node.operator.token](
        compile_expression(node.left), compile_expression(node.right)),
    'UnaryExpression': lambda node: unary_operators[node.operator.token](compile_expression(node.argument)),
    'ParenthesisExpression': lambda node: compile_expression(node.expression),
    'CallExpression': lambda node: CompiledCall(
        compile_expression(node.callee), [compile_expression(arg) for arg in node.arguments]),
    'PropertyExpression': compile_property_expression,
    'AttributeExpression': compile_attribute_expression,
    'ThisExpression': lambda node: CompiledThis(),
}

values = {
    'String': lambda node, index: CompiledString(node.content),
    'ComplexString': lambda node, index: CompiledComplexString(
        [compile_expression(item) for item in node.content], node.source),
    'Hash': compile_hash,
}


def compile_expression(node):
    name = node.__class__.__name__
    if name in expressions:
        return expressions[name](node)
    else:
        return values[name](node, ())


def compile_value(node, index):
    return values[node.__class__.__name__](node, index)


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
