"""Executable PA9 examples using the earlier lexer, AST, cells and frames."""
from cells import Cell
from dispatcher import ClassDecl, USIObject, build_vtable
from frames import ActivationRecord, CallStack
from gc_heap import GCHeap, retain, release
from lexer import tokenize
from parser import (parse, Declaration, Assignment, FieldAssignment,
                    NewObject, Null, Field, Variable, Number, BinOp)
from symtable import Environment


class Interpreter:
    def __init__(self, heap=None):
        self.heap = heap if heap is not None else GCHeap()
        self.env = Environment(heap=self.heap)
        self.stack = CallStack()
        self.stack.push(ActivationRecord('main', {}, self.env, 'exit', None, None))
        self.classes = {name: build_vtable(ClassDecl(name, {})) for name in ('Dog', 'Node')}

    def eval_owned(self, node):
        """An object-valued expression returns one owned temporary reference."""
        if isinstance(node, NewObject):
            return USIObject(self.classes[node.class_name], {}, self.heap).handle
        if isinstance(node, Null):
            return None
        if isinstance(node, Number):
            return node.value
        if isinstance(node, Variable):
            value = self.env.resolve(node.name)
            value = value.value if isinstance(value, Cell) else value
            retain(value, self.heap)
            return value
        if isinstance(node, Field):
            receiver = self.eval_owned(node.receiver)
            try:
                value = self.heap.get(receiver).fields.get(node.name)
                retain(value, self.heap)
                return value
            finally:
                release(receiver, self.heap)
        if isinstance(node, BinOp):
            left = self.eval_owned(node.left)
            try:
                right = self.eval_owned(node.right)
                try:
                    return {'+': lambda: left + right, '-': lambda: left - right,
                            '*': lambda: left * right, '/': lambda: left / right}[node.op]()
                finally:
                    release(right, self.heap)
            finally:
                release(left, self.heap)
        raise TypeError(f'Unsupported expression: {node!r}')

    def execute(self, statement):
        value = self.eval_owned(statement.expr)
        try:
            if isinstance(statement, Declaration):
                self.env.define(statement.name, Cell(value))
            elif isinstance(statement, Assignment):
                self.env.assign(statement.name, value)
            elif isinstance(statement, FieldAssignment):
                receiver = self.eval_owned(statement.receiver)
                try:
                    self.heap.get(receiver).fields[statement.name] = value
                finally:
                    release(receiver, self.heap)
            else:
                raise TypeError(f'Unsupported statement: {statement!r}')
        finally:
            release(value, self.heap)

    def run(self, source, after_statement=None):
        program = parse(tokenize(source), heap=self.heap)
        try:
            for index, statement in enumerate(program.statements, 1):
                self.execute(statement)
                if after_statement:
                    after_statement(index, self)
        finally:
            self.heap.decref(program.handle)

    def close(self):
        while self.stack._records:
            self.stack.pop()
