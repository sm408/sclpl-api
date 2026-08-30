"""SCLPLL v2 lexer: significant indentation into a token stream.

Line-oriented and whitespace-significant. Directives start with `@` at column 0; a step
body is the indented block beneath it. Everything else about a line is left to the
parser, which knows what verbs mean.

The indentation rules are the ones Python users already have in their fingers: a
consistent unit per level, tabs and spaces not mixed within a file, and a dedent to a
column nobody opened is an error rather than a guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from sclpl.run.errors import ValidationError


class Kind(Enum):
    DIRECTIVE = auto()  # @workflow, @step, @var, ...
    LINE = auto()  # a body line: verb plus arguments
    INDENT = auto()
    DEDENT = auto()
    EOF = auto()


@dataclass(frozen=True, slots=True)
class Token:
    kind: Kind
    #: For DIRECTIVE, the word after '@'. For LINE, the first word.
    head: str = ""
    #: Everything after the head, stripped. The parser splits it further.
    rest: str = ""
    line: int = 0
    column: int = 0
    raw: str = ""

    def where(self, origin: str = "") -> str:
        prefix = f"{origin}:" if origin else "line "
        return f"{prefix}{self.line}"


def tokenize(source: str, *, origin: str = "<sclpll>") -> list[Token]:
    """Turn source text into directives, body lines, and indentation markers."""
    tokens: list[Token] = []
    indents: list[int] = [0]
    unit: int | None = None
    uses_tabs: bool | None = None

    for number, raw in enumerate(source.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue  # blank lines and comments never affect indentation

        column = _indent_width(raw)
        leading = raw[: len(raw) - len(raw.lstrip())]
        if leading:
            has_tab = "\t" in leading
            if uses_tabs is None:
                uses_tabs = has_tab
            elif has_tab != uses_tabs:
                raise ValidationError(
                    "this file mixes tabs and spaces for indentation",
                    where=f"{origin}:{number}",
                    remedies=["pick one and use it throughout; two spaces is conventional"],
                )

        if column > indents[-1]:
            if unit is None:
                unit = column - indents[-1]
            tokens.append(Token(Kind.INDENT, line=number, column=column, raw=raw))
            indents.append(column)
        else:
            while column < indents[-1]:
                indents.pop()
                tokens.append(Token(Kind.DEDENT, line=number, column=column, raw=raw))
            if column != indents[-1]:
                raise ValidationError(
                    f"this line is indented to column {column}, which does not line up "
                    f"with any enclosing block",
                    where=f"{origin}:{number}",
                    remedies=[
                        f"open blocks are at columns {', '.join(str(i) for i in indents)}",
                        "indent consistently -- two spaces per level",
                    ],
                )

        if stripped.startswith("@"):
            head, _, rest = stripped[1:].partition(" ")
            tokens.append(Token(Kind.DIRECTIVE, head.strip(), rest.strip(), number, column, raw))
        else:
            head, _, rest = stripped.partition(" ")
            tokens.append(Token(Kind.LINE, head.strip(), rest.strip(), number, column, raw))

    while len(indents) > 1:
        indents.pop()
        tokens.append(Token(Kind.DEDENT, line=len(source.splitlines()) + 1))
    tokens.append(Token(Kind.EOF, line=len(source.splitlines()) + 1))
    return tokens


def _indent_width(raw: str, tab_width: int = 4) -> int:
    width = 0
    for char in raw:
        if char == " ":
            width += 1
        elif char == "\t":
            width += tab_width - (width % tab_width)
        else:
            break
    return width


def split_args(rest: str) -> list[str]:
    """Split a line's arguments, respecting quotes, interpolation, and JSON.

    `header Authorization: Bearer {{@auth.token}}` is three tokens, not five: the
    interpolation is opaque and the quoted string is one unit. A JSON literal is one
    unit too -- `rename @products {"sku": "code"}` is two arguments, not three -- so a
    mapping or a list can be written where one is wanted.

    `{{` is read as interpolation before a bare `{`, so an object literal cannot start
    with another object. Write a space -- `{ {"a": 1} }` -- in the rare case it must.
    """
    args: list[str] = []
    current: list[str] = []
    depth = 0
    brackets = 0
    quote: str | None = None
    index = 0

    while index < len(rest):
        char = rest[index]
        if quote is not None:
            current.append(char)
            if char == quote and (index == 0 or rest[index - 1] != "\\"):
                quote = None
            index += 1
            continue
        if char in "'\"":
            quote = char
            current.append(char)
            index += 1
            continue
        if rest.startswith("{{", index):
            depth += 1
            current.append("{{")
            index += 2
            continue
        if rest.startswith("}}", index) and depth:
            depth -= 1
            current.append("}}")
            index += 2
            continue
        if char in "{[":
            brackets += 1
        elif char in "}]" and brackets:
            brackets -= 1
        if char.isspace() and depth == 0 and brackets == 0:
            if current:
                args.append("".join(current))
                current = []
            index += 1
            continue
        current.append(char)
        index += 1

    if quote is not None:
        raise ValidationError(
            "unterminated string on this line",
            remedies=[f"add a closing {quote}"],
        )
    if current:
        args.append("".join(current))
    return args


def unquote(text: str) -> str:
    """Strip surrounding quotes if present, leaving the contents alone."""
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    return text
