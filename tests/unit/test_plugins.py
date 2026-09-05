"""Plugin discovery, the manifest, capabilities, and the bundled set.

The bundled plugins are tested through the same path an external one takes -- discovery,
manifest, capability check, import -- because that is the whole argument for shipping
them. If `sqlite` needed something the public API does not offer, the API would be
missing something, and this is where that shows.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from sclpl import bootstrap
from sclpl.errors import ValidationError
from sclpl.expr import evaluate, parse
from sclpl.ext import plugins as ext

bootstrap.load()


def make_plugin(
    root: Path,
    name: str,
    *,
    api: str = "sclpl/1",
    capabilities: str = "[]",
    body: str = "",
    manifest: str | None = None,
) -> Path:
    """Write a plugin on disk, as a user would."""
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "plugin.toml").write_text(
        manifest
        if manifest is not None
        else (
            f'[plugin]\nname = "{name}"\nversion = "1.0"\n'
            f'api = "{api}"\nmodule = "{name}"\ncapabilities = {capabilities}\n'
        ),
        encoding="utf-8",
    )
    (directory / "__init__.py").write_text(
        body or "def register() -> None:\n    pass\n", encoding="utf-8"
    )
    return directory


# -- the bundled set ---------------------------------------------------------------


def test_the_bundled_plugins_load() -> None:
    """Through the same discovery path an external plugin takes."""
    registry = ext.discover()
    for name in ("sqlite", "fs", "text", "example"):
        assert registry.plugins[name].loaded, registry.plugins[name].refused


def test_the_bundled_plugins_declare_what_they_do() -> None:
    registry = ext.discover()
    assert registry.plugins["sqlite"].capabilities == {"fs:read", "fs:write"}
    assert registry.plugins["text"].capabilities == frozenset()
    assert registry.plugins["example"].capabilities == frozenset()


def test_static_discovery_does_not_import_a_local_plugin(tmp_path: Path) -> None:
    marker = tmp_path / "imported.txt"
    body = f"from pathlib import Path\nPath({str(marker)!r}).write_text('x')\n"
    make_plugin(tmp_path, "sentinel", body=body)
    registry = ext.discover(include_bundled=False, extra_dirs=[tmp_path], activate=False)
    assert "sentinel" in registry.plugins
    assert not marker.exists()


def test_a_manifest_declaring_a_connector_gets_it_registered() -> None:
    """A manifest naming something the code forgot is a bug worth being able to see."""
    from sclpl.ext.functions import REGISTRY

    registry = ext.discover()
    declared = {
        item.name for item in registry.plugins["sqlite"].contributes if item.kind == "connector"
    }
    assert declared <= set(REGISTRY)


# -- the manifest ------------------------------------------------------------------


def test_a_plugin_built_for_another_api_is_refused(tmp_path: Path) -> None:
    """Named versions at load, rather than an AttributeError at the first call."""
    make_plugin(tmp_path, "future", api="sclpl/99")
    registry = ext.discover(extra_dirs=[tmp_path])
    plugin = registry.plugins["future"]
    assert not plugin.loaded
    assert "sclpl/99" in plugin.refused
    assert "sclpl/1" in plugin.refused


def test_an_unknown_capability_is_refused_not_ignored(tmp_path: Path) -> None:
    """A typo in a manifest should not silently widen or narrow what is granted."""
    make_plugin(tmp_path, "typo", capabilities='["netwrok"]')
    plugin = ext.discover(extra_dirs=[tmp_path]).plugins["typo"]
    assert not plugin.loaded
    assert "netwrok" in plugin.refused


def test_a_malformed_manifest_is_reported_not_skipped(tmp_path: Path) -> None:
    """Skipping it silently leaves someone wondering why their plugin does not appear."""
    make_plugin(tmp_path, "broken", manifest="this is not toml [[[")
    plugin = ext.discover(extra_dirs=[tmp_path]).plugins["broken"]
    assert not plugin.loaded
    assert "not readable" in plugin.refused


def test_a_directory_without_a_manifest_is_not_a_plugin(tmp_path: Path) -> None:
    (tmp_path / "notaplugin").mkdir()
    assert "notaplugin" not in ext.discover(extra_dirs=[tmp_path]).plugins


def test_a_plugin_that_will_not_import_is_refused_not_fatal(tmp_path: Path) -> None:
    """One broken plugin should not stop a run that does not use it."""
    make_plugin(tmp_path, "explodes", body="raise RuntimeError('boom')\n")
    registry = ext.discover(extra_dirs=[tmp_path])
    assert not registry.plugins["explodes"].loaded
    assert "boom" in registry.plugins["explodes"].refused
    assert registry.plugins["sqlite"].loaded


def test_a_register_that_raises_is_refused_not_fatal(tmp_path: Path) -> None:
    make_plugin(
        tmp_path,
        "badregister",
        body="def register() -> None:\n    raise ValueError('nope')\n",
    )
    plugin = ext.discover(extra_dirs=[tmp_path]).plugins["badregister"]
    assert not plugin.loaded
    assert "nope" in plugin.refused


def test_two_plugins_claiming_one_name_is_reported(tmp_path: Path) -> None:
    """A coin toss would be worse than a message."""
    make_plugin(tmp_path, "sqlite")
    registry = ext.discover(extra_dirs=[tmp_path])
    assert any(name == "sqlite" for name, _first, _second in registry.shadowed)
    # The bundled one keeps the name; the later claim is what is reported.
    assert registry.plugins["sqlite"].source == "bundled"


# -- capabilities ------------------------------------------------------------------


def test_a_denied_capability_refuses_the_plugin(tmp_path: Path) -> None:
    make_plugin(tmp_path, "needsnet", capabilities='["network"]')
    ext.DENIED.clear()
    try:
        plugin = ext.discover(denied=["network"], extra_dirs=[tmp_path]).plugins["needsnet"]
        assert not plugin.loaded
        assert "network" in plugin.refused
        assert "denied" in plugin.refused
    finally:
        ext.DENIED.clear()
        ext.discover()


def test_a_denied_plugin_never_executes_its_import_sentinel(tmp_path: Path) -> None:
    marker = tmp_path / "imported.txt"
    body = f"from pathlib import Path\nPath({str(marker)!r}).write_text('x')\n"
    make_plugin(tmp_path, "needsnet", capabilities='["network"]', body=body)
    ext.DENIED.clear()
    try:
        plugin = ext.discover(denied=["network"], extra_dirs=[tmp_path]).plugins["needsnet"]
        assert not plugin.loaded
        assert not marker.exists()
    finally:
        ext.DENIED.clear()
        ext.discover()


def test_a_denial_survives_a_second_discovery(tmp_path: Path) -> None:
    """`plugin list` re-discovers, and must see the same refusals the run did."""
    ext.DENIED.clear()
    try:
        ext.discover(denied=["fs:write"])
        assert not ext.discover().plugins["sqlite"].loaded
    finally:
        ext.DENIED.clear()
        ext.discover()


@pytest.mark.parametrize("name", sorted(ext.CAPABILITIES))
def test_every_declared_capability_is_accepted(name: str) -> None:
    assert ext.parse_capabilities([name]) == {name}


def test_a_misspelled_denial_is_corrected() -> None:
    with pytest.raises(ValidationError) as caught:
        ext.parse_capabilities(["netwrok"])
    assert "network" in str(caught.value)


# -- the public API ------------------------------------------------------------------


def test_a_connector_needs_a_namespace() -> None:
    """The dot is what lets two plugins both offer `query`."""
    from sclpl.ext.api import connector

    with pytest.raises(ValidationError) as caught:
        connector("query")
    assert "no dot" in str(caught.value)


def test_the_api_exports_what_a_plugin_needs() -> None:
    """Anything here keeps working across a minor version. Anything else may not."""
    from sclpl.ext import api

    for name in ("function", "connector", "Table", "records_of", "ValidationError"):
        assert name in api.__all__
        assert hasattr(api, name)


def test_records_of_understands_a_table() -> None:
    """The bundled sqlite plugin found this: a plugin gets tables, and must handle them.

    Before, `records_of(table)` produced `[{"value": "<Table 3x3>"}]` -- the repr, in one
    column. The function catalogue worked around it privately, so only a plugin hit it.
    """
    from sclpl.ext.api import Table, records_of

    table = Table.from_records([{"id": 1}, {"id": 2}])
    assert records_of(table) == [{"id": 1}, {"id": 2}]


# -- the bundled sqlite plugin, doing its job ----------------------------------------


def run(source: str) -> Any:
    return asyncio.run(evaluate(parse(source)))


def test_sqlite_writes_reads_and_describes(tmp_path: Path) -> None:
    database = (tmp_path / "t.sqlite").as_posix()
    rows = "[{'id': 1, 'name': 'Ada'}, {'id': 2, 'name': 'Grace'}]"

    written = run(f"sqlite.write({rows}, '{database}', 'people')")
    assert written == {"written": 2, "table": "people", "columns": ["id", "name"]}

    assert run(f"sqlite.schema('{database}')") == {"people": {"id": "INTEGER", "name": "TEXT"}}
    assert run(f'sqlite.query("{database}", "select name from people order by id")') == [
        {"name": "Ada"},
        {"name": "Grace"},
    ]


def test_sqlite_binds_parameters_rather_than_formatting_them(tmp_path: Path) -> None:
    """Bound parameters keep their type, which is invariant 2 reaching into the database."""
    database = (tmp_path / "t.sqlite").as_posix()
    run(f"sqlite.write([{{'id': 1, 'score': 9.5}}], '{database}', 't')")
    assert run(f'sqlite.query("{database}", "select score from t where id = ?", 1)') == [
        {"score": 9.5}
    ]


def test_sqlite_takes_the_union_of_the_columns(tmp_path: Path) -> None:
    """An API omitting a null field on some rows must not drop it for everybody."""
    database = (tmp_path / "t.sqlite").as_posix()
    run(f"sqlite.write([{{'a': 1}}, {{'a': 2, 'b': 'x'}}], '{database}', 't')")
    assert set(run(f"sqlite.schema('{database}')")["t"]) == {"a", "b"}


def test_sqlite_widens_an_existing_table_rather_than_failing(tmp_path: Path) -> None:
    """The same reasoning as `assert_schema` allowing extra columns by default."""
    database = (tmp_path / "t.sqlite").as_posix()
    run(f"sqlite.write([{{'a': 1}}], '{database}', 't')")
    run(f"sqlite.write([{{'a': 2, 'later': 'x'}}], '{database}', 't', mode='append')")
    assert "later" in run(f"sqlite.schema('{database}')")["t"]


def test_sqlite_encodes_a_nested_value_as_json_not_as_a_repr(tmp_path: Path) -> None:
    """A dict rendered with `repr` is readable by nothing; JSON round trips."""
    database = (tmp_path / "t.sqlite").as_posix()
    run(f"sqlite.write([{{'id': 1, 'tags': ['a', 'b']}}], '{database}', 't')")
    stored = run(f'sqlite.query("{database}", "select tags from t")')[0]["tags"]
    assert stored == '["a", "b"]'


def test_sqlite_refuses_an_unknown_write_mode(tmp_path: Path) -> None:
    database = (tmp_path / "t.sqlite").as_posix()
    with pytest.raises(ValidationError) as caught:
        run(f"sqlite.write([{{'a': 1}}], '{database}', 't', mode='sideways')")
    assert "upsert" in str(caught.value)


def test_upsert_without_a_key_says_what_is_missing(tmp_path: Path) -> None:
    database = (tmp_path / "t.sqlite").as_posix()
    with pytest.raises(ValidationError) as caught:
        run(f"sqlite.write([{{'a': 1}}], '{database}', 't', mode='upsert')")
    assert "key=" in str(caught.value)


def test_querying_a_database_that_is_not_there_says_so(tmp_path: Path) -> None:
    with pytest.raises(ValidationError) as caught:
        run(f"sqlite.query('{(tmp_path / 'absent.sqlite').as_posix()}', 'select 1')")
    assert "does not exist" in str(caught.value)


def test_a_table_name_with_a_quote_in_it_is_escaped(tmp_path: Path) -> None:
    """The one place a name is interpolated into SQL, so the escaping is load-bearing."""
    database = (tmp_path / "t.sqlite").as_posix()
    run(f"""sqlite.write([{{'a': 1}}], '{database}', 'odd"name')""")
    with sqlite3.connect(database) as connection:
        names = {
            row[0]
            for row in connection.execute("select name from sqlite_master where type='table'")
        }
    assert 'odd"name' in names


# -- the bundled fs plugin -----------------------------------------------------------


def test_fs_glob_returns_records_not_strings(tmp_path: Path) -> None:
    """So the result goes straight into `sort_by` or a `foreach`."""
    for name in ("a.txt", "b.txt"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    found = run(f"fs.glob('{(tmp_path / '*.txt').as_posix()}')")
    assert [item["name"] for item in found] == ["a.txt", "b.txt"]
    assert found[0]["bytes"] == 1


def test_fs_glob_matching_nothing_is_not_an_error(tmp_path: Path) -> None:
    """ "No files today" is a normal answer; `assert_rowcount` disagrees if it should."""
    assert run(f"fs.glob('{(tmp_path / '*.none').as_posix()}')") == []


def test_fs_exists_never_raises(tmp_path: Path) -> None:
    assert run(f"fs.exists('{(tmp_path / 'nope').as_posix()}')") is False


def test_fs_remove_refuses_a_directory_unless_told(tmp_path: Path) -> None:
    """One character in a glob separates a file from a tree, and a tree is not recoverable."""
    target = tmp_path / "sub"
    target.mkdir()
    with pytest.raises(ValidationError) as caught:
        run(f"fs.remove('{target.as_posix()}')")
    assert "directory=true" in str(caught.value)
    assert run(f"fs.remove('{target.as_posix()}', directory=true)")["removed"] is True


def test_fs_copy_creates_the_destination_directory(tmp_path: Path) -> None:
    source = tmp_path / "a.txt"
    source.write_text("hello", encoding="utf-8")
    target = tmp_path / "deep" / "nested" / "b.txt"
    run(f"fs.copy('{source.as_posix()}', '{target.as_posix()}')")
    assert target.read_text(encoding="utf-8") == "hello"


# -- the bundled text plugin ---------------------------------------------------------


def test_text_slug_makes_a_filename_safe_value() -> None:
    assert run("text.slug('Quarterly Revenue Report!')") == "quarterly-revenue-report"


def test_text_template_renders_each_record() -> None:
    rendered = run("text.template('{id}: {name}', [{'id': 1, 'name': 'Ada'}])")
    assert rendered == ["1: Ada"]


def test_text_template_names_a_missing_field() -> None:
    with pytest.raises(ValidationError) as caught:
        run("text.template('{missing}', [{'id': 1}])")
    assert "available: id" in str(caught.value)


def test_text_extract_adds_a_field_to_records() -> None:
    rows = run("text.extract([{'raw': 'ticket-42'}], 'raw', 'ticket-(\\d+)', into='id')")
    assert rows == [{"raw": "ticket-42", "id": "42"}]


def test_text_split_and_join_round_trip() -> None:
    assert run("text.join(text.split('a, b, c'), sep='|')") == "a|b|c"


# -- the example plugin, which is the scaffold ---------------------------------------


def test_the_scaffold_template_actually_works() -> None:
    """A scaffold that needs three fixes teaches the wrong thing about how hard this is."""
    assert run("greet('world')") == "Hello, world."
    assert run("example.echo(7, times=3)") == [7, 7, 7]


def test_a_scaffolded_plugin_loads_and_runs(tmp_path: Path) -> None:
    """The other half of the exit criterion: something written today, working today."""
    from sclpl.cli.plugin_cmd import _MANIFEST, _MODULE

    directory = tmp_path / "brandnew"
    directory.mkdir()
    (directory / "plugin.toml").write_text(_MANIFEST.format(name="brandnew"), encoding="utf-8")
    (directory / "__init__.py").write_text(_MODULE.format(name="brandnew"), encoding="utf-8")

    plugin = ext.discover(extra_dirs=[tmp_path]).plugins["brandnew"]
    assert plugin.loaded, plugin.refused
    assert run("brandnew_hello('you')") == "Hello from brandnew, you."
    assert run("brandnew.echo('x', times=2)") == ["x", "x"]


# -- dotted calls in expressions -----------------------------------------------------


def test_a_dotted_name_followed_by_a_paren_is_a_connector_call() -> None:
    from sclpl.expr.ast import Call

    parsed = parse("sqlite.query('db', 'select 1')")
    assert isinstance(parsed.node, Call)
    assert parsed.node.name == "sqlite.query"


def test_a_ref_chain_is_not_a_call() -> None:
    """`@response.body(...)` would be calling a value, which is not a thing."""
    from sclpl.expr.ast import Call

    assert not isinstance(parse("@response.body").node, Call)
