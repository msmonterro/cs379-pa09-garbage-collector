"""
PA 4: The USILang Symbol Table -- starter.

Complete Environment and check_program below. See
PA_04_The_USILang_Symbol_Table.md, Part B, for the full requirements.
"""

from typing import Optional
from gc_heap import retain, release
from cells import Cell

from parser import Assignment, BinOp, Declaration, Number, Program, Variable


class SemanticError(Exception):
    pass


class Environment:
    def __init__(self, parent: Optional["Environment"] = None, heap=None) -> None:
        self.parent = parent
        self.heap = heap if heap is not None else (parent.heap if parent else None)
        if parent is not None and parent.heap is not self.heap:
            raise ValueError("Parent environment belongs to another heap")
        self._names: dict = {}
        self._released = False
        self.handle = self.heap.allocate(self) if self.heap else None
        if self.heap and parent is not None:
            self.heap.incref(parent.handle)

    def assign(self, name, value):
        if name not in self._names:
            if self.parent is not None:
                return self.parent.assign(name, value)
            return self.resolve(name)
        old = self._names[name]
        if isinstance(old, Cell):
            old.value = value
        else:
            if self.heap:
                retain(value, self.heap)
            self._names[name] = value
            if self.heap:
                release(old, self.heap)

    def close(self):
        """Drop the activation/root ownership; captures may keep this env alive."""
        if not self._released:
            self._released = True
            if self.heap:
                self.heap.decref(self.handle)

    def gc_release(self):
        for value in self._names.values():
            if isinstance(value, Cell):
                value.unbind(self.heap)
            else:
                release(value, self.heap)
        self._names.clear()
        if self.parent is not None:
            self.heap.decref(self.parent.handle)
            self.parent = None

    def define(self, name: str, line: int) -> None:
        if name in self._names:
            original_line = self._names[name]
            raise SemanticError(
                f"Duplicate declaration of '{name}' "
                f"(line {line}; originally declared line {original_line})."
            )

        if self.heap:
            if isinstance(line, Cell):
                line.bind(self.heap)
            else:
                retain(line, self.heap)
        self._names[name] = line

    def resolve(self, name: str, line: Optional[int] = None) -> int:
        if name in self._names:
            return self._names[name]

        if self.parent is not None:
            return self.parent.resolve(name, line)

        if line is None:
            raise SemanticError(f"Use of undeclared variable '{name}'.")

        raise SemanticError(
            f"Use of undeclared variable '{name}' (line {line})."
        )


def check_program(ast: Program) -> Environment:
    env = Environment(parent=None)

    def check_expr(expr: object) -> None:
        if isinstance(expr, Number):
            return

        if isinstance(expr, Variable):
            env.resolve(expr.name, expr.line)
            return

        if isinstance(expr, BinOp):
            check_expr(expr.left)
            check_expr(expr.right)
            return

    for statement in ast.statements:
        if isinstance(statement, Declaration):
            check_expr(statement.expr)
            env.define(statement.name, statement.line)

        elif isinstance(statement, Assignment):
            env.resolve(statement.name, statement.line)
            check_expr(statement.expr)

    return env