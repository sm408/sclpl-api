# `expr/`

Budget 1,500. The expression language.

| File | Job |
|---|---|
| `lex.py` | Tokens |
| `parse.py` | Parser → AST; `parse_interpolated` for `{{ }}` |
| `ast.py` | The node types, and `unparse` — AST back to source |
| `eval.py` | The evaluator, `Context`, `stringify` |
| `path.py` | Path resolution, projections, nearest-key suggestions |
| `dispatch.py` | The `(name, type)` table with MRO walk-up |
| `refs.py` | **The** reference scanner |
| `ops/` | The operator catalogue → [[expr-ops]] |

→ [[Expressions]]

## `refs.py` is the one that must stay singular

`refs_in(text)` decides what counts as a reference, for all three shapes an expression
can arrive in: a whole expression, an interpolation, and a bare `@ref`.

A second scanner anywhere else means
[[Invariants#3 The DAG is inferred from references]] holds only for the shapes that
scanner knows about — which is exactly the bug it was created to fix.

## `unparse` lives in `ast.py`

Because it is a property of the node types, not a separate pass. It is what lets
`explain` and a diagnostic show the expression the user wrote rather than a repr.
