"""Turn an existing request description into a workflow -- as data, never by
executing anything the description names. `curl` (I1) is the first source;
OpenAPI (I2) and Postman (I3) share the same "parse to data, then render a
workflow" shape.
"""

from __future__ import annotations
