from __future__ import unicode_literals

from ..compiler import (
    Resolvable, BoundEntity, CompiledEntity, BoundMacro, CompiledMacro, CompiledExpr, LazyHash,
    CompiledEntryAccess, CompiledGlobalAccess, CompiledLocalAccess, CompiledVariableAccess,
    Compiler
)
from .similarity import get_similar
from .stacktrace import attach_stack, Frame


class DebugBoundEntity(BoundEntity):
    def __init__(self, entity, lenv):
        super(DebugBoundEntity, self).__init__(entity, lenv)
        self._debug_hook = entity._debug_hook.with_barrier(True)

    def resolve(self):
        with self._debug_hook:
            return super(DebugBoundEntity, self).resolve()

    def resolve_once(self):
        with self._debug_hook:
            return self._entity._content.evaluate(self._env)

    def __getitem__(self, key):
        with self._debug_hook:
            val = self._entity._content.evaluate(self._env)
        return val[key]

    def get_attribute(self, name):
        with self._debug_hook:
            return super(DebugBoundEntity, self).get_attribute(name)

    def resolve_attribute(self, name):
        with self._debug_hook:
            return super(DebugBoundEntity, self).resolve_attribute(name)


class DebugCompiledEntity(CompiledEntity):
    def __init__(self, name, content, attrs, debug_hook):
        super(DebugCompiledEntity, self).__init__(name, content, attrs)
        self._debug_hook = debug_hook

    def bind(self, lenv):
        return DebugBoundEntity(self, lenv)


class DebugBoundMacro(BoundMacro):
    def __init__(self, macro, lenv):
        super(DebugBoundMacro, self).__init__(macro, lenv)
        self._debug_hook = macro._debug_hook.with_barrier(True)

    def invoke(self, args):
        with self._debug_hook:
            return super(DebugBoundMacro, self).invoke(args)


class DebugCompiledMacro(CompiledMacro):
    def __init__(self, name, arg_names, expr, debug_hook):
        super(DebugCompiledMacro, self).__init__(name, arg_names, expr)
        self._debug_hook = debug_hook

    def bind(self, lenv):
        return DebugBoundMacro(self, lenv)


class DebugLazyHash(Resolvable):
    def __init__(self, lazy_hash, debug_hook):
        self._lazy_hash = lazy_hash
        self._debug_hook = debug_hook.with_barrier(True)

    def __getitem__(self, key):
        with self._debug_hook:
            return self._lazy_hash[key]

    def resolve_once(self):
        with self._debug_hook:
            return self._lazy_hash.resolve_once()


class DebugCompiledEntryAccess(CompiledEntryAccess):
    def evaluate(self, env):
        try:
            return super(DebugCompiledEntryAccess, self).evaluate(env)
        except NameError:
            similar = get_similar(self._name, self._entries.keys())
            if similar:
                raise NameError('Entry "{0}" is not defined. Did you mean "{1}"?'.format(self._name, similar))

            raise


class DebugCompiledGlobalAccess(CompiledGlobalAccess):
    def evaluate(self, env):
        try:
            return super(DebugCompiledGlobalAccess, self).evaluate(env)
        except NameError:
            similar = get_similar(self._name, env.parent.globals.keys())
            if similar:
                raise NameError('Global "{0}" is not defined. Did you mean "{1}"?'.format(self._name, similar))

            raise


class DebugCompiledVariableAccess(CompiledVariableAccess):
    def __init__(self, name, local_names):
        super(DebugCompiledVariableAccess, self).__init__(name)
        self._local_names = local_names

    def evaluate(self, env):
        try:
            return super(DebugCompiledVariableAccess, self).evaluate(env)
        except NameError:
            similar = get_similar(self._name, env.parent.vars.keys() + self._local_names)
            if similar:
                raise NameError('Variable "{0}" is not defined. Did you mean "{1}"?'.format(self._name, similar))

            raise


class DebugCompiledExpr(CompiledExpr):
    def __init__(self, expr, debug_hook):
        self._expr = expr
        self._debug_hook = debug_hook

    def evaluate(self, env):
        with self._debug_hook:
            ret = self._expr.evaluate(env)

        if isinstance(ret, LazyHash):
            ret = DebugLazyHash(ret, self._debug_hook)

        return ret

    # evaluate_* methods are wrappers for evaluate that perform resolution and type checking - if
    # wrapped expression may be successfully evaluated, but resolution / type checking fails, then
    # the error is related to the outer expression (e.g. "1 && 2" should report a failure for "&&"
    # operator, because it operates on booleans only, and not for "1").


class DebugHook(object):
    def __init__(self, entry_type, entry_name, pos, barrier=False):
        self.entry_type = entry_type
        self.entry_name = entry_name
        self.pos = pos
        self._barrier = barrier

    def with_barrier(self, barrier):
        return DebugHook(self.entry_type, self.entry_name, self.pos, barrier)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            if isinstance(exc_val, basestring):
                exc_val = exc_type(exc_val)
                throw = True
            else:
                throw = False

            tb = attach_stack(exc_val)
            if tb and tb[-1] is None:
                if self._barrier:
                    tb.pop()
            else:
                tb.append(Frame(self.entry_type, self.entry_name, self.pos))
                if not self._barrier:
                    tb.append(None)

            if throw:
                raise exc_type, exc_val, exc_tb


class DebugCompiler(Compiler):
    def make_debug_hook(self, node):
        return DebugHook(self.entry_type, self.entry_name, node.pos)

    def compile_entity(self, node):
        self.begin_entity(node.id.name)

        attrs = self.compile_attributes(node.attrs)
        content = self.compile_value_with_index(node.value, node.index)
        entry = DebugCompiledEntity(node.id.name, content, attrs, self.make_debug_hook(node))

        self.finish_entry(entry)

    def compile_macro(self, node):
        arg_names = [arg.id.name for arg in node.args]
        self.begin_macro(node.id.name, arg_names)

        expr = self.compile_expression(node.expression)
        macro = DebugCompiledMacro(node.id.name, arg_names, expr, self.make_debug_hook(node))

        self.finish_entry(macro)

    def compile_globals_expression(self, node):
        return DebugCompiledGlobalAccess(node.id.name)

    def compile_identifier(self, node):
        return DebugCompiledEntryAccess(self.collected_entries, node.name)

    def compile_variable(self, node):
        var_name = node.id.name
        try:
            return CompiledLocalAccess(self.local_names.index(var_name))
        except ValueError:
            return DebugCompiledVariableAccess(var_name, self.local_names)

    def compile_value(self, node, index, depth):
        return self.wrap_compiled_expr(super(DebugCompiler, self).compile_value(node, index, depth), node)

    def compile_expression(self, node):
        return self.wrap_compiled_expr(super(DebugCompiler, self).compile_expression(node), node)

    def wrap_compiled_expr(self, expr, node):
        # expr may be already wrapped e.g. when we compile ParenthesisExpression
        # node is not available when we compile entity with empty content
        if isinstance(expr, DebugCompiledExpr) or node is None:
            return expr

        return DebugCompiledExpr(expr, self.make_debug_hook(node))
