"""Expression parser: recursive descent, producing our own AST.

Never `eval`, never `compile`, never `ast.literal_eval` on user input (invariant 7).
The only things an expression can reach are the nodes below and the operators in the
dispatch table.

Infix lowers to calls as it parses -- `a > 10` becomes `Call("gt", ...)` -- so the
evaluator sees one uniform shape. `and`, `or`, `not`, and the ternary stay as their own
nodes because they must short-circuit.
"""

from __future__ import annotations

from sclpl.expr.ast import (
    And,
    Attr,
    Call,
    DictLit,
    Expr,
    Filter,
    Index,
    Interpolation,
    ListLit,
    Literal,
    Node,
    Not,
    Or,
    Pipe,
    Projection,
    Ref,
    Slice,
    Ternary,
    Var,
    collect_refs,
)
from sclpl.expr.lex import Kind, Token, tokenize
from sclpl.run.errors import ExpressionError

#: Infix operator -> the canonical function it lowers to. The names on the right are
#: what `dispatch.py` registers, so adding an operator means adding an overload rather
#: than a branch in the evaluator.
INFIX: dict[str, str] = {
    "==": "eq",
    "!=": "ne",
    "<": "lt",
    "<=": "le",
    ">": "gt",
    ">=": "ge",
    "+": "add",
    "-": "sub",
    "*": "mul",
    "/": "div",
    "//": "floordiv",
    "%": "mod",
    "**": "pow",
    "=~": "matches",
    "in": "contains_by",
}

#: Binding power. Higher binds tighter.
PRECEDENCE: dict[str, int] = {
    "==": 3,
    "!=": 3,
    "<": 3,
    "<=": 3,
    ">": 3,
    ">=": 3,
    "=~": 3,
    "in": 3,
    "+": 4,
    "-": 4,
    "*": 5,
    "/": 5,
    "//": 5,
    "%": 5,
    "**": 6,
}

RIGHT_ASSOCIATIVE = frozenset({"**"})


def parse(source: str) -> Expr:
    """Parse a complete expression. Trailing tokens are an error, not a silent stop."""
    parser = _Parser(tokenize(source), source)
    node = parser.expression()
    parser.expect_end()
    return Expr(node=node, source=source, refs=collect_refs(node))


def parse_interpolated(source: str) -> Expr:
    """Parse a string that may contain `{{expr}}` holes.

    A string that is exactly one hole (`"{{@a.id}}"`) yields that expression directly,
    so the value keeps its type (invariant 2). Anything else becomes an
    `Interpolation`, where stringification happens at the boundary and nowhere else.

    A string that is a bare reference (`"@orders.body"`) is also an expression. Reading
    it as literal text would be worse than useless: no `@name` would be collected, so
    no dependency edge would exist (invariant 3), and the step would run before its
    input and then interpolate the reference's own source text into the request.
    """
    if "{{" not in source and source.lstrip().startswith("@"):
        return parse(source)

    parts: list[str | Node] = []
    index = 0
    while index < len(source):
        opening = source.find("{{", index)
        if opening < 0:
            parts.append(source[index:])
            break
        closing = source.find("}}", opening + 2)
        if closing < 0:
            raise ExpressionError(
                "unterminated '{{' in an interpolated string",
                where=source,
                remedies=["close it with '}}'"],
            )
        if opening > index:
            parts.append(source[index:opening])
        inner = source[opening + 2 : closing].strip()
        if not inner:
            raise ExpressionError(
                "empty '{{}}' in an interpolated string",
                where=source,
                remedies=["put an expression inside, or remove the braces"],
            )
        parts.append(parse(inner).node)
        index = closing + 2

    if len(parts) == 1 and not isinstance(parts[0], str):
        node = parts[0]
        return Expr(node=node, source=source, refs=collect_refs(node))
    if all(isinstance(part, str) for part in parts):
        literal = Literal("".join(part for part in parts if isinstance(part, str)))
        return Expr(node=literal, source=source, refs=frozenset())
    interpolation = Interpolation(tuple(parts))
    return Expr(node=interpolation, source=source, refs=collect_refs(interpolation))


def is_expression(text: str) -> bool:
    """Whether ``text`` looks like something to parse rather than a plain string."""
    return "{{" in text or text.lstrip().startswith("@")


class _Parser:
    __slots__ = ("_tokens", "_index", "_source")

    def __init__(self, tokens: list[Token], source: str) -> None:
        self._tokens = tokens
        self._index = 0
        self._source = source

    # -- grammar -----------------------------------------------------------------

    def expression(self) -> Node:
        return self.ternary()

    def ternary(self) -> Node:
        condition = self.pipeline()
        if self.at(Kind.QUESTION):
            self.advance()
            then = self.expression()
            self.consume(Kind.COLON, "expected ':' to complete the '?' branch")
            return Ternary(condition, then, self.expression())
        # Python-style `x if cond else y` reads better in a `when` clause.
        if self.at_keyword("if"):
            self.advance()
            test = self.pipeline()
            self.expect_keyword("else", "expected 'else' to complete the conditional")
            return Ternary(test, condition, self.expression())
        return condition

    def pipeline(self) -> Node:
        node = self.logical_or()
        while self.at(Kind.PIPE):
            self.advance()
            call = self.unary()
            if not isinstance(call, Call):
                raise self.error("the right side of '|' must be a function call")
            node = Pipe(node, call)
        return node

    def logical_or(self) -> Node:
        node = self.logical_and()
        while self.at_keyword("or") or self.at_operator("||"):
            self.advance()
            node = Or(node, self.logical_and())
        return node

    def logical_and(self) -> Node:
        node = self.unary_not()
        while self.at_keyword("and") or self.at_operator("&&"):
            self.advance()
            node = And(node, self.unary_not())
        return node

    def unary_not(self) -> Node:
        if self.at_keyword("not") or self.at_operator("!"):
            self.advance()
            return Not(self.unary_not())
        return self.binary(0)

    def binary(self, minimum: int) -> Node:
        left = self.unary()
        while True:
            operator = self.peek_operator()
            if operator is None:
                break
            power = PRECEDENCE[operator]
            if power < minimum:
                break
            negate = False
            if operator == "in" and self._previous_was_not():
                negate = True
            self.advance()
            next_minimum = power if operator in RIGHT_ASSOCIATIVE else power + 1
            right = self.binary(next_minimum)
            if operator == "in":
                # `x in xs` reads as membership; the overload takes the container first.
                left = Call("contains", (right, left))
                if negate:
                    left = Not(left)
            else:
                left = Call(INFIX[operator], (left, right))
        return left

    def unary(self) -> Node:
        if self.at_operator("-"):
            self.advance()
            return Call("neg", (self.unary(),))
        if self.at_operator("+"):
            self.advance()
            return self.unary()
        if self.at_keyword("not") or self.at_operator("!"):
            self.advance()
            return Not(self.unary())
        return self.postfix()

    def postfix(self) -> Node:
        node = self.primary()
        while True:
            if self.at(Kind.DOT):
                self.advance()
                token = self.current()
                if token.kind is not Kind.IDENT:
                    raise self.error("expected a field name after '.'")
                self.advance()
                node = Attr(node, token.text)
                continue
            if self.at(Kind.LBRACKET):
                node = self.subscript(node)
                continue
            if self.at(Kind.LPAREN) and isinstance(node, Var):
                node = self.call(node.name)
                continue
            break
        return node

    def subscript(self, obj: Node) -> Node:
        self.advance()  # consume '['
        if self.at_operator("*"):
            self.advance()
            self.consume(Kind.RBRACKET, "expected ']' after '[*]'")
            return Projection(obj)
        if self.at(Kind.QUESTION):
            self.advance()
            self.consume(Kind.LPAREN, "expected '(' after '[?'")
            predicate = self.expression()
            self.consume(Kind.RPAREN, "expected ')' to close the filter predicate")
            self.consume(Kind.RBRACKET, "expected ']' to close the filter")
            return Filter(obj, predicate)
        if self.at(Kind.COLON):
            self.advance()
            stop = None if self.at(Kind.RBRACKET) else self.expression()
            self.consume(Kind.RBRACKET, "expected ']' to close the slice")
            return Slice(obj, None, stop)
        index = self.expression()
        if self.at(Kind.COLON):
            self.advance()
            stop = None if self.at(Kind.RBRACKET) else self.expression()
            self.consume(Kind.RBRACKET, "expected ']' to close the slice")
            return Slice(obj, index, stop)
        self.consume(Kind.RBRACKET, "expected ']' to close the subscript")
        return Index(obj, index)

    def call(self, name: str) -> Call:
        self.advance()  # consume '('
        args: list[Node] = []
        kwargs: list[tuple[str, Node]] = []
        while not self.at(Kind.RPAREN):
            if self.at(Kind.IDENT) and self.peek(1).kind is Kind.OP and self.peek(1).text == "=":
                keyword = self.current().text
                self.advance()
                self.advance()
                kwargs.append((keyword, self.expression()))
            elif self.at(Kind.IDENT) and self.peek(1).kind is Kind.COLON:
                # `f(name: value)` -- the SCLPLL-flavoured spelling of a keyword.
                keyword = self.current().text
                self.advance()
                self.advance()
                kwargs.append((keyword, self.expression()))
            else:
                if kwargs:
                    raise self.error("positional arguments cannot follow keyword arguments")
                args.append(self.expression())
            if self.at(Kind.COMMA):
                self.advance()
                continue
            break
        self.consume(Kind.RPAREN, f"expected ')' to close the call to {name}")
        return Call(name, tuple(args), tuple(kwargs))

    def primary(self) -> Node:
        token = self.current()
        match token.kind:
            case Kind.NUMBER | Kind.STRING:
                self.advance()
                return Literal(token.value)
            case Kind.REF:
                self.advance()
                return Ref(str(token.value))
            case Kind.IDENT:
                lowered = token.text.lower()
                if lowered == "true":
                    self.advance()
                    return Literal(True)
                if lowered == "false":
                    self.advance()
                    return Literal(False)
                if lowered in ("null", "none"):
                    self.advance()
                    return Literal(None)
                if lowered == "not":
                    self.advance()
                    return Not(self.unary())
                self.advance()
                return Var(token.text)
            case Kind.LPAREN:
                self.advance()
                inner = self.expression()
                self.consume(Kind.RPAREN, "expected ')'")
                return inner
            case Kind.LBRACKET:
                return self.list_literal()
            case Kind.LBRACE:
                return self.dict_literal()
            case _:
                raise self.error(f"unexpected {_describe(token)}")

    def list_literal(self) -> Node:
        self.advance()
        items: list[Node] = []
        while not self.at(Kind.RBRACKET):
            items.append(self.expression())
            if self.at(Kind.COMMA):
                self.advance()
                continue
            break
        self.consume(Kind.RBRACKET, "expected ']' to close the list")
        return ListLit(tuple(items))

    def dict_literal(self) -> Node:
        self.advance()
        pairs: list[tuple[Node, Node]] = []
        while not self.at(Kind.RBRACE):
            key = self.expression()
            if isinstance(key, Var):
                key = Literal(key.name)
            self.consume(Kind.COLON, "expected ':' between a key and its value")
            pairs.append((key, self.expression()))
            if self.at(Kind.COMMA):
                self.advance()
                continue
            break
        self.consume(Kind.RBRACE, "expected '}' to close the object")
        return DictLit(tuple(pairs))

    # -- token handling ----------------------------------------------------------

    def current(self) -> Token:
        return self._tokens[self._index]

    def peek(self, ahead: int = 1) -> Token:
        index = min(self._index + ahead, len(self._tokens) - 1)
        return self._tokens[index]

    def advance(self) -> Token:
        token = self._tokens[self._index]
        if token.kind is not Kind.EOF:
            self._index += 1
        return token

    def at(self, kind: Kind) -> bool:
        return self.current().kind is kind

    def at_operator(self, text: str) -> bool:
        token = self.current()
        return token.kind is Kind.OP and token.text == text

    def at_keyword(self, word: str) -> bool:
        token = self.current()
        return token.kind is Kind.IDENT and token.text.lower() == word

    def peek_operator(self) -> str | None:
        token = self.current()
        if token.kind is Kind.OP and token.text in PRECEDENCE:
            return token.text
        if token.kind is Kind.IDENT and token.text.lower() == "in":
            return "in"
        return None

    def consume(self, kind: Kind, message: str) -> Token:
        if not self.at(kind):
            raise self.error(message)
        return self.advance()

    def expect_keyword(self, word: str, message: str) -> None:
        if not self.at_keyword(word):
            raise self.error(message)
        self.advance()

    def expect_end(self) -> None:
        if not self.at(Kind.EOF):
            raise self.error(f"unexpected {_describe(self.current())} after the expression")

    def error(self, message: str) -> ExpressionError:
        token = self.current()
        if token.kind is Kind.OP and token.text == "=":
            # The single most common typo in a condition. Say so directly.
            return ExpressionError(
                "'=' assigns, it does not compare",
                where=_mark(self._source, token.position),
                remedies=["use '==' to compare", "keyword arguments look like f(name=value)"],
            )
        return ExpressionError(message, where=_mark(self._source, token.position))

    def _previous_was_not(self) -> bool:
        if self._index == 0:
            return False
        previous = self._tokens[self._index - 1]
        return previous.kind is Kind.IDENT and previous.text.lower() == "not"


def _describe(token: Token) -> str:
    if token.kind is Kind.EOF:
        return "end of expression"
    return f"{token.text!r}"


def _mark(source: str, index: int) -> str:
    index = min(index, len(source))
    return f"{source}\n{' ' * index}^"
