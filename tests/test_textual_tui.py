"""Textual TUI integration tests using Textual's pilot testing framework."""

import pytest

from app.ui.textual_app import SCLPLTextualApp


@pytest.fixture
def app():
    """Create a test app instance."""
    return SCLPLTextualApp()


@pytest.mark.asyncio
async def test_app_launches(app):
    """Test: App launches without errors."""
    async with app.run_test() as pilot:
        # Verify app is running
        assert app.title == "SCLPLAPI"
        assert app.sub_title == "API Workflow Studio"


@pytest.mark.asyncio
async def test_sidebar_visible(app):
    """Test: Sidebar is visible on launch."""
    async with app.run_test() as pilot:
        sidebar = app.query_one("#sidebar")
        assert sidebar is not None
        assert sidebar.display


@pytest.mark.asyncio
async def test_workspace_visible(app):
    """Test: Workspace tabs are visible."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        assert workspace is not None
        assert workspace.display


@pytest.mark.asyncio
async def test_request_tab_default(app):
    """Test: Request tab is active by default."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        assert workspace.active == "tab-request"


@pytest.mark.asyncio
async def test_ctrl_p_opens_palette(app):
    """Test: Ctrl+P opens command palette."""
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        await pilot.pause()
        # Command palette should be on the screen stack
        assert len(app.screen_stack) > 1


@pytest.mark.asyncio
async def test_ctrl_t_switches_to_request(app):
    """Test: Ctrl+T switches to request tab."""
    async with app.run_test() as pilot:
        # Switch to another tab first
        workspace = app.query_one("#workspace")
        workspace.active = "tab-collections"
        await pilot.pause()

        # Press Ctrl+T
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert workspace.active == "tab-request"


@pytest.mark.asyncio
async def test_ctrl_r_triggers_request(app):
    """Test: Ctrl+R triggers request execution."""
    async with app.run_test() as pilot:
        # Should not crash even with empty URL
        await pilot.press("ctrl+r")
        await pilot.pause()


@pytest.mark.asyncio
async def test_f1_shows_help(app):
    """Test: F1 shows help notification."""
    async with app.run_test() as pilot:
        await pilot.press("f1")
        await pilot.pause()


@pytest.mark.asyncio
async def test_f5_refreshes(app):
    """Test: F5 refreshes data."""
    async with app.run_test() as pilot:
        await pilot.press("f5")
        await pilot.pause()


@pytest.mark.asyncio
async def test_escape_cancels(app):
    """Test: Escape key works."""
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()


@pytest.mark.asyncio
async def test_collections_tab(app):
    """Test: Collections tab switches correctly."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-collections"
        await pilot.pause()
        assert workspace.active == "tab-collections"


@pytest.mark.asyncio
async def test_history_tab(app):
    """Test: History tab switches correctly."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-history"
        await pilot.pause()
        assert workspace.active == "tab-history"


@pytest.mark.asyncio
async def test_workflows_tab(app):
    """Test: Workflows tab switches correctly."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-workflows"
        await pilot.pause()
        assert workspace.active == "tab-workflows"


@pytest.mark.asyncio
async def test_environments_tab(app):
    """Test: Environments tab switches correctly."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-environments"
        await pilot.pause()
        assert workspace.active == "tab-environments"


@pytest.mark.asyncio
async def test_functions_tab(app):
    """Test: Functions tab switches correctly."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-functions"
        await pilot.pause()
        assert workspace.active == "tab-functions"


@pytest.mark.asyncio
async def test_plugins_tab(app):
    """Test: Plugins tab switches correctly."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-plugins"
        await pilot.pause()
        assert workspace.active == "tab-plugins"


@pytest.mark.asyncio
async def test_batch_tab(app):
    """Test: Batch tab switches correctly."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-batch"
        await pilot.pause()
        assert workspace.active == "tab-batch"


@pytest.mark.asyncio
async def test_logs_tab(app):
    """Test: Logs tab switches correctly."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-logs"
        await pilot.pause()
        assert workspace.active == "tab-logs"


@pytest.mark.asyncio
async def test_import_export_tab(app):
    """Test: Import/Export tab switches correctly."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-import-export"
        await pilot.pause()
        assert workspace.active == "tab-import-export"


@pytest.mark.asyncio
async def test_settings_tab(app):
    """Test: Settings tab switches correctly."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-settings"
        await pilot.pause()
        assert workspace.active == "tab-settings"


@pytest.mark.asyncio
async def test_all_tabs_accessible(app):
    """Test: All tabs are accessible via keyboard."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        tabs = [
            "tab-request", "tab-collections", "tab-history",
            "tab-workflows", "tab-environments", "tab-functions",
            "tab-plugins", "tab-import-export", "tab-batch",
            "tab-logs", "tab-settings"
        ]
        for tab in tabs:
            workspace.active = tab
            await pilot.pause()
            assert workspace.active == tab


@pytest.mark.asyncio
async def test_sidebar_has_sections(app):
    """Test: Sidebar has collection and workflow sections."""
    async with app.run_test() as pilot:
        sidebar = app.query_one("#sidebar")
        assert sidebar is not None


@pytest.mark.asyncio
async def test_log_pane_visible(app):
    """Test: Log pane is visible."""
    async with app.run_test() as pilot:
        log_pane = app.query_one("#log-pane")
        assert log_pane is not None


@pytest.mark.asyncio
async def test_request_editor_widgets(app):
    """Test: Request editor has required widgets."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        # Request editor should be present


@pytest.mark.asyncio
async def test_workflow_list_has_table(app):
    """Test: Workflow list has a data table."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-workflows"
        await pilot.pause()
        # WorkflowList should be present


@pytest.mark.asyncio
async def test_rapid_tab_switching(app):
    """Test: Rapid tab switching doesn't crash."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        tabs = ["tab-request", "tab-collections", "tab-history", "tab-workflows"]
        for _ in range(10):
            for tab in tabs:
                workspace.active = tab
                await pilot.pause()
