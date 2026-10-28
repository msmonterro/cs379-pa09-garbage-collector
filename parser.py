"""
USILang parser dependency: completed PA 3 interface.

Complete the parsing functions below. AST node types are already
defined -- do not modify them. See the assignment,
Part B, for the full requirements.
"""

from dataclasses import dataclass, field
from typing import List

from lexer import Token, tokenize


@dataclass
class Program:
    statements: list


@dataclass
class Declaration:
    name: str
    expr: object
    line: int


@dataclass
class Assignment:
    name: str
    expr: object
    line: int


@dataclass
class BinOp:
    op: str
    left: object
    right: object
    line: int


@dataclass
class Number:
    value: int
    line: int


@dataclass
class Variable:
    name: str
    line: int


@dataclass
class NewObject:
    class_name: str
    line: int


@dataclass
class Null:
    line: int


@dataclass
class Field:
    receiver: object
    name: str
    line: int


@dataclass
class FieldAssignment:
    receiver: object
    name: str
    expr: object
    line: int


class ParseError(Exception):
    pass


class _ParserState:
    """Given: a small cursor wrapper over the token list. Not required to use, but handy."""

    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, type_: str) -> Token:
        tok = self.peek()
        if tok.type != type_:
            raise ParseError(f"Line {tok.line}: expected {type_}, found {tok.type} ({tok.lexeme!r}).")
        return self.advance()


def parse_factor(state: _ParserState):
    tok = state.peek()
    if tok.type == "NUMBER":
        state.advance()
        return Number(int(tok.lexeme), tok.line)
    if tok.type == "IDENT":
        state.advance()
        if tok.lexeme == "null":
            return Null(tok.line)
        if state.peek().type == "LPAREN":
            state.advance()
            state.expect("RPAREN")
            return NewObject(tok.lexeme, tok.line)
        expr = Variable(tok.lexeme, tok.line)
        while state.peek().type == "DOT":
            state.advance()
            name = state.expect("IDENT")
            expr = Field(expr, name.lexeme, name.line)
        return expr
    if tok.type == "LPAREN":
        state.advance()
        expr = parse_expr(state)
        state.expect("RPAREN")
        return expr
    raise ParseError(f"Line {tok.line}: expected a number, variable, or '(', found {tok.type}.")


def parse_term(state: _ParserState):
    expr = parse_factor(state)
    while state.peek().type in ("STAR", "SLASH"):
        op = state.advance()
        expr = BinOp(op.lexeme, expr, parse_factor(state), op.line)
    return expr


def parse_expr(state: _ParserState):
    expr = parse_term(state)
    while state.peek().type in ("PLUS", "MINUS"):
        op = state.advance()
        expr = BinOp(op.lexeme, expr, parse_term(state), op.line)
    return expr


def parse_declaration(state: _ParserState) -> Declaration:
    start = state.expect("LET")
    name = state.expect("IDENT")
    state.expect("ASSIGN")
    expr = parse_expr(state)
    state.expect("SEMI")
    return Declaration(name.lexeme, expr, start.line)


def parse_assignment(state: _ParserState) -> Assignment:
    target = parse_factor(state)
    state.expect("ASSIGN")
    expr = parse_expr(state)
    state.expect("SEMI")
    if isinstance(target, Variable):
        return Assignment(target.name, expr, target.line)
    if isinstance(target, Field):
        return FieldAssignment(target.receiver, target.name, expr, target.line)
    raise ParseError("Assignment target must be a variable or field")


def parse_statement(state: _ParserState):
    tok = state.peek()
    if tok.type == "LET":
        return parse_declaration(state)
    if tok.type == "IDENT":
        return parse_assignment(state)
    raise ParseError(f"Line {tok.line}: expected a declaration or assignment, found {tok.type}.")


def parse_program(state: _ParserState) -> Program:
    statements = []
    while state.peek().type != "EOF":
        statements.append(parse_statement(state))
    state.expect("EOF")
    return Program(statements)


def parse(tokens: List[Token], heap=None) -> Program:
    state = _ParserState(tokens)
    program = parse_program(state)
    if heap is not None:
        program.handle = heap.track_ast(program)
    return program
