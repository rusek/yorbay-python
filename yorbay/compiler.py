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
    def __init__(self, entries, vars):
        self.entries = entries
        self.vars = vars
        self.globals = {}
        self.this = None
        self._stack = []
        self._vars = vars

    def push(self, this, local_vars):
        self._stack.append((self.this, self.vars))
        new_vars = {}
        new_vars.update(self._vars)
        new_vars.update(local_vars)
        self.this = this
        self.vars = new_vars

    def pop(self):
        self.this, self.vars = self._stack.pop()

    def capture(self):
        return self.this, self.vars

    def push_captured(self, state):
        self._stack.append((self.this, self.vars))
        self.this, self.vars = state


class L20n(object):
    def __init__(self, entries):
        self._entries = entries

    def make_env(self, vars):
        return Env(self._entries, vars)

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


class CompiledEntity(object):
    def __init__(self, name, content):
        self._name = name
        self._content = content

    def invoke(self, env):
        env.push(self, {})
        try:
            return self._content.evaluate(env)
        finally:
            env.pop()


class CompiledMacro(object):
    def __init__(self, name, arg_names, expr):
        self._name = name
        self._arg_names = arg_names
        self._expr = expr

    def invoke(self, env, args):
        assert len(args) == len(self._arg_names)
        env.push(self, dict(zip(self._arg_names, args)))
        try:
            return self._expr.evaluate(env)
        finally:
            env.pop()


class CompiledExpr(object):
    def evaluate(self, env):
        raise NotImplementedError

    def evaluate_resolved(self, env):
        val = self.evaluate(env)
        while True:
            if isinstance(val, CompiledEntity):
                val = val.invoke(env)
            elif isinstance(val, LazyHash):
                val = val.get_default()
            else:
                assert get_type(val) is not OBJECT
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
        assert isinstance(callee_val, CompiledMacro)
        args = [arg.evaluate(env) for arg in self._args]
        return callee_val.invoke(env, args)


class CompiledPropertyAccess(CompiledExpr):
    def __init__(self, expr, prop):
        self._expr = expr
        self._prop = prop

    def evaluate(self, env):
        expr_val = self._expr.evaluate(env)
        prop_val = self._prop.evaluate_string(env)

        if isinstance(expr_val, CompiledEntity):
            expr_val = expr_val.invoke(env)

        return expr_val[prop_val]  # xxxxxxx check if operation supported


class LazyHash(object):
    def __init__(self, env, items, default):
        self._env = env
        self._env_state = env.capture()
        self._items = items
        self._default = default

    def __getitem__(self, key):
        value = self._items[key]
        self._env.push_captured(self._env_state)
        try:
            return value.evaluate(self._env)
        finally:
            self._env.pop()

    def get_default(self):
        assert self._default, 'no default'
        self._env.push_captured(self._env_state)
        try:
            return self._default.evaluate(self._env)
        finally:
            self._env.pop()


class CompiledHash(CompiledExpr):
    def __init__(self, items, default):
        self._items = items
        self._default = default

    def evaluate(self, env):
        return LazyHash(env, self._items, self._default)


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
    assert entity.value is not None
    assert entity.index is None
    assert entity.attrs is None
    return entity.id.name, CompiledEntity(entity.id.name, compile_value(entity.value))


@compile_entry.register(type='Macro')
def compile_macro(macro):
    arg_names = [arg.id.name for arg in macro.args]
    return macro.id.name, CompiledMacro(macro.id.name, arg_names, compile_expression(macro.expression))


def compile_hash(node):
    default = None
    items = {}
    for item_node in node.content:
        value = compile_expression(item_node.value)
        if item_node.default:
            default = value
        items[item_node.key.name] = value
    return CompiledHash(items, default)


def compile_property_expression(node):
    expr = compile_expression(node.expression)
    if node.computed:
        prop = compile_expression(node.property)
    else:
        prop = CompiledString(node.property.name)
    return CompiledPropertyAccess(expr, prop)


expressions = {
    'String': lambda node: CompiledString(node.content),
    'Number': lambda node: CompiledNumber(node.value),
    'Identifier': lambda node: CompiledIdentifier(node.name),
    'Variable': lambda node: CompiledVariable(node.id.name),
    'GlobalsExpression': lambda node: CompiledGlobals(node.id.name),
    'ComplexString': lambda node: CompiledComplexString([compile_expression(item) for item in node.content]),
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
    'Hash': compile_hash,
    'ThisExpression': lambda node: CompiledThis(),
}

# Missing: AttributeExpression
# Missing entries: Entity with index, Entity with attributes


def compile_expression(node):
    return expressions[node.__class__.__name__](node)

compile_value = compile_expression


# @compile_expression.register(type='String')
# def compile_string(string):
#     return CompiledString(string.content)
#
#
# @compile_expression.register(type='Number')
# def compile_number(node):
#     return CompiledNumber(node.value)
#
#
# @compile_expression.register(type='Identifier')
# def compile_identifier(node):
#     return CompiledIdentifier(node.name)
#
#
# @compile_expression.register(type='ComplexString')
# def compile_complex_string(node):
#     return CompiledComplexString([compile_expression(item) for item in node.content])
#
#
# @compile_expression.register(type='ConditionalExpression')
# def compile_conditional_expression(node):
#     return CompiledConditional(
#         compile_expression(node.test),
#         compile_expression(node.consequent),
#         compile_expression(node.alternate),
#     )


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


# @compile_expression.register(type='BinaryExpression')
# def compile_binary_expression(node):
#     return binary_operators[node.operator.token](compile_expression(node.left), compile_expression(node.right))


logical_operators = {
    '&&': CompiledAnd,
    '||': CompiledOr,
}


# @compile_expression.register(type='LogicalExpression')
# def compile_binary_expression(node):
#     return logical_operators[node.operator.token](compile_expression(node.left), compile_expression(node.right))


unary_operators = {
    '!': CompiledNot,
    '-': CompiledNegate,
    '+': CompiledPositive,
}


# @compile_expression.register(type='UnaryExpression')
# def compile_unary_expression(node):
#     return unary_operators[node.operator.token](compile_expression(node.argument))
#
#
# @compile_expression.register(type='ParenthesisExpression')
# def compile_parenthesis_expression(node):
#     return compile_expression(node.expression)


def compile_and_resolve(l20n, name, **values):
    compiled_l20n = compile_l20n(l20n)
    return compiled_l20n.get(name).invoke(compiled_l20n.make_env(values))