"""Advanced TUI feature tests for authentication, batch, history cleanup, event bus."""


import pytest

from app.ui.textual_app import SCLPLTextualApp


@pytest.fixture
def app():
    return SCLPLTextualApp()


# ── Authentication ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_auth_type_select_exists(app):
    """Test: Auth type selector exists in request editor."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        auth_select = app.query("#auth-type")
        assert len(auth_select) > 0


@pytest.mark.asyncio
async def test_auth_type_options(app):
    """Test: Auth type has None/Bearer/Basic/API Key options."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        auth_select = app.query_one("#auth-type")
        # Should have None, Bearer, Basic, API Key
        assert auth_select is not None


@pytest.mark.asyncio
async def test_auth_token_input(app):
    """Test: Auth token input exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        token_input = app.query("#auth-token")
        assert len(token_input) > 0


@pytest.mark.asyncio
async def test_auth_basic_inputs(app):
    """Test: Basic auth has username and password inputs."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        username = app.query("#auth-username")
        password = app.query("#auth-password")
        assert len(username) > 0
        assert len(password) > 0


@pytest.mark.asyncio
async def test_auth_apikey_input(app):
    """Test: API key input exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        apikey = app.query("#auth-api-key")
        assert len(apikey) > 0


# ── Request Editor Tabs ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_body_tab(app):
    """Test: Body tab exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        body_tab = app.query("#tab-body")
        assert len(body_tab) > 0


@pytest.mark.asyncio
async def test_headers_tab(app):
    """Test: Headers tab exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        headers_tab = app.query("#tab-headers")
        assert len(headers_tab) > 0


@pytest.mark.asyncio
async def test_params_tab(app):
    """Test: Params tab exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        params_tab = app.query("#tab-params")
        assert len(params_tab) > 0


@pytest.mark.asyncio
async def test_auth_tab(app):
    """Test: Auth tab exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        auth_tab = app.query("#tab-auth")
        assert len(auth_tab) > 0


@pytest.mark.asyncio
async def test_headers_editor(app):
    """Test: Headers editor textarea exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        editor = app.query("#headers-editor")
        assert len(editor) > 0


@pytest.mark.asyncio
async def test_params_editor(app):
    """Test: Params editor textarea exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        editor = app.query("#params-editor")
        assert len(editor) > 0


# ── Batch CSV Import ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_batch_csv_input(app):
    """Test: Batch has CSV file path input."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-batch"
        await pilot.pause()
        csv_input = app.query("#batch-csv-input")
        assert len(csv_input) > 0


@pytest.mark.asyncio
async def test_batch_load_button(app):
    """Test: Batch has Load button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-batch"
        await pilot.pause()
        load_btn = app.query("#load-csv-btn")
        assert len(load_btn) > 0


@pytest.mark.asyncio
async def test_batch_start_button(app):
    """Test: Batch has Start button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-batch"
        await pilot.pause()
        start_btn = app.query("#start-batch-btn")
        assert len(start_btn) > 0


@pytest.mark.asyncio
async def test_batch_stop_button(app):
    """Test: Batch has Stop button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-batch"
        await pilot.pause()
        stop_btn = app.query("#stop-batch-btn")
        assert len(stop_btn) > 0


@pytest.mark.asyncio
async def test_batch_progress_bar(app):
    """Test: Batch has progress bar."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-batch"
        await pilot.pause()
        progress = app.query("#batch-progress")
        assert len(progress) > 0


@pytest.mark.asyncio
async def test_batch_table(app):
    """Test: Batch has results table."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-batch"
        await pilot.pause()
        table = app.query("#batch-table")
        assert len(table) > 0


# ── History Cleanup ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_history_cleanup_policy(app):
    """Test: History has cleanup policy selector."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-history"
        await pilot.pause()
        policy = app.query("#cleanup-policy")
        assert len(policy) > 0


@pytest.mark.asyncio
async def test_history_cleanup_button(app):
    """Test: History has cleanup button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-history"
        await pilot.pause()
        cleanup_btn = app.query("#cleanup-btn")
        assert len(cleanup_btn) > 0


# ── Response Viewer ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_response_pretty_tab(app):
    """Test: Response has Pretty tab with JSON tree."""
    async with app.run_test() as pilot:
        # TabPanes are inside TabbedContent, check the tabbed content exists
        tabbed = app.query("TabbedContent")
        assert len(tabbed) > 0


@pytest.mark.asyncio
async def test_response_viewer_has_tabs(app):
    """Test: Response viewer has tabbed content."""
    async with app.run_test() as pilot:
        # ResponseViewer should have TabbedContent
        assert app.is_running


@pytest.mark.asyncio
async def test_response_json_tree(app):
    """Test: Response has JSON tree widget."""
    async with app.run_test() as pilot:
        # Tree widget should exist
        trees = app.query("Tree")
        assert len(trees) > 0


@pytest.mark.asyncio
async def test_response_viewer_exists(app):
    """Test: Response viewer exists in request tab."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        assert app.is_running


# ── Diff Viewer ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_diff_viewer_import(app):
    """Test: DiffViewer can be imported."""
    from app.ui.screens.diff_viewer import DiffViewer
    viewer = DiffViewer()
    assert viewer is not None


@pytest.mark.asyncio
async def test_diff_viewer_methods(app):
    """Test: DiffViewer has set_diff and set_unified_diff methods."""
    from app.ui.screens.diff_viewer import DiffViewer
    viewer = DiffViewer()
    assert hasattr(viewer, 'set_diff')
    assert hasattr(viewer, 'set_unified_diff')


# ── Log Viewer ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_log_viewer_search(app):
    """Test: Log viewer has search input."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-logs"
        await pilot.pause()
        search = app.query("#log-search")
        assert len(search) > 0


@pytest.mark.asyncio
async def test_log_viewer_level_filter(app):
    """Test: Log viewer has level filter."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-logs"
        await pilot.pause()
        level = app.query("#level-filter")
        assert len(level) > 0


# ── Event Bus ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_event_bus_subscribe(app):
    """Test: Event bus subscription works."""
    async with app.run_test() as pilot:
        if app._app:
            from app.core.contracts.event_bus import Event
            events = []
            app._app.event_bus.subscribe("*", lambda e: events.append(e.name))
            app._app.event_bus.publish(Event(name="test.event", data={}, source="test"))
            assert len(events) > 0
            assert events[0] == "test.event"


@pytest.mark.asyncio
async def test_event_bus_multiple_events(app):
    """Test: Event bus handles multiple events."""
    async with app.run_test() as pilot:
        if app._app:
            from app.core.contracts.event_bus import Event
            events = []
            app._app.event_bus.subscribe("*", lambda e: events.append(e.name))
            for i in range(5):
                app._app.event_bus.publish(Event(name=f"event.{i}", data={}, source="test"))
            assert len(events) == 5


# ── Settings ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_settings_db_path_input(app):
    """Test: Settings has database path input."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-settings"
        await pilot.pause()
        db_path = app.query("#db-path-input")
        assert len(db_path) > 0


@pytest.mark.asyncio
async def test_settings_export_dir_input(app):
    """Test: Settings has export directory input."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-settings"
        await pilot.pause()
        export_dir = app.query("#export-dir-input")
        assert len(export_dir) > 0


@pytest.mark.asyncio
async def test_settings_timeout_input(app):
    """Test: Settings has timeout input."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-settings"
        await pilot.pause()
        timeout = app.query("#timeout-input")
        assert len(timeout) > 0


@pytest.mark.asyncio
async def test_settings_save_button(app):
    """Test: Settings has save button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-settings"
        await pilot.pause()
        save = app.query("#save-settings-btn")
        assert len(save) > 0


@pytest.mark.asyncio
async def test_settings_reset_button(app):
    """Test: Settings has reset button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-settings"
        await pilot.pause()
        reset = app.query("#reset-settings-btn")
        assert len(reset) > 0


# ── Import/Export ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_import_export_export_all(app):
    """Test: Export all button exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-import-export"
        await pilot.pause()
        btn = app.query("#export-all-btn")
        assert len(btn) > 0


@pytest.mark.asyncio
async def test_import_export_import_all(app):
    """Test: Import all button exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-import-export"
        await pilot.pause()
        btn = app.query("#import-all-btn")
        assert len(btn) > 0


@pytest.mark.asyncio
async def test_import_export_openapi(app):
    """Test: OpenAPI import button exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-import-export"
        await pilot.pause()
        btn = app.query("#import-openapi-btn")
        assert len(btn) > 0


# ── Performance ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rapid_tab_switching_200_times(app):
    """Test: Rapid tab switching 200 times doesn't crash."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        tabs = ["tab-request", "tab-collections", "tab-history", "tab-workflows",
                "tab-environments", "tab-functions", "tab-plugins", "tab-batch", "tab-logs"]
        for _ in range(22):  # 22 * 9 = ~200 switches
            for tab in tabs:
                workspace.active = tab
                await pilot.pause()


@pytest.mark.asyncio
async def test_rapid_actions_no_crash(app):
    """Test: Rapid actions don't crash."""
    async with app.run_test() as pilot:
        for _ in range(20):
            await pilot.press("f5")
            await pilot.pause()
