"""Reconcile API orders against the accounting ledger.

Reads ``{"api": [...], "ledger": [...]}`` on stdin -- each side already
verified unique by id before this runs. Writes one row per id seen on either
side, so the report has lineage: where a row came from, and whether the two
sources agree.
"""

from __future__ import annotations

import json
import sys


def main() -> None:
    payload = json.load(sys.stdin)
    api = {row["id"]: row["total"] for row in payload["api"]}
    ledger = {row["id"]: row["total"] for row in payload["ledger"]}

    rows = []
    for order_id in sorted(set(api) | set(ledger)):
        api_total = api.get(order_id)
        ledger_total = ledger.get(order_id)
        if order_id not in api:
            origin = "ledger_only"
        elif order_id not in ledger:
            origin = "api_only"
        elif api_total != ledger_total:
            origin = "mismatch"
        else:
            origin = "matched"
        rows.append(
            {
                "id": order_id,
                "api_total": api_total,
                "ledger_total": ledger_total,
                "origin": origin,
            }
        )
    json.dump(rows, sys.stdout)


if __name__ == "__main__":
    main()
