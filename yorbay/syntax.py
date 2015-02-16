from collections import namedtuple

Position = namedtuple('Position', ('line', 'column', 'origin'))


class L20n(object):
    def __init__(self, entries):
        self.entries = entries


class Identifier(object):
    def __init__(self, name):
        self.name = name


class Macro(object):
    def __init__(self, id, args, expression):
        self.id = id
        self.args = args
        self.expression = expression


class Variable(object):
    def __init__(self, id):
        self.id = id


class GlobalsExpression(object):
    def __init__(self, id):
        self.id = id


class Comment(object):
    def __init__(self, content):
        self.content = content


class ImportStatement(object):
    def __init__(self, uri):
        self.uri = uri


class Entity(object):
    def __init__(self, id, value, index, attrs, local=None):
        self.id = id
        self.value = value
        self.index = index
        self.attrs = attrs
        self.local = self.id.name.startswith('_') if local is None else local


class Attribute(object):
    def __init__(self, key, value, index, local=None):
        self.key = key
        self.value = value
        self.index = index
        self.local = self.key.name.startswith('_') if local is None else local


class HashItem(object):
    def __init__(self, key, value, default):
        self.key = key
        self.value = value
        self.default = default


class Hash(object):
    def __init__(self, content):
        self.content = content


class ConditionalExpression(object):
    def __init__(self, test, consequent, alternate):
        self.test = test
        self.consequent = consequent
        self.alternate = alternate


class LogicalExpression(object):
    def __init__(self, operator, left, right):
        self.operator = operator
        self.left = left
        self.right = right


class BinaryExpression(object):
    def __init__(self, operator, left, right):
        self.operator = operator
        self.left = left
        self.right = right


class LogicalOperator(object):
    def __init__(self, token):
        self.token = token


class BinaryOperator(object):
    def __init__(self, token):
        self.token = token


class UnaryExpression(object):
    def __init__(self, operator, argument):
        self.operator = operator
        self.argument = argument


class UnaryOperator(object):
    def __init__(self, token):
        self.token = token


class ParenthesisExpression(object):
    def __init__(self, expression):
        self.expression = expression


class PropertyExpression(object):
    def __init__(self, expression, property, computed):
        self.expression = expression
        self.property = property
        self.computed = computed


class AttributeExpression(object):
    def __init__(self, expression, attribute, computed):
        self.expression = expression
        self.attribute = attribute
        self.computed = computed


class ThisExpression(object):
    def __init__(self):
        pass


class CallExpression(object):
    def __init__(self, callee, arguments):
        self.callee = callee
        self.arguments = arguments


class Number(object):
    def __init__(self, value):
        self.value = value


class String(object):
    def __init__(self, content):
        self.content = content


class ComplexString(object):
    def __init__(self, content, source):
        self.content = content
        self.source = source
