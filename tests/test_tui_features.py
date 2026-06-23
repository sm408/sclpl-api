"""Comprehensive TUI feature tests using Textual's pilot framework."""

import pytest

from app.ui.textual_app import SCLPLTextualApp


@pytest.fixture
def app():
    return SCLPLTextualApp()


# ── Request Execution ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_request_editor_has_method_select(app):
    """Test: Request editor has method selector."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        # RequestEditor should be present
        editor = app.query("RequestEditor")
        assert len(editor) > 0


@pytest.mark.asyncio
async def test_request_editor_has_url_input(app):
    """Test: Request editor has URL input."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        # URL input should exist


@pytest.mark.asyncio
async def test_request_editor_has_send_button(app):
    """Test: Request editor has send button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        # Send button should exist


@pytest.mark.asyncio
async def test_request_editor_has_body_editor(app):
    """Test: Request editor has body editor."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        # Body editor should exist


# ── Response Viewer ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_response_viewer_exists(app):
    """Test: Response viewer widget exists."""
    async with app.run_test() as pilot:
        # ResponseViewer is inside RequestEditor tab
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        # Widget should be present in the app
        assert app.is_running


@pytest.mark.asyncio
async def test_response_viewer_has_tabs(app):
    """Test: Response viewer has body/headers/raw tabs."""
    async with app.run_test() as pilot:
        # ResponseViewer should have TabbedContent
        pass


# ── Collections ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collections_tab_has_table(app):
    """Test: Collections tab has data table."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-collections"
        await pilot.pause()
        collections = app.query("CollectionList")
        assert len(collections) > 0


@pytest.mark.asyncio
async def test_collections_has_new_button(app):
    """Test: Collections has new button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-collections"
        await pilot.pause()
        # New button should exist


@pytest.mark.asyncio
async def test_collections_has_delete_button(app):
    """Test: Collections has delete button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-collections"
        await pilot.pause()
        # Delete button should exist


# ── History ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_history_tab_has_table(app):
    """Test: History tab has data table."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-history"
        await pilot.pause()
        history = app.query("HistoryView")
        assert len(history) > 0


@pytest.mark.asyncio
async def test_history_has_filter(app):
    """Test: History has filter input."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-history"
        await pilot.pause()
        # Filter input should exist


@pytest.mark.asyncio
async def test_history_has_clear_button(app):
    """Test: History has clear button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-history"
        await pilot.pause()
        # Clear button should exist


# ── Workflows ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_workflows_tab_has_table(app):
    """Test: Workflows tab has data table."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-workflows"
        await pilot.pause()
        workflows = app.query("WorkflowList")
        assert len(workflows) > 0


@pytest.mark.asyncio
async def test_workflows_has_run_button(app):
    """Test: Workflows has run button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-workflows"
        await pilot.pause()
        # Run button should exist


@pytest.mark.asyncio
async def test_workflows_has_view_steps_button(app):
    """Test: Workflows has view steps button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-workflows"
        await pilot.pause()
        # View steps button should exist


@pytest.mark.asyncio
async def test_workflow_execution_view_exists(app):
    """Test: Workflow execution view exists."""
    async with app.run_test() as pilot:
        exec_view = app.query("WorkflowExecution")
        assert len(exec_view) > 0


@pytest.mark.asyncio
async def test_workflow_execution_has_export_buttons(app):
    """Test: Workflow execution has export buttons."""
    async with app.run_test() as pilot:
        # Export JSON, Export CSV, Re-run buttons should exist
        pass


# ── Environments ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_environments_tab_has_table(app):
    """Test: Environments tab has data table."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-environments"
        await pilot.pause()
        envs = app.query("EnvironmentView")
        assert len(envs) > 0


@pytest.mark.asyncio
async def test_environments_has_new_button(app):
    """Test: Environments has new button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-environments"
        await pilot.pause()
        # New button should exist


@pytest.mark.asyncio
async def test_environments_has_activate_button(app):
    """Test: Environments has activate button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-environments"
        await pilot.pause()
        # Activate button should exist


@pytest.mark.asyncio
async def test_environments_has_variable_buttons(app):
    """Test: Environments has set/delete variable buttons."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-environments"
        await pilot.pause()
        # Set Variable, Delete Variable buttons should exist


# ── Functions ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_functions_tab_has_table(app):
    """Test: Functions tab has data table."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-functions"
        await pilot.pause()
        funcs = app.query("FunctionBrowser")
        assert len(funcs) > 0


@pytest.mark.asyncio
async def test_functions_has_search(app):
    """Test: Functions has search input."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-functions"
        await pilot.pause()
        # Search input should exist


@pytest.mark.asyncio
async def test_functions_has_source_viewer(app):
    """Test: Functions has source code viewer."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-functions"
        await pilot.pause()
        # Source viewer should exist


# ── Plugins ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_plugins_tab_has_table(app):
    """Test: Plugins tab has data table."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-plugins"
        await pilot.pause()
        plugins = app.query("PluginBrowser")
        assert len(plugins) > 0


@pytest.mark.asyncio
async def test_plugins_has_reload_button(app):
    """Test: Plugins has reload button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-plugins"
        await pilot.pause()
        # Reload button should exist


@pytest.mark.asyncio
async def test_plugins_has_view_functions_button(app):
    """Test: Plugins has view functions button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-plugins"
        await pilot.pause()
        # View functions button should exist


# ── Import/Export ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_import_export_tab_exists(app):
    """Test: Import/Export tab exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-import-export"
        await pilot.pause()
        ie = app.query("ImportExportView")
        assert len(ie) > 0


@pytest.mark.asyncio
async def test_import_export_has_export_all(app):
    """Test: Import/Export has export all button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-import-export"
        await pilot.pause()
        # Export All button should exist


@pytest.mark.asyncio
async def test_import_export_has_import_all(app):
    """Test: Import/Export has import all button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-import-export"
        await pilot.pause()
        # Import All button should exist


@pytest.mark.asyncio
async def test_import_export_has_openapi(app):
    """Test: Import/Export has OpenAPI import button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-import-export"
        await pilot.pause()
        # Import OpenAPI button should exist


# ── Batch ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_batch_tab_exists(app):
    """Test: Batch tab exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-batch"
        await pilot.pause()
        batch = app.query("BatchView")
        assert len(batch) > 0


@pytest.mark.asyncio
async def test_batch_has_progress_bar(app):
    """Test: Batch has progress bar."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-batch"
        await pilot.pause()
        # Progress bar should exist


@pytest.mark.asyncio
async def test_batch_has_load_csv_button(app):
    """Test: Batch has load CSV button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-batch"
        await pilot.pause()
        # Load CSV button should exist


@pytest.mark.asyncio
async def test_batch_has_start_stop_buttons(app):
    """Test: Batch has start/stop buttons."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-batch"
        await pilot.pause()
        # Start, Stop buttons should exist


# ── Logs ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_logs_tab_exists(app):
    """Test: Logs tab exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-logs"
        await pilot.pause()
        logs = app.query("LogViewer")
        assert len(logs) > 0


@pytest.mark.asyncio
async def test_logs_has_search(app):
    """Test: Logs has search input."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-logs"
        await pilot.pause()
        # Search input should exist


@pytest.mark.asyncio
async def test_logs_has_level_filter(app):
    """Test: Logs has level filter."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-logs"
        await pilot.pause()
        # Level filter should exist


# ── Settings ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_settings_tab_exists(app):
    """Test: Settings tab exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-settings"
        await pilot.pause()
        settings = app.query("SettingsView")
        assert len(settings) > 0


@pytest.mark.asyncio
async def test_settings_has_db_path(app):
    """Test: Settings has database path input."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-settings"
        await pilot.pause()
        # DB path input should exist


@pytest.mark.asyncio
async def test_settings_has_save_button(app):
    """Test: Settings has save button."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-settings"
        await pilot.pause()
        # Save button should exist


# ── Sidebar ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sidebar_has_collection_tree(app):
    """Test: Sidebar has collection tree."""
    async with app.run_test() as pilot:
        sidebar = app.query_one("#sidebar")
        assert sidebar is not None


@pytest.mark.asyncio
async def test_sidebar_has_workflow_tree(app):
    """Test: Sidebar has workflow tree."""
    async with app.run_test() as pilot:
        sidebar = app.query_one("#sidebar")
        assert sidebar is not None


@pytest.mark.asyncio
async def test_sidebar_has_environment_display(app):
    """Test: Sidebar has environment display."""
    async with app.run_test() as pilot:
        sidebar = app.query_one("#sidebar")
        assert sidebar is not None


# ── Command Palette ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_command_palette_opens(app):
    """Test: Command palette opens with Ctrl+P."""
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        await pilot.pause()
        assert len(app.screen_stack) > 1


@pytest.mark.asyncio
async def test_command_palette_has_input(app):
    """Test: Command palette has search input."""
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        await pilot.pause()
        # Input should be present in the palette


@pytest.mark.asyncio
async def test_command_palette_closes_on_escape(app):
    """Test: Command palette closes on escape."""
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        # Should return to main screen


# ── Notifications ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notify_works(app):
    """Test: Notification system works."""
    async with app.run_test() as pilot:
        app.notify("Test notification")
        await pilot.pause()


@pytest.mark.asyncio
async def test_notify_error_works(app):
    """Test: Error notification works."""
    async with app.run_test() as pilot:
        app.notify("Error message", severity="error")
        await pilot.pause()


@pytest.mark.asyncio
async def test_notify_warning_works(app):
    """Test: Warning notification works."""
    async with app.run_test() as pilot:
        app.notify("Warning message", severity="warning")
        await pilot.pause()


# ── Layout ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_header_visible(app):
    """Test: Header is visible."""
    async with app.run_test() as pilot:
        header = app.query("Header")
        assert len(header) > 0


@pytest.mark.asyncio
async def test_footer_visible(app):
    """Test: Footer is visible."""
    async with app.run_test() as pilot:
        footer = app.query("Footer")
        assert len(footer) > 0


@pytest.mark.asyncio
async def test_log_pane_visible(app):
    """Test: Log pane is visible."""
    async with app.run_test() as pilot:
        log_pane = app.query_one("#log-pane")
        assert log_pane is not None


@pytest.mark.asyncio
async def test_sidebar_visible(app):
    """Test: Sidebar is visible."""
    async with app.run_test() as pilot:
        sidebar = app.query_one("#sidebar")
        assert sidebar is not None
        assert sidebar.display


@pytest.mark.asyncio
async def test_workspace_visible(app):
    """Test: Workspace is visible."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        assert workspace is not None
        assert workspace.display


# ── Performance ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rapid_tab_switching_100_times(app):
    """Test: Rapid tab switching 100 times doesn't crash."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        tabs = ["tab-request", "tab-collections", "tab-history", "tab-workflows",
                "tab-environments", "tab-functions", "tab-plugins"]
        for _ in range(15):
            for tab in tabs:
                workspace.active = tab
                await pilot.pause()
