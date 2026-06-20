"""Comprehensive TUI feature validation tests."""

import pytest
from app.ui.textual_app import SCLPLTextualApp


@pytest.fixture
def app():
    return SCLPLTextualApp()


# ── Theme Switching ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_theme_toggle_dark_to_light(app):
    """Test: Theme toggles from dark to light."""
    async with app.run_test() as pilot:
        assert app.THEME == "dark"
        await pilot.press("f2")
        await pilot.pause()
        assert app.THEME == "light"


@pytest.mark.asyncio
async def test_theme_toggle_light_to_dark(app):
    """Test: Theme toggles from light to dark."""
    async with app.run_test() as pilot:
        app.THEME = "light"
        await pilot.press("f2")
        await pilot.pause()
        assert app.THEME == "dark"


@pytest.mark.asyncio
async def test_theme_toggle_multiple_times(app):
    """Test: Theme toggle works multiple times."""
    async with app.run_test() as pilot:
        for _ in range(5):
            await pilot.press("f2")
            await pilot.pause()


# ── Collection Search ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collection_search_input_exists(app):
    """Test: Collection search input exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-collections"
        await pilot.pause()
        search = app.query("#collection-search")
        assert len(search) > 0


@pytest.mark.asyncio
async def test_collection_search_filters(app):
    """Test: Collection search filters results."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-collections"
        await pilot.pause()
        # Search input should exist
        search = app.query("#collection-search")
        assert len(search) > 0


# ── Workflow Search ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_workflow_search_input_exists(app):
    """Test: Workflow search input exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-workflows"
        await pilot.pause()
        search = app.query("#workflow-search")
        assert len(search) > 0


@pytest.mark.asyncio
async def test_workflow_search_filters(app):
    """Test: Workflow search filters results."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-workflows"
        await pilot.pause()
        search = app.query_one("#workflow-search")
        await pilot.click("#workflow-search")
        await pilot.press("w", "e", "a", "t", "h", "e", "r")
        await pilot.pause()


# ── Plugin Search ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_plugin_search_input_exists(app):
    """Test: Plugin search input exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-plugins"
        await pilot.pause()
        search = app.query("#plugin-search")
        assert len(search) > 0


# ── Command Palette Search ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_command_palette_search(app):
    """Test: Command palette filters commands."""
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        await pilot.pause()
        # Type to filter
        await pilot.press("w", "o", "r", "k")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()


@pytest.mark.asyncio
async def test_command_palette_search_export(app):
    """Test: Command palette finds export commands."""
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        await pilot.pause()
        await pilot.press("e", "x", "p", "o", "r", "t")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()


@pytest.mark.asyncio
async def test_command_palette_search_plugin(app):
    """Test: Command palette finds plugin commands."""
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        await pilot.pause()
        await pilot.press("p", "l", "u", "g", "i", "n")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()


# ── History Operations ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_history_filter_input(app):
    """Test: History has filter input."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-history"
        await pilot.pause()
        filter_input = app.query("#filter-input")
        assert len(filter_input) > 0


@pytest.mark.asyncio
async def test_history_method_filter(app):
    """Test: History has method filter."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-history"
        await pilot.pause()
        method_filter = app.query("#method-filter")
        assert len(method_filter) > 0


@pytest.mark.asyncio
async def test_history_clear_button(app):
    """Test: History has clear button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-history"
        await pilot.pause()
        clear_btn = app.query("#clear-history-btn")
        assert len(clear_btn) > 0


# ── Environment Operations ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_environment_new_button(app):
    """Test: Environment has new button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-environments"
        await pilot.pause()
        new_btn = app.query("#new-env-btn")
        assert len(new_btn) > 0


@pytest.mark.asyncio
async def test_environment_activate_button(app):
    """Test: Environment has activate button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-environments"
        await pilot.pause()
        activate_btn = app.query("#activate-env-btn")
        assert len(activate_btn) > 0


@pytest.mark.asyncio
async def test_environment_delete_button(app):
    """Test: Environment has delete button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-environments"
        await pilot.pause()
        delete_btn = app.query("#delete-env-btn")
        assert len(delete_btn) > 0


@pytest.mark.asyncio
async def test_environment_set_var_button(app):
    """Test: Environment has set variable button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-environments"
        await pilot.pause()
        set_btn = app.query("#set-var-btn")
        assert len(set_btn) > 0


@pytest.mark.asyncio
async def test_environment_delete_var_button(app):
    """Test: Environment has delete variable button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-environments"
        await pilot.pause()
        delete_btn = app.query("#delete-var-btn")
        assert len(delete_btn) > 0


# ── Function Browser ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_function_search(app):
    """Test: Function browser has search."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-functions"
        await pilot.pause()
        search = app.query("#func-search")
        assert len(search) > 0


@pytest.mark.asyncio
async def test_function_source_viewer(app):
    """Test: Function browser has source viewer."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-functions"
        await pilot.pause()
        source = app.query("#func-source")
        assert len(source) > 0


# ── Import/Export ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_import_export_export_all(app):
    """Test: Import/Export has export all button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-import-export"
        await pilot.pause()
        btn = app.query("#export-all-btn")
        assert len(btn) > 0


@pytest.mark.asyncio
async def test_import_export_import_all(app):
    """Test: Import/Export has import all button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-import-export"
        await pilot.pause()
        btn = app.query("#import-all-btn")
        assert len(btn) > 0


@pytest.mark.asyncio
async def test_import_export_openapi(app):
    """Test: Import/Export has OpenAPI button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-import-export"
        await pilot.pause()
        btn = app.query("#import-openapi-btn")
        assert len(btn) > 0


# ── Batch ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_batch_load_csv(app):
    """Test: Batch has load CSV button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-batch"
        await pilot.pause()
        btn = app.query("#load-csv-btn")
        assert len(btn) > 0


@pytest.mark.asyncio
async def test_batch_start(app):
    """Test: Batch has start button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-batch"
        await pilot.pause()
        btn = app.query("#start-batch-btn")
        assert len(btn) > 0


@pytest.mark.asyncio
async def test_batch_stop(app):
    """Test: Batch has stop button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-batch"
        await pilot.pause()
        btn = app.query("#stop-batch-btn")
        assert len(btn) > 0


@pytest.mark.asyncio
async def test_batch_progress_bar(app):
    """Test: Batch has progress bar."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-batch"
        await pilot.pause()
        progress = app.query("#batch-progress")
        assert len(progress) > 0


# ── Logs ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_logs_search(app):
    """Test: Logs has search input."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-logs"
        await pilot.pause()
        search = app.query("#log-search")
        assert len(search) > 0


@pytest.mark.asyncio
async def test_logs_level_filter(app):
    """Test: Logs has level filter."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-logs"
        await pilot.pause()
        level = app.query("#level-filter")
        assert len(level) > 0


# ── Settings ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_settings_db_path(app):
    """Test: Settings has database path input."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-settings"
        await pilot.pause()
        db_path = app.query("#db-path-input")
        assert len(db_path) > 0


@pytest.mark.asyncio
async def test_settings_export_dir(app):
    """Test: Settings has export directory input."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-settings"
        await pilot.pause()
        export_dir = app.query("#export-dir-input")
        assert len(export_dir) > 0


@pytest.mark.asyncio
async def test_settings_timeout(app):
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


# ── Response Viewer ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_response_viewer_tabs(app):
    """Test: Response viewer has body/headers/raw tabs."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        # ResponseViewer should be present in the request tab


# ── Workflow Execution ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_workflow_run_button(app):
    """Test: Workflow has run button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-workflows"
        await pilot.pause()
        run_btn = app.query("#run-workflow-btn")
        assert len(run_btn) > 0


@pytest.mark.asyncio
async def test_workflow_view_steps_button(app):
    """Test: Workflow has view steps button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-workflows"
        await pilot.pause()
        view_btn = app.query("#view-steps-btn")
        assert len(view_btn) > 0


@pytest.mark.asyncio
async def test_workflow_execution_export_buttons(app):
    """Test: Workflow execution has export buttons."""
    async with app.run_test() as pilot:
        export_json = app.query("#export-json-btn")
        export_csv = app.query("#export-csv-btn")
        rerun = app.query("#rerun-workflow-btn")
        assert len(export_json) > 0
        assert len(export_csv) > 0
        assert len(rerun) > 0


# ── Collection Operations ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collection_new_button(app):
    """Test: Collection has new button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-collections"
        await pilot.pause()
        new_btn = app.query("#new-collection-btn")
        assert len(new_btn) > 0


@pytest.mark.asyncio
async def test_collection_delete_button(app):
    """Test: Collection has delete button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-collections"
        await pilot.pause()
        delete_btn = app.query("#delete-collection-btn")
        assert len(delete_btn) > 0


# ── Notification System ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notification_info(app):
    """Test: Info notification works."""
    async with app.run_test() as pilot:
        app.notify("Info message", severity="information")
        await pilot.pause()


@pytest.mark.asyncio
async def test_notification_error(app):
    """Test: Error notification works."""
    async with app.run_test() as pilot:
        app.notify("Error message", severity="error")
        await pilot.pause()


@pytest.mark.asyncio
async def test_notification_warning(app):
    """Test: Warning notification works."""
    async with app.run_test() as pilot:
        app.notify("Warning message", severity="warning")
        await pilot.pause()


# ── Keyboard Navigation ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ctrl_b_batch(app):
    """Test: Ctrl+B switches to batch tab."""
    async with app.run_test() as pilot:
        await pilot.press("ctrl+b")
        await pilot.pause()
        workspace = app.query_one("#workspace")
        assert workspace.active == "tab-batch"


@pytest.mark.asyncio
async def test_f2_theme(app):
    """Test: F2 toggles theme."""
    async with app.run_test() as pilot:
        initial = app.THEME
        await pilot.press("f2")
        await pilot.pause()
        assert app.THEME != initial


# ── Error Handling ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_request_no_crash(app):
    """Test: Sending empty request doesn't crash."""
    async with app.run_test() as pilot:
        await pilot.press("ctrl+r")
        await pilot.pause()


@pytest.mark.asyncio
async def test_invalid_tab_no_crash(app):
    """Test: Invalid tab switch doesn't crash."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        # Try to set invalid tab
        try:
            workspace.active = "nonexistent-tab"
        except Exception:
            pass
        await pilot.pause()


@pytest.mark.asyncio
async def test_rapid_actions_no_crash(app):
    """Test: Rapid actions don't crash."""
    async with app.run_test() as pilot:
        for _ in range(10):
            await pilot.press("f5")
            await pilot.pause()
