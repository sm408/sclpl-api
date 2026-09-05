"""`sclpl call --header` and the reporter it should register credential-shaped values with.

`call` is a debugging tool -- showing the request is the whole point -- so headers are
never masked wholesale. But a bearer token or cookie passed on the command line should
not then turn up in a retry log or an error an unreliable server chose to echo back.
"""

from __future__ import annotations

import io

from sclpl.cli.run import _register_sensitive_headers
from sclpl.render.plain import PlainSink
from sclpl.render.reporter import Reporter


def make_reporter() -> Reporter:
    return Reporter([PlainSink(io.StringIO(), verbosity=-2)])


def test_an_authorization_header_is_registered_for_redaction() -> None:
    reporter = make_reporter()
    _register_sensitive_headers({"Authorization": "Bearer sk-live-distinctive"}, reporter)
    assert "sk-live-distinctive" not in reporter.scrub("saw Bearer sk-live-distinctive")


def test_header_name_matching_is_case_insensitive() -> None:
    reporter = make_reporter()
    _register_sensitive_headers({"authorization": "sk-live-distinctive"}, reporter)
    assert "sk-live-distinctive" not in reporter.scrub("sk-live-distinctive")


def test_an_ordinary_header_is_left_alone() -> None:
    """`Content-Type` is not a credential; nothing here should touch it."""
    reporter = make_reporter()
    _register_sensitive_headers({"Content-Type": "application/json"}, reporter)
    assert reporter.scrub("application/json still readable") == "application/json still readable"


def test_a_short_sensitive_value_does_not_raise() -> None:
    """Too short to redact safely (see redact.MIN_LENGTH) is not a reason to crash `call`."""
    reporter = make_reporter()
    _register_sensitive_headers({"X-Api-Key": "abc"}, reporter)  # must not raise
