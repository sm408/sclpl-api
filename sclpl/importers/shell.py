"""Tokenize a copy-pasted shell command into argv, without a shell.

A browser's "Copy as cURL" offers three dialects, and each quotes differently.
Interpreting the string ourselves -- never handing it to `bash`/`cmd`/`powershell`
-- is the whole safety property I1 asks for: a command that would delete files if
actually run is just text here.
"""

from __future__ import annotations

import shlex


def detect_dialect(command: str) -> str:
    """`"posix"` or `"windows"`, guessed from the line-continuation style used."""
    for line in command.splitlines():
        stripped = line.rstrip()
        if stripped.endswith("^"):
            return "windows"
        if stripped.endswith("`"):
            return "windows"
        if stripped.endswith("\\"):
            return "posix"
    return "posix"


def tokenize(command: str, *, dialect: str) -> list[str]:
    if dialect == "posix":
        return _tokenize_posix(command)
    if dialect == "windows":
        return _tokenize_windows(command)
    raise ValueError(f"unknown shell dialect {dialect!r}")


def _tokenize_posix(command: str) -> list[str]:
    joined = _join_continuations(command, continuation="\\")
    return shlex.split(joined, posix=True)


def _join_continuations(command: str, *, continuation: str) -> str:
    lines = command.splitlines()
    joined: list[str] = []
    for line in lines:
        stripped = line.rstrip()
        if stripped.endswith(continuation):
            joined.append(stripped[: -len(continuation)])
        else:
            joined.append(line)
            joined.append("\n")
    return "".join(joined)


def _tokenize_windows(command: str) -> list[str]:
    """PowerShell (backtick continuation, `` `" `` for an embedded quote) and cmd
    (`^` continuation, `\\"` for an embedded quote) both ultimately hand curl.exe
    an argv parsed by the standard Windows C-runtime convention. Normalizing the
    two escape spellings to one, then applying that one convention, covers both.
    """
    without_powershell_continuation = _join_continuations(command, continuation="`")
    joined = _join_continuations(without_powershell_continuation, continuation="^")
    normalized = joined.replace('`"', '\\"')
    return _split_msvcrt(normalized)


def _split_msvcrt(command: str) -> list[str]:
    """The Windows C-runtime argv convention: run's of `\\` before a `"` collapse
    to half as many literal backslashes, plus one literal `"` if the count was
    odd (which also means the quote does not toggle quoting); any other `"`
    toggles whether whitespace is a token separator.
    """
    tokens: list[str] = []
    current: list[str] = []
    in_quotes = False
    seen_token = False
    index = 0
    length = len(command)
    while index < length:
        char = command[index]
        if char == "\\":
            run = 0
            while index < length and command[index] == "\\":
                run += 1
                index += 1
            if index < length and command[index] == '"':
                current.append("\\" * (run // 2))
                if run % 2 == 1:
                    current.append('"')
                    index += 1
                else:
                    in_quotes = not in_quotes
                    index += 1
                seen_token = True
            else:
                current.append("\\" * run)
                seen_token = True
            continue
        if char == '"':
            in_quotes = not in_quotes
            seen_token = True
            index += 1
            continue
        if char.isspace() and not in_quotes:
            if seen_token:
                tokens.append("".join(current))
                current = []
                seen_token = False
            index += 1
            continue
        current.append(char)
        seen_token = True
        index += 1
    if seen_token:
        tokens.append("".join(current))
    return tokens
