"""Migration m006: Add document-model fields to workflow tables.

Extends the ``workflows`` table with ``layout`` (JSON graph positions)
and ``sclpll_source`` (raw SCLPLL text) columns so that the canonical
WorkflowDocument model can be fully persisted.

Extends the ``workflow_versions`` table with ``metadata`` (JSON) and
``author`` columns for richer version tracking.
"""

from __future__ import annotations

from app.storage.migrations.base import Migration


class AddWorkflowDocumentFields(Migration):
    @property
    def version(self) -> int:
        return 6

    @property
    def description(self) -> str:
        return "Add layout, sclpll_source to workflows; metadata, author to workflow_versions"

    async def up(self, db) -> None:
        # Workflows: add layout and sclpll_source columns
        await db.execute(
            "ALTER TABLE workflows ADD COLUMN layout TEXT DEFAULT '{}'"
        )
        await db.execute(
            "ALTER TABLE workflows ADD COLUMN sclpll_source TEXT DEFAULT ''"
        )

        # Workflow versions: add metadata and author columns
        await db.execute(
            "ALTER TABLE workflow_versions ADD COLUMN metadata TEXT DEFAULT '{}'"
        )
        await db.execute(
            "ALTER TABLE workflow_versions ADD COLUMN author TEXT DEFAULT ''"
        )

    async def down(self, db) -> None:
        # SQLite does not support DROP COLUMN in older versions.
        # These are additive columns so we leave them in place on rollback.
        pass
