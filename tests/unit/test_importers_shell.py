"""I1: tokenizing a copied shell command without ever running a shell."""

from __future__ import annotations

from sclpl.importers import shell


def test_posix_single_quotes_and_line_continuations() -> None:
    command = (
        "curl 'https://api.example.com/x' \\\n"
        "  -H 'Authorization: Bearer abc123' \\\n"
        "  --data-raw '{\"a\":1}'"
    )
    assert shell.tokenize(command, dialect="posix") == [
        "curl",
        "https://api.example.com/x",
        "-H",
        "Authorization: Bearer abc123",
        "--data-raw",
        '{"a":1}',
    ]


def test_posix_double_quotes_with_embedded_spaces() -> None:
    command = 'curl "https://api.example.com/x" -H "X-Name: a value with spaces"'
    assert shell.tokenize(command, dialect="posix") == [
        "curl",
        "https://api.example.com/x",
        "-H",
        "X-Name: a value with spaces",
    ]


def test_windows_cmd_caret_continuation_and_backslash_quote() -> None:
    command = (
        'curl "https://api.example.com/x" ^\n'
        '  -H "Authorization: Bearer abc123" ^\n'
        '  --data-raw "{\\"a\\":1}"'
    )
    assert shell.tokenize(command, dialect="windows") == [
        "curl",
        "https://api.example.com/x",
        "-H",
        "Authorization: Bearer abc123",
        "--data-raw",
        '{"a":1}',
    ]


def test_windows_powershell_backtick_continuation_and_quote() -> None:
    command = (
        'curl.exe "https://api.example.com/x" `\n'
        '  -H "Authorization: Bearer abc123" `\n'
        '  --data-raw "{`"a`":1}"'
    )
    assert shell.tokenize(command, dialect="windows") == [
        "curl.exe",
        "https://api.example.com/x",
        "-H",
        "Authorization: Bearer abc123",
        "--data-raw",
        '{"a":1}',
    ]


def test_detect_dialect_from_continuation_style() -> None:
    assert shell.detect_dialect("curl x \\\n  -H y") == "posix"
    assert shell.detect_dialect("curl x ^\n  -H y") == "windows"
    assert shell.detect_dialect("curl x `\n  -H y") == "windows"
    assert shell.detect_dialect("curl https://x") == "posix"


def test_repeated_backslashes_before_a_quote_halve_and_toggle() -> None:
    # Windows argv convention: 2N backslashes + quote -> N literal backslashes,
    # quote toggles; 2N+1 backslashes + quote -> N backslashes + literal quote.
    assert shell._split_msvcrt('a\\\\"b c"') == ["a\\b c"]
    assert shell._split_msvcrt('a\\"b') == ['a"b']
