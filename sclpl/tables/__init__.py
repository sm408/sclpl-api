"""Tabular data: the Table wrapper, the backend protocol, io, and flattening.

Importing this registers the Parquet reader with `values/ref.py`, which is how a
spilled table knows how to come back without `values/` importing `tables/`.
"""

from __future__ import annotations

from sclpl.tables.base import MissingExtra, Table, TableBackend, as_table, is_table
from sclpl.tables.flatten import flatten_record, flatten_records, infer_schema
from sclpl.tables.io import format_of, read, read_parquet_file, write
from sclpl.values.ref import register_reader

register_reader("parquet", read_parquet_file)

__all__ = [
    "MissingExtra",
    "Table",
    "TableBackend",
    "as_table",
    "flatten_record",
    "flatten_records",
    "format_of",
    "infer_schema",
    "is_table",
    "read",
    "read_parquet_file",
    "write",
]
