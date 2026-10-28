"""
USILang lexer dependency: completed PA 2 interface.

This is the same file from PA 2's repo -- copy your own working
tokenize() implementation over this stub before starting parser.py.
Every PA repo is independent (no shared filesystem across repos), so
each pipeline stage bundles its own copy of the prior stages.

Complete tokenize() below. See the assignment, Part B,
for the full requirements. Must use a single compiled master regex
with named groups -- not a hand-rolled character-by-character loop.
"""

import re
from dataclasses import dataclass
from typing import List


@dataclass
class Token:
    type: str
    lexeme: str
    line: int


class LexError(Exception):
    pass


_MASTER_RE = re.compile(
    r"(?P<COMMENT>//[^\n]*|\#[^\n]*)|(?P<NUMBER>\d+)|(?P<IDENT>[A-Za-z_]\w*)"
    r"|(?P<PLUS>\+)|(?P<MINUS>-)|(?P<STAR>\*)|(?P<SLASH>/)"
    r"|(?P<LPAREN>\()|(?P<RPAREN>\))|(?P<ASSIGN>=)|(?P<SEMI>;)"
    r"|(?P<DOT>\.)|(?P<NEWLINE>\n)"
    r"|(?P<WHITESPACE>[^\S\n]+)|(?P<MISMATCH>.)"
)


def tokenize(source: str) -> List[Token]:
    """
    Convert `source` into a list of Token objects, ending in an EOF
    token with an empty lexeme. Recognize NUMBER, IDENT, LET, PLUS,
    MINUS, STAR, SLASH, LPAREN, RPAREN, ASSIGN, SEMI. Discard
    whitespace and '#'-prefixed comments without emitting tokens for
    them. Track 1-indexed line numbers. Raise LexError (with the
    offending character and line) on unrecognized input.
    """
    tokens = []
    line = 1
    for match in _MASTER_RE.finditer(source):
        token_type = match.lastgroup
        lexeme = match.group()
        if token_type == "NEWLINE":
            line += 1
        elif token_type in ("COMMENT", "WHITESPACE"):
            continue
        elif token_type == "MISMATCH":
            raise LexError(f"Unrecognized character {lexeme!r} on line {line}.")
        else:
            if token_type == "IDENT" and lexeme == "let":
                token_type = "LET"
            tokens.append(Token(token_type, lexeme, line))
    tokens.append(Token("EOF", "", line))
    return tokens
