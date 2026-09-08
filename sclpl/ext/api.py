"""The public plugin API: everything a plugin may use, and nothing else.

A plugin imports from here. Not from `sclpl.run`, not from `sclpl.values` -- from here.
That is not a technical restriction, because Python has none to offer; it is a promise in
one direction. **Anything in this module keeps working across a minor version. Anything
outside it may be rearranged without warning.**

The bundled plugins use only this module, which is how the promise stays honest. If
`sqlite` needed something that is not here, the API would be missing something, and we
would find out before anyone else did.

What a plugin can contribute:

| | Register with | Called as |
|---|---|---|
| a **function** | `@function` | `my_thing(@rows)` in a workflow |
| a **connector** | `@connector` | `postgres.query "select 1"` |
| an **operator overload** | `@overload` | an existing name, for a new type |
| a **table backend** | `set_backend` | invisibly, under every `Table` |
| a **rehydrator** | `register_reader` | invisibly, when a spilled value comes back |

`register()` in the plugin's module is called once at load, and is where those go.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from sclpl.errors import (
    AssertionFailed,
    SclplError,
    StepFailed,
    TypeDispatchError,
    ValidationError,
    did_you_mean,
)
from sclpl.expr.dispatch import generic, overload
from sclpl.ext.functions import function
from sclpl.ext.resources import (
    ResourceAuthenticationError,
    ResourceCapabilities,
    ResourceConflict,
    ResourceInfo,
    ResourceInvalidURI,
    ResourceNotFound,
    ResourcePermissionDenied,
    ResourceProvider,
    ResourceRef,
    ResourceUnavailable,
    ResourceUnsupportedOperation,
    register_resource_provider,
)
from sclpl.tables.base import (
    MissingExtra,
    Table,
    TableBackend,
    as_table,
    is_table,
    set_backend,
)
from sclpl.tables.flatten import flatten_records, infer_schema, records_of
from sclpl.values.ref import register_reader

F = TypeVar("F", bound=Callable[..., Any])

#: What this build implements. A plugin may check it, but does not have to: the loader
#: has already refused anything incompatible before `register()` is reached.
API_VERSION = 1


def connector(name: str, *, lane: str | None = None, version: int = 1) -> Callable[[F], F]:
    """Register a namespaced callable: `sqlite.query`, `postgres.exec`.

    A connector is a function whose name has a dot in it. The dot is the whole
    difference -- it namespaces a plugin's contributions so two plugins can both offer
    `query` without either having to be renamed.

    Everything else about it is a function: the signature generates the schema, the help,
    the completion values, and the argument coercion.
    """
    if "." not in name:
        raise ValidationError(
            f"a connector name needs a namespace: {name!r} has no dot",
            remedies=[f"try '<plugin>.{name}'", "a bare name is a function, not a connector"],
        )
    return function(name, version=version, lane=lane)


__all__ = [
    "API_VERSION",
    "ResourceCapabilities",
    "ResourceAuthenticationError",
    "ResourceConflict",
    "ResourceInfo",
    "ResourceInvalidURI",
    "ResourceNotFound",
    "ResourcePermissionDenied",
    "ResourceProvider",
    "ResourceRef",
    "ResourceUnavailable",
    "ResourceUnsupportedOperation",
    "AssertionFailed",
    "MissingExtra",
    "SclplError",
    "StepFailed",
    "Table",
    "TableBackend",
    "TypeDispatchError",
    "ValidationError",
    "as_table",
    "connector",
    "did_you_mean",
    "flatten_records",
    "function",
    "generic",
    "infer_schema",
    "is_table",
    "overload",
    "records_of",
    "register_reader",
    "register_resource_provider",
    "set_backend",
]
