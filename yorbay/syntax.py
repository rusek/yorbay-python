from collections import namedtuple

Position = namedtuple('Position', ('line', 'column'))


class L20n(object):
    def __init__(self, entries):
        self.entries = entries

    def to_json(self):
        return dict(type='L20n', entries=[entry.to_json() for entry in self.entries])


class Identifier(object):
    def __init__(self, name):
        self.name = name

    def to_json(self):
        return dict(type='Identifier', name=self.name)


class Macro(object):
    def __init__(self, id, args, expression):
        self.id = id
        self.args = args
        self.expression = expression

    def to_json(self):
        return dict(type='Macro', id=self.id.to_json(), args=[arg.to_json() for arg in self.args],
                    expression=self.expression.to_json())


class Variable(object):
    def __init__(self, id):
        self.id = id

    def to_json(self):
        return dict(type='Variable', id=self.id.to_json())


class GlobalsExpression(object):
    def __init__(self, id):
        self.id = id

    def to_json(self):
        return dict(type='GlobalsExpression', id=self.id.to_json())


class Comment(object):
    def __init__(self, content):
        self.content = content

    def to_json(self):
        return dict(type='Comment', content=self.content)


class ImportStatement(object):
    def __init__(self, uri):
        self.uri = uri

    def to_json(self):
        return dict(type='ImportStatement', uri=self.uri.to_json())


class Entity(object):
    def __init__(self, id, value, index, attrs):
        self.id = id
        self.value = value
        self.index = index
        self.attrs = attrs

    @property
    def local(self):
        return self.id.name.startswith('_')

    def to_json(self):
        return dict(type='Entity', id=self.id.to_json(), value=None if self.value is None else self.value.to_json(),
                    index=None if self.index is None else [arg.to_json() for arg in self.index],
                    attrs=None if self.attrs is None else [attr.to_json() for attr in self.attrs], local=self.local)


class Attribute(object):
    def __init__(self, key, value, index):
        self.key = key
        self.value = value
        self.index = index

    @property
    def local(self):
        return self.key.name.startswith('_')

    def to_json(self):
        return dict(type='Attribute', key=self.key.to_json(), value=self.value.to_json(),
                    index=[arg.to_json() for arg in self.index], local=self.local)


class HashItem(object):
    def __init__(self, key, value, default):
        self.key = key
        self.value = value
        self.default = default

    def to_json(self):
        return dict(type='HashItem', key=self.key.to_json(), value=self.value.to_json(), default=self.default)


class Hash(object):
    def __init__(self, content):
        self.content = content

    def to_json(self):
        return dict(type='Hash', content=[item.to_json() for item in self.content])


class ConditionalExpression(object):
    def __init__(self, test, consequent, alternate):
        self.test = test
        self.consequent = consequent
        self.alternate = alternate

    def to_json(self):
        return dict(type='ConditionalExpression', test=self.test.to_json(), consequent=self.consequent.to_json(),
                    alternate=self.alternate.to_json())


class LogicalExpression(object):
    def __init__(self, operator, left, right):
        self.operator = operator
        self.left = left
        self.right = right

    def to_json(self):
        return dict(type='LogicalExpression', operator=self.operator.to_json(), left=self.left.to_json(),
                    right=self.right.to_json())


class BinaryExpression(object):
    def __init__(self, operator, left, right):
        self.operator = operator
        self.left = left
        self.right = right

    def to_json(self):
        return dict(type='BinaryExpression', operator=self.operator.to_json(), left=self.left.to_json(),
                    right=self.right.to_json())


class LogicalOperator(object):
    def __init__(self, token):
        self.token = token

    def to_json(self):
        return dict(type='LogicalOperator', token=self.token)


class BinaryOperator(object):
    def __init__(self, token):
        self.token = token

    def to_json(self):
        return dict(type='BinaryOperator', token=self.token)


class UnaryExpression(object):
    def __init__(self, operator, argument):
        self.operator = operator
        self.argument = argument

    def to_json(self):
        return dict(type='UnaryExpression', operator=self.operator.to_json(), argument=self.argument.to_json())


class UnaryOperator(object):
    def __init__(self, token):
        self.token = token

    def to_json(self):
        return dict(type='UnaryOperator', token=self.token)


class ParenthesisExpression(object):
    def __init__(self, expression):
        self.expression = expression

    def to_json(self):
        return dict(type='ParenthesisExpression', expression=self.expression.to_json())


class PropertyExpression(object):
    def __init__(self, expression, property, computed):
        self.expression = expression
        self.property = property
        self.computed = computed

    def to_json(self):
        return dict(type='PropertyExpression', expression=self.expression.to_json(), property=self.property.to_json(),
                    computed=self.computed)


class AttributeExpression(object):
    def __init__(self, expression, attribute, computed):
        self.expression = expression
        self.attribute = attribute
        self.computed = computed

    def to_json(self):
        return dict(type='AttributeExpression', expression=self.expression.to_json(),
                    attribute=self.attribute.to_json(), computed=self.computed)


class ThisExpression(object):
    def __init__(self):
        pass

    def to_json(self):
        return dict(type='ThisExpression')


class CallExpression(object):
    def __init__(self, callee, arguments):
        self.callee = callee
        self.arguments = arguments

    def to_json(self):
        return dict(type='CallExpression', callee=self.callee.to_json(),
                    arguments=[arg.to_json() for arg in self.arguments])


class Number(object):
    def __init__(self, value):
        self.value = value

    def to_json(self):
        return dict(type='Number', value=self.value)


class String(object):
    def __init__(self, content):
        self.content = content

    def to_json(self):
        return dict(type='String', content=self.content)


class ComplexString(object):
    def __init__(self, content, source):
        self.content = content
        self.source = source

    def to_json(self):
        return dict(type='ComplexString', content=[item.to_json() for item in self.content], source=self.source)
