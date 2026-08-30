# `plugins_bundled/`

Budget 600. **Empty — M8.** #todo

Planned: `sqlite`, `fs`, `example`.

SQLite ships as a bundled *plugin* rather than as core
([[Locked Decisions#8 SQLite ships as a bundled *plugin*, not core]]) — which is how we
know the plugin API is sufficient. If the bundled plugin needs something the API does not
offer, the API is wrong, and we find out before anyone else does.

`tables/io.py` already points at it: reading or writing `.sqlite` raises a
`ValidationError` naming the connector, rather than failing obscurely.
