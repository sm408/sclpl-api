"""Reproducible SCLPL project packages: build, validate, install, and lifecycle.

A package bundles a project's declared workflows, tests, local plugins, and scripts
into one versioned, content-addressed archive. Nothing here executes project code;
building and installing are both metadata-and-file operations.
"""

from __future__ import annotations
