"""Rendering: the event protocol, the reporter, and the sinks.

Hand-written terminal handling, no `rich` (SPEC decision 7). The engine emits events;
exactly one task in `reporter` writes them.
"""
