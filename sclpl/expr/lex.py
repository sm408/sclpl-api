"""Expression lexer.

Hand-written, like the parser: the language is small and the error messages matter more
than the generality a generated lexer would buy. Every token carries its offset so a
diagnostic can point at the character that broke.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from sclpl.run.errors import ExpressionError


class Kind(Enum):
    NUMBER = auto()
    STRING = auto()
    IDENT = auto()
    REF = auto()  # @name
    OP = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LBRACE = auto()
    RBRACE = auto()
    COMMA = auto()
    COLON = auto()
    DOT = auto()
    QUESTION = auto()
    PIPE = auto()
    EOF = auto()


@dataclass(frozen=True, slots=True)
class Token:
    kind: Kind
    text: str
    position: int
    value: object = None

    def __str__(self) -> str:
        return self.text or self.kind.name


#: Longest first, so `>=` never lexes as `>` followed by `=`.
OPERATORS: tuple[str, ...] = (
    "**",
    "//",
    "==",
    "!=",
    "<=",
    ">=",
    "=~",
    "&&",
    "||",
    "<",
    ">",
    "+",
    "-",
    "*",
    "/",
    "%",
    "!",
    # Lexed, but only legal as a keyword-argument separator. The parser rejects it
    # anywhere else, where it can tell `f(n=1)` from a mistyped comparison.
    "=",
)

KEYWORDS: frozenset[str] = frozenset(
    {"and", "or", "not", "in", "true", "false", "null", "none", "if", "else"}
)

_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "\\": "\\",
    "'": "'",
    '"': '"',
    "0": "\0",
}


def tokenize(source: str) -> list[Token]:
    """Split ``source`` into tokens, or raise with the offset that failed."""
    tokens: list[Token] = []
    index = 0
    length = len(source)

    while index < length:
        char = source[index]

        if char in " \t\n\r":
            index += 1
            continue

        if char == "#":  # a comment runs to end of line
            while index < length and source[index] != "\n":
                index += 1
            continue

        if char == "@":
            start = index
            index += 1
            name_start = index
            while index < length and (source[index].isalnum() or source[index] in "_-"):
                index += 1
            if index == name_start:
                raise ExpressionError(
                    "'@' must be followed by a name",
                    where=_point(source, start),
                    remedies=["write @step_id to reference a step's output"],
                )
            tokens.append(Token(Kind.REF, source[start:index], start, source[name_start:index]))
            continue

        if char.isdigit() or (char == "." and index + 1 < length and source[index + 1].isdigit()):
            start = index
            seen_dot = False
            seen_exp = False
            while index < length:
                current = source[index]
                if current.isdigit() or current == "_":
                    index += 1
                elif current == "." and not seen_dot and not seen_exp:
                    seen_dot = True
                    index += 1
                elif current in "eE" and not seen_exp and index + 1 < length:
                    seen_exp = True
                    index += 1
                    if index < length and source[index] in "+-":
                        index += 1
                else:
                    break
            text = source[start:index].replace("_", "")
            value: object = float(text) if seen_dot or seen_exp else int(text)
            tokens.append(Token(Kind.NUMBER, source[start:index], start, value))
            continue

        if char in "'\"":
            tokens.append(_read_string(source, index))
            index = tokens[-1].position + len(tokens[-1].text)
            continue

        if char.isalpha() or char == "_":
            start = index
            while index < length and (source[index].isalnum() or source[index] == "_"):
                index += 1
            text = source[start:index]
            tokens.append(Token(Kind.IDENT, text, start))
            continue

        simple = {
            "(": Kind.LPAREN,
            ")": Kind.RPAREN,
            "[": Kind.LBRACKET,
            "]": Kind.RBRACKET,
            "{": Kind.LBRACE,
            "}": Kind.RBRACE,
            ",": Kind.COMMA,
            ":": Kind.COLON,
            ".": Kind.DOT,
            "?": Kind.QUESTION,
        }
        if char in simple:
            tokens.append(Token(simple[char], char, index))
            index += 1
            continue

        if char == "|":
            if index + 1 < length and source[index + 1] == "|":
                tokens.append(Token(Kind.OP, "||", index))
                index += 2
            else:
                tokens.append(Token(Kind.PIPE, "|", index))
                index += 1
            continue

        for operator in OPERATORS:
            if source.startswith(operator, index):
                tokens.append(Token(Kind.OP, operator, index))
                index += len(operator)
                break
        else:
            raise ExpressionError(
                f"unexpected character {char!r}",
                where=_point(source, index),
            )

    tokens.append(Token(Kind.EOF, "", length))
    return tokens


def _read_string(source: str, start: int) -> Token:
    quote = source[start]
    index = start + 1
    out: list[str] = []
    while index < len(source):
        char = source[index]
        if char == "\\":
            if index + 1 >= len(source):
                break
            following = source[index + 1]
            out.append(_ESCAPES.get(following, "\\" + following))
            index += 2
            continue
        if char == quote:
            text = source[start : index + 1]
            return Token(Kind.STRING, text, start, "".join(out))
        out.append(char)
        index += 1
    raise ExpressionError(
        "unterminated string",
        where=_point(source, start),
        remedies=[f"add a closing {quote}"],
    )


def _point(source: str, index: int) -> str:
    """A short quotation of the source with the offending offset marked."""
    window = 24
    left = max(0, index - window)
    right = min(len(source), index + window)
    excerpt = source[left:right]
    caret = " " * (index - left) + "^"
    prefix = "…" if left > 0 else ""
    return f"{prefix}{excerpt}\n{' ' * len(prefix)}{caret}"
