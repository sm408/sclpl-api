"""SCLPLL v2 parser: tokens in, IR out.

The grammar stays small because unknown verbs are not a parse error. A verb the parser
does not recognise is looked up in the function and connector registries, which is what
lets a plugin contribute vocabulary without touching this file (SPEC section 7).

v2 is a clean break from v1 (decision 4). No converter, and nothing here reads a v1
file well enough to half-work on one -- a v1 file fails at its first directive with a
message saying so, which is better than importing it wrong.
"""

from __future__ import annotations

from typing import Any

from sclpl.errors import ValidationError, did_you_mean
from sclpl.run.ir import (
    FnConfig,
    ForeachConfig,
    GateConfig,
    HttpConfig,
    IfConfig,
    LetConfig,
    Limits,
    ModeSpec,
    Pagination,
    ParallelConfig,
    Port,
    Retry,
    Step,
    WhileConfig,
    WorkflowDoc,
)
from sclpl.run.sclpll.lex import Kind, Token, split_args, tokenize, unquote

METHODS = ("get", "post", "put", "patch", "delete", "head", "options")

#: Body verbs the parser handles itself. Anything else is resolved as a function.
REQUEST_VERBS = frozenset(
    {"header", "query", "body", "auth", "paginate", "timeout", "extract", "proxy", "verify"}
)
CONTROL_VERBS = frozenset(
    {"when", "assert", "retry", "lane", "tag", "cache", "keep", "skip_if", "retry_if"}
)

#: Directives legal at column 0.
DIRECTIVES = frozenset(
    {
        "workflow",
        "version",
        "description",
        "default_mode",
        "var",
        "input",
        "output",
        "mode",
        "rule",
        "limits",
        "step",
    }
)


def parse(source: str, *, origin: str = "<sclpll>") -> WorkflowDoc:
    """Parse SCLPLL v2 text into the IR."""
    return _Parser(tokenize(source, origin=origin), origin).workflow()


class _Parser:
    __slots__ = ("_tokens", "_index", "_origin")

    def __init__(self, tokens: list[Token], origin: str) -> None:
        self._tokens = tokens
        self._index = 0
        self._origin = origin

    # -- top level ---------------------------------------------------------------

    def workflow(self) -> WorkflowDoc:
        doc: dict[str, Any] = {
            "name": "",
            "vars": {},
            "rules": {},
            "inputs": [],
            "outputs": [],
            "modes": {},
            "steps": [],
        }
        limits: dict[str, Any] = {}
        seen_workflow = False

        while not self.at(Kind.EOF):
            token = self.current()
            if token.kind in (Kind.INDENT, Kind.DEDENT):
                self.advance()
                continue
            if token.kind is not Kind.DIRECTIVE:
                raise self.error(
                    f"expected a directive, found {token.head!r}",
                    token,
                    ["directives start with '@' at the left margin"],
                )
            self.advance()
            name = token.head

            match name:
                case "workflow":
                    seen_workflow = True
                    args = split_args(token.rest)
                    if not args:
                        raise self.error("@workflow needs a name", token)
                    doc["name"] = unquote(args[0])
                    if len(args) > 1:
                        doc["description"] = unquote(" ".join(args[1:]))
                case "version":
                    doc["version"] = int(token.rest.strip())
                case "default_mode":
                    doc["default_mode"] = unquote(token.rest.strip())
                case "description":
                    doc["description"] = unquote(token.rest)
                case "var":
                    key, value = self.binding(token, "@var")
                    doc["vars"][key] = value
                case "rule":
                    key, value = self.binding(token, "@rule")
                    doc["rules"][key] = str(value)
                case "input":
                    doc["inputs"].append(self.port(token))
                case "output":
                    doc["outputs"].append(self.port(token))
                case "limits":
                    limits.update(self.limits(token))
                case "mode":
                    mode_name, spec = self.mode(token)
                    doc["modes"][mode_name] = spec
                case "step":
                    doc["steps"].append(self.step(token))
                case _:
                    raise self.error(
                        f"unknown directive @{name}",
                        token,
                        _suggest(name, DIRECTIVES),
                    )

        if not seen_workflow:
            raise ValidationError(
                "no @workflow directive",
                where=self._origin,
                remedies=[
                    "the first line should be: @workflow my-name",
                    "SCLPLL v1 files are not readable by v2 -- rewrite the header",
                ],
            )
        if limits:
            doc["limits"] = Limits.model_validate(limits)
        return WorkflowDoc.model_validate(doc)

    # -- directives --------------------------------------------------------------

    def binding(self, token: Token, what: str) -> tuple[str, Any]:
        name, separator, value = token.rest.partition("=")
        if not separator:
            raise self.error(f"{what} needs 'name = value'", token)
        return name.strip(), _literal(value.strip())

    def port(self, token: Token) -> dict[str, Any]:
        """`@input orders:csv?` -- name, optional format, optional '?' for not-required."""
        args = split_args(token.rest)
        if not args:
            raise self.error("a port needs a name", token)
        spec = args[0]
        required = True
        if spec.endswith("?"):
            required = False
            spec = spec[:-1]
        name, _, fmt = spec.partition(":")
        port: dict[str, Any] = {"name": name, "required": required}
        if fmt:
            port["format"] = fmt
        for extra in args[1:]:
            key, separator, value = extra.partition("=")
            if separator:
                port[key] = unquote(value)
        Port.model_validate(port)
        return port

    def limits(self, token: Token) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for item in split_args(token.rest):
            key, separator, value = item.partition("=")
            if not separator:
                raise self.error(f"@limits takes key=value pairs, found {item!r}", token)
            out[key.strip()] = _literal(value.strip())
        return out

    def mode(self, token: Token) -> tuple[str, dict[str, Any]]:
        args = split_args(token.rest)
        if not args:
            raise self.error("@mode needs a name", token)
        name = args[0]
        spec: dict[str, Any] = {"include": [], "exclude": [], "vars": {}, "limit": {}, "stub": {}}
        rest = args[1:]
        if rest and rest[0][:1] in "'\"":
            # A quoted string right after the name is the description. Treating it as a
            # selector would silently select nothing and run the wrong subset.
            spec["description"] = unquote(rest.pop(0))
        for item in rest:
            self._mode_clause(spec, item, token)
        if self.at(Kind.INDENT):
            self.advance()
            while not self.at(Kind.DEDENT) and not self.at(Kind.EOF):
                line = self.expect(Kind.LINE, "expected a mode clause")
                self._mode_body_line(spec, line)
            if self.at(Kind.DEDENT):
                self.advance()
        ModeSpec.model_validate(spec)
        return name, spec

    def _mode_clause(self, spec: dict[str, Any], item: str, token: Token) -> None:
        if item == "all":
            spec["all"] = True
        elif item.startswith("-"):
            spec["exclude"].append(item[1:])
        elif item.startswith("+"):
            spec["include"].append(item[1:])
        elif "=" in item:
            key, _, value = item.partition("=")
            spec["vars"][key.strip()] = _literal(value.strip())
        else:
            spec["include"].append(item)

    def _mode_body_line(self, spec: dict[str, Any], line: Token) -> None:
        args = split_args(line.rest)
        match line.head:
            case "include":
                spec["include"].extend(args)
            case "exclude":
                spec["exclude"].extend(args)
            case "extends":
                spec["extends"] = args[0] if args else None
            case "describe":
                spec["description"] = unquote(line.rest)
            case "var" | "limit" | "stub":
                target = {"var": "vars", "limit": "limit", "stub": "stub"}[line.head]
                for item in args:
                    key, separator, value = item.partition("=")
                    if not separator:
                        raise self.error(f"{line.head} takes key=value", line)
                    spec[target][key.strip()] = _literal(value.strip())
            case _:
                raise self.error(
                    f"unknown mode clause {line.head!r}",
                    line,
                    _suggest(line.head, {"include", "exclude", "extends", "var", "limit", "stub"}),
                )

    # -- steps -------------------------------------------------------------------

    def step(self, token: Token) -> dict[str, Any]:
        """`@step name <- dep1 dep2 -> port` followed by an indented body."""
        header = token.rest
        writes: str | None = None
        if "->" in header:
            header, _, target = header.partition("->")
            names = split_args(target.strip())
            if len(names) != 1:
                raise self.error(
                    "`->` names exactly one output port",
                    token,
                    ["e.g. `@step write_report -> report`"],
                )
            writes = names[0]

        needs: list[str] = []
        if "<-" in header:
            header, _, dependencies = header.partition("<-")
            needs = split_args(dependencies.strip())
        args = split_args(header.strip())
        if not args:
            raise self.error("@step needs a name", token)
        step_id = args[0]

        body = self.block()
        if not body:
            raise self.error(
                f"step {step_id!r} has an empty body",
                token,
                ["indent at least one line under it, e.g. `get https://…`"],
            )
        return self.assemble(step_id, needs, body, token, writes)

    def block(self) -> list[Token]:
        """The indented lines beneath a directive, nested blocks included."""
        if not self.at(Kind.INDENT):
            return []
        self.advance()
        lines: list[Token] = []
        depth = 1
        while depth and not self.at(Kind.EOF):
            token = self.current()
            if token.kind is Kind.INDENT:
                depth += 1
            elif token.kind is Kind.DEDENT:
                depth -= 1
                if depth == 0:
                    self.advance()
                    break
            else:
                lines.append(token)
            self.advance()
        return lines

    def assemble(
        self,
        step_id: str,
        needs: list[str],
        body: list[Token],
        token: Token,
        writes: str | None = None,
    ) -> dict[str, Any]:
        """Turn a step's body lines into a `Step` dict.

        The first line decides the kind: an HTTP verb makes it a request, `let` makes it
        a binding, `foreach`/`when`/`while` make it control flow, and anything else is
        a function call. Later lines configure whatever the first line chose.
        """
        step: dict[str, Any] = {"id": step_id, "tags": [], "needs": needs}
        if writes is not None:
            step["writes"] = writes
        first = body[0]
        head = first.head.lower()

        if head in METHODS:
            step["kind"] = "http"
            config: dict[str, Any] = {"method": head.upper(), "url": unquote(first.rest)}
            self._http_body(config, body[1:], step)
            step["config"] = HttpConfig.model_validate(config).model_dump(exclude_defaults=True)
        elif head == "let":
            step["kind"] = "let"
            step["config"] = LetConfig(expr=_binding(first.rest)).model_dump(exclude_defaults=True)
            self._common_body(step, body[1:])
        elif head == "foreach":
            step["kind"] = "foreach"
            step["config"] = self._foreach(first, body[1:], step)
        elif head == "when":
            step["kind"] = "if"
            step["config"] = self._conditional(first, body[1:], step)
        elif head in ("while", "do_while"):
            step["kind"] = head
            step["config"] = self._loop(first, body[1:], step)
        elif head == "parallel":
            step["kind"] = "parallel"
            step["config"] = self._parallel(first, body[1:], step)
        elif head == "gate":
            step["kind"] = "gate"
            reason = unquote(first.rest.strip())
            step["config"] = GateConfig(reason=reason).model_dump(exclude_defaults=True)
            self._common_body(step, body[1:])
        else:
            step["kind"] = "fn"
            args = split_args(first.rest)
            config_fn: dict[str, Any] = {"name": first.head, "args": [], "kwargs": {}}
            for item in args:
                key, separator, value = item.partition("=")
                if separator and key.isidentifier():
                    config_fn["kwargs"][key] = _literal(value)
                else:
                    config_fn["args"].append(_literal(item))
            step["config"] = FnConfig.model_validate(config_fn).model_dump(exclude_defaults=True)
            self._common_body(step, body[1:])

        Step.model_validate(step)
        return step

    def _http_body(self, config: dict[str, Any], lines: list[Token], step: dict[str, Any]) -> None:
        for line in lines:
            verb = line.head.lower()
            if verb in CONTROL_VERBS:
                self._common_line(step, line)
                continue
            if verb not in REQUEST_VERBS:
                raise self.error(
                    f"{verb!r} is not something a request understands",
                    line,
                    _suggest(verb, REQUEST_VERBS | CONTROL_VERBS),
                )
            match verb:
                case "header":
                    name, _, value = line.rest.partition(":")
                    config.setdefault("headers", {})[name.strip()] = value.strip()
                case "query":
                    for item in split_args(line.rest):
                        key, _, value = item.partition("=")
                        config.setdefault("query", {})[key.strip()] = _literal(value.strip())
                case "body":
                    config["body"] = _literal(line.rest)
                case "auth":
                    config["auth"] = unquote(line.rest)
                case "timeout":
                    config["timeout"] = float(line.rest)
                case "extract":
                    config["extract"] = line.rest.strip()
                case "paginate":
                    config["paginate"] = self._paginate(line)
                case "proxy":
                    config["proxy"] = unquote(line.rest)
                case "verify":
                    config["verify"] = _literal(line.rest.strip())

    def _paginate(self, line: Token) -> dict[str, Any]:
        args = split_args(line.rest)
        spec: dict[str, Any] = {}
        if args and "=" not in args[0]:
            spec["strategy"] = args[0]
            args = args[1:]
        for item in args:
            key, separator, value = item.partition("=")
            if not separator:
                raise self.error(f"paginate takes key=value, found {item!r}", line)
            spec[key.strip()] = _literal(value.strip())
        Pagination.model_validate(spec)
        return spec

    def _foreach(self, first: Token, lines: list[Token], step: dict[str, Any]) -> dict[str, Any]:
        """`foreach row in @rows`, `foreach @rows as row`, or `foreach @rows`.

        Both namings are accepted because both are what people write. What is not
        accepted is a third shape: `foreach @rows row` would otherwise be read as the
        expression `@rows row`, bind `item`, and fail much later with `@row` unknown.
        """
        args = split_args(first.rest)
        if not args:
            raise self.error("foreach needs a collection", first)

        if len(args) >= 3 and args[1] == "in":
            variable, over = args[0], " ".join(args[2:])
        elif len(args) >= 3 and args[-2] == "as":
            variable, over = args[-1], " ".join(args[:-2])
        elif len(args) == 1:
            variable, over = "item", args[0]
        else:
            raise self.error(
                f"cannot tell what {first.rest.strip()!r} loops over",
                first,
                [
                    "foreach row in @rows",
                    "foreach @rows as row",
                    "foreach @rows          (binds `item`)",
                ],
            )
        if not variable.isidentifier():
            raise self.error(f"{variable!r} is not a usable name for the loop variable", first)
        body, rest = self._nested(lines, step)
        if not body:
            raise self.error(
                "a foreach needs a body",
                first,
                ["indent at least one `step` under it"],
            )
        config: dict[str, Any] = {"over": over, "var": variable, "body": body}

        # Clauses configuring the loop sit above its first `step`, which is also where
        # they read. `concurrency 4` and `concurrency=4` both work: one is a clause and
        # the other is a setting, and arguing about which this is helps nobody.
        for line in rest:
            _, separator, value = line.rest.partition("=")
            argument = (value if separator else line.rest).strip()
            match line.head:
                case "concurrency":
                    if not argument.isdigit():
                        remedies = ["e.g. `concurrency 4`"]
                        if "{{" in argument:
                            # Worth saying outright: the limit is read when the file is
                            # parsed, before any value exists to interpolate.
                            remedies.insert(
                                0,
                                "it has to be a literal -- the limit is read at parse "
                                "time, before there is anything to interpolate",
                            )
                        raise self.error(
                            f"concurrency needs a number, found {argument!r}",
                            line,
                            remedies,
                        )
                    config["concurrency"] = int(argument)
                case "collect":
                    if not argument:
                        raise self.error(
                            "collect needs an expression",
                            line,
                            ["e.g. `collect @one.body.id` keeps the ids, not the responses"],
                        )
                    config["collect"] = argument
                case _:
                    raise self.error(
                        f"a foreach takes no clause {line.head!r}",
                        line,
                        [
                            "known: concurrency, collect",
                            "a clause goes above the first `step`, not below it",
                        ],
                    )
        ForeachConfig.model_validate(config)
        return config

    def _conditional(
        self, first: Token, lines: list[Token], step: dict[str, Any]
    ) -> dict[str, Any]:
        body, rest = self._nested(lines, step, frozenset({"otherwise"}))
        if not body:
            raise self.error(
                "a when needs a body",
                first,
                ["indent at least one `step` under it", "`otherwise` holds the other branch"],
            )
        otherwise: list[dict[str, Any]] = []
        for index, line in enumerate(rest):
            if line.head == "otherwise":
                otherwise, _ = self._nested(rest[index + 1 :], step)
                break
        config: dict[str, Any] = {
            "condition": first.rest.strip(),
            "then": body,
            "otherwise": otherwise,
        }
        IfConfig.model_validate(config)
        return config

    def _parallel(self, first: Token, lines: list[Token], step: dict[str, Any]) -> dict[str, Any]:
        """`parallel` with an indented `branch` per independent path."""
        branches: list[list[dict[str, Any]]] = []
        rest = lines
        while rest:
            if rest[0].head != "branch":
                raise self.error(
                    f"a parallel holds branches, not {rest[0].head!r}",
                    rest[0],
                    ["indent each path under its own `branch` line"],
                )
            found, rest = self._nested(rest[1:], step, frozenset({"branch"}))
            if found:
                branches.append(found)
        if not branches:
            raise self.error("a parallel needs at least one branch", first)
        config: dict[str, Any] = {"branches": branches}
        ParallelConfig.model_validate(config)
        return config

    def _loop(self, first: Token, lines: list[Token], step: dict[str, Any]) -> dict[str, Any]:
        body, _ = self._nested(lines, step)
        if not body:
            raise self.error(
                f"a {first.head} needs a body",
                first,
                ["indent at least one `step` under it"],
            )
        config: dict[str, Any] = {"condition": first.rest.strip(), "body": body}
        WhileConfig.model_validate(config)
        return config

    def _nested(
        self,
        lines: list[Token],
        step: dict[str, Any],
        stop_at: frozenset[str] = frozenset(),
    ) -> tuple[list[dict[str, Any]], list[Token]]:
        """Split a control-flow body into nested steps and everything after it.

        A nested step is introduced by a `step` line inside the block; anything before
        the first one configures the control step itself.

        ``stop_at`` names the words that end the block -- `otherwise` for a `when`,
        `branch` for a `parallel`. Without it those words land inside the last nested
        step's body and are reported as an unknown clause on that step, which points at
        the wrong line and does not mention the structure that actually went wrong.
        """
        nested: list[dict[str, Any]] = []
        trailing: list[Token] = []
        current: list[Token] = []
        current_id: str | None = None

        def close(at: Token) -> None:
            if current_id is not None and current:
                nested.append(self.assemble(current_id, [], current, at))

        for index, line in enumerate(lines):
            if line.head in stop_at:
                close(line)
                current_id = None
                trailing.extend(lines[index:])
                break
            if line.head == "step":
                close(line)
                current_id = split_args(line.rest)[0] if line.rest else f"body{len(nested)}"
                current = []
            elif current_id is None:
                trailing.append(line)
            else:
                current.append(line)
        else:
            close(lines[-1] if lines else Token(kind=Kind.LINE))
        return nested, trailing

    def _common_body(self, step: dict[str, Any], lines: list[Token]) -> None:
        for line in lines:
            self._common_line(step, line)

    def _common_line(self, step: dict[str, Any], line: Token) -> None:
        verb = line.head.lower()
        match verb:
            case "tag":
                step["tags"].extend(split_args(line.rest))
            case "assert":
                step["assert"] = line.rest.strip()
            case "when" | "skip_if":
                step["skip_if"] = line.rest.strip()
            case "retry_if":
                step["retry_if"] = line.rest.strip()
            case "lane":
                step["lane"] = line.rest.strip()
            case "keep":
                step["keep"] = True
            case "retry":
                args = split_args(line.rest)
                spec: dict[str, Any] = {}
                if args and "=" not in args[0]:
                    spec["max"] = int(args[0])
                    args = args[1:]
                for item in args:
                    key, separator, value = item.partition("=")
                    if separator:
                        spec[key.strip()] = _literal(value.strip())
                step["retry"] = Retry.model_validate(spec).model_dump(exclude_defaults=True)
            case "cache":
                args = split_args(line.rest)
                if args and args[0] in ("off", "no", "false"):
                    step["cache"] = {"enabled": False}
                else:
                    spec_cache: dict[str, Any] = {}
                    for item in args:
                        key, separator, value = item.partition("=")
                        if separator:
                            spec_cache[key.strip()] = _literal(value.strip())
                    step["cache"] = spec_cache
            case _:
                raise self.error(
                    f"unknown clause {line.head!r}",
                    line,
                    _suggest(line.head, CONTROL_VERBS),
                )

    # -- token handling ----------------------------------------------------------

    def current(self) -> Token:
        return self._tokens[self._index]

    def advance(self) -> Token:
        token = self._tokens[self._index]
        if token.kind is not Kind.EOF:
            self._index += 1
        return token

    def at(self, kind: Kind) -> bool:
        return self.current().kind is kind

    def expect(self, kind: Kind, message: str) -> Token:
        if not self.at(kind):
            raise self.error(message, self.current())
        return self.advance()

    def error(
        self, message: str, token: Token, remedies: list[str] | None = None
    ) -> ValidationError:
        return ValidationError(
            message,
            where=f"{self._origin}:{token.line}",
            remedies=(remedies or []) + ([f"  {token.raw.strip()}"] if token.raw else []),
        )


def _binding(rest: str) -> str:
    """The expression from a `let` line, whether or not it names the value first.

    `let total = sum(@rows)` and `let sum(@rows)` both mean the same thing -- the step
    id is the name either way. Splitting on the first `=` would take `by=` out of
    `sum(@rows, by="total")` and `==` out of a comparison, so the `=` only separates a
    name when what precedes it is a bare identifier and the `=` stands alone.
    """
    rest = rest.strip()
    index = rest.find("=")
    while index != -1:
        pair = rest[index : index + 2]
        if pair != "==" and (index == 0 or rest[index - 1] not in "!<>="):
            break
        index = rest.find("=", index + 2 if pair == "==" else index + 1)
    if index == -1:
        return rest
    name = rest[:index].strip()
    if not name.isidentifier():
        return rest
    return rest[index + 1 :].strip() or rest


def _literal(text: str) -> Any:
    """Read a bare token as the value it obviously is.

    Numbers, booleans, and null are recognised; anything else stays a string, including
    a `{{...}}` interpolation, which the expression layer resolves later.
    """
    text = text.strip()
    if not text:
        return ""
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in ("null", "none"):
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    if (text.startswith("[") and text.endswith("]")) or (
        text.startswith("{") and text.endswith("}")
    ):
        import json

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Not JSON after all -- most often a `{{...}}` interpolation, which the
            # expression layer resolves later. Leaving it a string is what lets it.
            pass
    return text


def _suggest(name: str, candidates: set[str] | frozenset[str]) -> list[str]:
    suggestion = did_you_mean(name, sorted(candidates))
    remedies = [suggestion] if suggestion else []
    remedies.append(f"known: {', '.join(sorted(candidates))}")
    return remedies
