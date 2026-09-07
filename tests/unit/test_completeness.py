"""F5: a run's overall data completeness, aggregated from what each paginated
step's own extraction actually covered (D7), plus cancellation.
"""

from __future__ import annotations

import io

from sclpl.render.plain import PlainSink
from sclpl.render.reporter import Reporter
from sclpl.run.execute import Runtime
from sclpl.run.ir import WorkflowDoc
from sclpl.run.runner import _completeness_of
from sclpl.run.schedule import Outcome
from sclpl.run.transport import Pool
from sclpl.values.store import ValueStore


def _runtime(*statuses: str) -> Runtime:
    runtime = Runtime(
        doc=WorkflowDoc(name="orders"),
        store=ValueStore(),
        reporter=Reporter([PlainSink(io.StringIO(), verbosity=-2)]),
        pool=Pool(),
    )
    runtime.completeness.extend(statuses)
    return runtime


def test_no_paginated_steps_is_complete() -> None:
    assert _completeness_of(_runtime(), Outcome(status="ok")) == "complete"


def test_every_paginated_step_reaching_its_declared_bound_is_complete() -> None:
    assert _completeness_of(_runtime("complete", "complete"), Outcome(status="ok")) == "complete"


def test_one_partial_step_makes_the_whole_run_partial() -> None:
    assert _completeness_of(_runtime("complete", "partial"), Outcome(status="ok")) == "partial"


def test_one_unknown_step_makes_the_whole_run_unknown() -> None:
    assert _completeness_of(_runtime("complete", "unknown"), Outcome(status="ok")) == "unknown"


def test_unknown_outranks_partial() -> None:
    assert _completeness_of(_runtime("partial", "unknown"), Outcome(status="ok")) == "unknown"


def test_a_cancelled_run_is_unknown_even_with_no_paginated_step_at_all() -> None:
    assert _completeness_of(_runtime(), Outcome(status="cancelled")) == "unknown"


def test_a_cancelled_run_stays_unknown_even_if_a_step_reported_complete() -> None:
    assert _completeness_of(_runtime("complete"), Outcome(status="cancelled")) == "unknown"
