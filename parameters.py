"""
PA 7: The Parameter Simulator.

Complete bind_parameters, commit_value_result, and Closure below.
Cell, evaluate(), and FunctionDecl are already provided -- do not
modify them. See the assignment, Part B, for the
full requirements.

Value-result binding has two steps: bind_parameters runs at call time
and records each caller destination; commit_value_result runs after
the simulated body and copies the final local values back in parameter
order. The handout specifies both steps.

Design note 2: variables are stored as Cell objects (a mutable box),
not raw values, specifically so reference-mode parameters can share
the exact same storage as the caller's variable -- see Part A,
Questions 1-2, for why "bind directly to the caller's slot" requires
this instead of just copying a plain value.
"""

from typing import Any, List, Tuple

from parser import BinOp, Number, Variable
from symtable import Environment


from cells import Cell
from gc_heap import Handle, retain


class FunctionDecl:
    """Given: a minimal function declaration -- params and a single expr body."""

    __slots__ = ("params", "body")

    def __init__(self, params: List[str], body) -> None:
        self.params = params
        self.body = body


def evaluate(node, env: Environment):
    """Given: evaluate a PA3 expression AST node against `env` (Cells are transparently dereferenced)."""
    if isinstance(node, Number):
        return node.value
    if isinstance(node, Variable):
        val = env.resolve(node.name)
        return val.value if isinstance(val, Cell) else val
    if isinstance(node, BinOp):
        if node.op == "neg":
            return -evaluate(node.left, env)
        left = evaluate(node.left, env)
        right = evaluate(node.right, env)
        return {"+": lambda a, b: a + b, "-": lambda a, b: a - b, "*": lambda a, b: a * b, "/": lambda a, b: a / b}[node.op](left, right)
    raise ValueError(f"cannot evaluate node: {node!r}")


def assign_through(env: Environment, name: str, value: Any) -> None:
    """Given: write `value` into whatever Cell `name` resolves to (mutates in place, does not rebind)."""
    cell = env.resolve(name)
    if not isinstance(cell, Cell):
        raise TypeError(f"'{name}' is not bound to a Cell -- did you forget to wrap it?")
    cell.value = value


def bind_parameters(param_specs: List[Tuple[str, str]], arg_nodes: list, caller_env: Environment, callee_record) -> None:
    """
    Populate callee_record.locals_env according to each parameter's
    mode ("value", "reference", or "value-result"). For value-result
    parameters, also record what commit_value_result needs to do the
    delayed write-back later -- store it whichever way you like (e.g.
    an attribute on callee_record such as callee_record.pending_writeback).
    """
    if len(param_specs) != len(arg_nodes):
        raise ValueError("Parameter and argument counts must match.")

    if caller_env.heap is not callee_record.locals_env.heap:
        raise ValueError("Caller and callee must use the same heap")
    callee_record.pending_writeback = []
    for (name, mode), argument in zip(param_specs, arg_nodes):
        if mode == "value":
            # Copy the value into private storage, not the caller's Cell.
            local_cell = Cell(evaluate(argument, caller_env))
        elif mode in ("reference", "value-result"):
            if not isinstance(argument, Variable):
                raise TypeError(f"{mode} argument for '{name}' must be a variable.")
            destination = caller_env.resolve(argument.name)
            if not isinstance(destination, Cell):
                raise TypeError(f"Argument '{argument.name}' must resolve to a Cell.")
            if mode == "reference":
                local_cell = destination
            else:
                local_cell = Cell(destination.value)
                # Save the actual destination now, in declaration order.
                callee_record.pending_writeback.append((local_cell, destination))
        else:
            raise ValueError(f"Unknown parameter mode: {mode!r}.")
        callee_record.locals_env.define(name, local_cell)


def commit_value_result(callee_record, caller_env: Environment) -> None:
    """
    For every value-result parameter bound by bind_parameters on this
    callee_record, copy its FINAL local value back into the caller's
    corresponding variable now (call this only after the callee's body
    has finished running).
    """
    # Destinations were resolved at call time; do not resolve names again.
    for local_cell, destination in getattr(callee_record, "pending_writeback", []):
        destination.value = local_cell.value
    callee_record.pending_writeback = []


class Closure:
    def __init__(self, declaration: FunctionDecl, defining_env: Environment) -> None:
        self.declaration = declaration
        self.defining_env = defining_env
        self.heap = defining_env.heap
        self.handle = None
        if self.heap:
            self.heap.incref(defining_env.handle)
            self._declaration_handle = self.heap.track_ast(declaration)
            self.handle = self.heap.allocate(self)

    def gc_release(self):
        self.heap.decref(self.defining_env.handle)
        self.heap.decref(self._declaration_handle)

    def call(self, args: list, caller_env: Environment):
        """
        Create the callee Environment as a child of self.defining_env
        (NOT caller_env) -- this is what makes closure capture work.
        Bind each declaration.params[i] to args[i] (already-evaluated
        values, wrapped in a Cell), then evaluate declaration.body in
        that new environment and return the result.
        """
        if len(args) != len(self.declaration.params):
            raise ValueError("Parameter and argument counts must match.")
        from frames import ActivationRecord, CallStack
        callee_env = Environment(parent=self.defining_env)
        stack = CallStack()
        stack.push(ActivationRecord("closure", {}, callee_env, "return", None, None))
        try:
            for name, value in zip(self.declaration.params, args):
                callee_env.define(name, Cell(value))
            result = evaluate(self.declaration.body, callee_env)
            # Return an owned reference so frame teardown cannot free the result.
            if self.heap:
                retain(result, self.heap)
            return result
        finally:
            stack.pop()
