"""The built-in function catalogue.

Importing this registers every built-in. The imports look unused and are not: the
`@function` decorators run on import, which is the registration.
"""

from __future__ import annotations

from sclpl.functions import diagnostics, io_fns, shape_fns

__all__ = ["diagnostics", "io_fns", "shape_fns"]
