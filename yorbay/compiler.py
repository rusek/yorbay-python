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


class Env(object):
    def __init__(self, entries, vars, globals, this):
        self.entries = entries
        self.vars = vars
        self.globals = globals
        self.this = this

    def copy(self, this, local_vars=None):
        if local_vars:
            vars = self.vars.copy()
            vars.update(local_vars)
        else:
            vars = self.vars

        return Env(self.entries, vars, self.globals, this)


class L20n(object):
    def __init__(self, entries):
        self._entries = entries

    def make_env(self, vars):
        entries = {}
        env = Env(entries, vars, {}, None)
        for k, v in self._entries.iteritems():
            entries[k] = v.bind(env)
        return env

    def get(self, name):
        return self._entries.get(name)


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
    def __init__(self, entity, env):
        self._entity = entity
        self._env = env.copy(self)

    def invoke(self):
        return self._entity._content.evaluate(self._env)

    resolve = resolve_once = invoke

    def __getitem__(self, key):
        return self._entity._content.evaluate(self._env)[key]  # xxxx should be consistent with PropertyAccess!

    def get_attribute(self, name):
        return self._entity._attrs[name].evaluate(self._env)


class CompiledEntity(object):
    def __init__(self, name, content, attrs):
        self._name = name
        self._content = content
        self._attrs = attrs

    def bind(self, env):
        return BoundEntity(self, env)


class BoundMacro(object):
    def __init__(self, macro, env):
        self._macro = macro
        self._env = env

    def invoke(self, args):
        assert len(args) == len(self._macro._arg_names)
        return self._macro._expr.evaluate(self._env.copy(self, dict(zip(self._macro._arg_names, args))))


class CompiledMacro(object):
    def __init__(self, name, arg_names, expr):
        self._name = name
        self._arg_names = arg_names
        self._expr = expr

    def bind(self, env):
        return BoundMacro(self, env)


class CompiledExpr(object):
    def evaluate(self, env):
        raise NotImplementedError

    def evaluate_resolved(self, env):
        val = self.evaluate(env)
        while True:
            if isinstance(val, Resolvable):
                val = val.resolve_once()
            else:
                assert get_type(val) is not OBJECT, val
                return val

    def evaluate_bool(self, env):
        val = self.evaluate_resolved(env)
        assert get_type(val) is BOOL
        return val

    def evaluate_string(self, env):
        val = self.evaluate_resolved(env)
        assert get_type(val) is STRING
        return val

    def evaluate_number(self, env):
        val = self.evaluate_resolved(env)
        assert get_type(val) is NUMBER
        return val

    def evaluate_placeable(self, env, buf):
        val = self.evaluate_resolved(env)
        type = get_type(val)
        if type is NUMBER:
            val = str(val)
        else:
            assert type is STRING
        buf.append(val)


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
        assert left_type is right_type and (left_type is NUMBER or left_type is STRING)
        return left == right

    evaluate_bool = evaluate


class CompiledNotEqual(CompiledBinary):
    def evaluate(self, env):
        left, right = self._left.evaluate_resolved(env), self._right.evaluate_resolved(env)
        left_type, right_type = get_type(left), get_type(right)
        assert left_type is right_type and (left_type is NUMBER or left_type is STRING)
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
        assert left_type is right_type and (left_type is NUMBER or left_type is STRING)
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


class CompiledIdentifier(CompiledNamed):
    def evaluate(self, env):
        return env.entries[self._name]  # KeyError


class CompiledVariable(CompiledNamed):
    def evaluate(self, env):
        return env.vars[self._name]  # KeyError


class CompiledGlobals(CompiledNamed):
    def evaluate(self, env):
        return env.globals[self._name]  # KeyError


class CompiledComplexString(CompiledExpr):
    def __init__(self, content):
        self._content = content

    def evaluate(self, env):
        buf = []
        for item in self._content:
            item.evaluate_placeable(env, buf)
        return ''.join(buf)

    evaluate_string = evaluate

    def evaluate_placeable(self, env, buf):
        for item in self._content:
            item.evaluate_placeable(env, buf)


class CompiledUnary(CompiledExpr):
    def __init__(self, arg):
        self._arg = arg


class CompiledNot(CompiledUnary):
    def evaluate(self, env):
        return not self._arg.evaluate_bool(env)

    evaluate_bool = evaluate


class CompiledNegate(CompiledUnary):
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
        assert isinstance(callee_val, BoundMacro)
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

        assert isinstance(expr_val, BoundEntity)
        return expr_val.get_attribute(attr_val)


class LazyHash(Resolvable):
    def __init__(self, env, items, index_item, default):
        self._env = env.copy(env.this)
        self._items = items
        self._index_item = index_item
        self._default = default

    def __getitem__(self, key):
        try:
            value = self._items[key]
        except KeyError:
            return self.get_default()
        return value.evaluate(self._env)

    def get_default(self):
        if self._index_item is not None:
            key = self._index_item.evaluate_string(self._env)
            try:
                value = self._items[key]
            except KeyError:
                pass
            else:
                return value.evaluate(self._env)

        if self._default is not None:
            return self._default.evaluate(self._env)

        assert False, 'hash key lookup failed'

    resolve_once = get_default


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


def compile_l20n(l20n):
    entries = {}
    for entry in l20n.entries:
        compiled_entry = compile_entry(entry)
        if compiled_entry is not None:
            k, v = compiled_entry
            entries[k] = v
    return L20n(entries)


compile_entry = Dispatcher()


@compile_entry.register(type='Entity')
def compile_entity(entity):
    attrs = {}
    for attr in entity.attrs or ():
        index = () if entity.index is None else [compile_expression(index_item) for index_item in entity.index]
        attrs[attr.key.name] = compile_value(attr.value, index)

    return entity.id.name, CompiledEntity(
        entity.id.name,
        compile_value(
            entity.value,
            () if entity.index is None else [compile_expression(index_item) for index_item in entity.index]
        ),
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
    'Identifier': lambda node: CompiledIdentifier(node.name),
    'Variable': lambda node: CompiledVariable(node.id.name),
    'GlobalsExpression': lambda node: CompiledGlobals(node.id.name),
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
    'ComplexString': lambda node, index: CompiledComplexString([compile_expression(item) for item in node.content]),
    'Hash': compile_hash,
}

# Missing: AttributeExpression
# Missing entries: Entity with attributes


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
    '-': CompiledNegate,
    '+': CompiledPositive,
}


def compile_and_resolve(l20n, name, **values):
    compiled_l20n = compile_l20n(l20n)
    return compiled_l20n.make_env(values).entries[name].invoke()
