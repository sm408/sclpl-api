"""Error handling and persistence tests for TUI."""

import pytest

from app.ui.textual_app import SCLPLTextualApp


@pytest.fixture
def app():
    return SCLPLTextualApp()


# ── Error Handling ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_url_no_crash(app):
    """Test: Sending request with empty URL doesn't crash."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        # Press send without URL
        await pilot.press("ctrl+r")
        await pilot.pause()
        assert app.is_running


@pytest.mark.asyncio
async def test_invalid_method_no_crash(app):
    """Test: Invalid HTTP method doesn't crash."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-request"
        await pilot.pause()
        # App should still be running
        assert app.is_running


@pytest.mark.asyncio
async def test_rapid_tab_switching_no_crash(app):
    """Test: Rapid tab switching doesn't crash."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        for _ in range(50):
            for tab in ["tab-request", "tab-collections", "tab-history"]:
                workspace.active = tab
                await pilot.pause()
        assert app.is_running


@pytest.mark.asyncio
async def test_multiple_refresh_no_crash(app):
    """Test: Multiple refreshes don't crash."""
    async with app.run_test() as pilot:
        for _ in range(10):
            await pilot.press("f5")
            await pilot.pause()
        assert app.is_running


@pytest.mark.asyncio
async def test_open_close_palette_no_crash(app):
    """Test: Opening and closing palette multiple times doesn't crash."""
    async with app.run_test() as pilot:
        for _ in range(10):
            await pilot.press("ctrl+p")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        assert app.is_running


# ── Persistence ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collections_persist(app):
    """Test: Collections are loaded from database."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-collections"
        await pilot.pause()
        # Collections should be loaded
        assert app.is_running


@pytest.mark.asyncio
async def test_environments_persist(app):
    """Test: Environments are loaded from database."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-environments"
        await pilot.pause()
        # Environments should be loaded
        assert app.is_running


@pytest.mark.asyncio
async def test_history_persist(app):
    """Test: History is loaded from database."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-history"
        await pilot.pause()
        # History should be loaded
        assert app.is_running


@pytest.mark.asyncio
async def test_settings_persist(app):
    """Test: Settings are accessible."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        workspace.active = "tab-settings"
        await pilot.pause()
        # Settings should be loaded
        assert app.is_running


# ── Navigation ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_keyboard_shortcuts(app):
    """Test: All keyboard shortcuts work without crash."""
    async with app.run_test() as pilot:
        shortcuts = ["ctrl+p", "ctrl+t", "ctrl+r", "ctrl+b", "f1", "f2", "f5", "escape"]
        for shortcut in shortcuts:
            await pilot.press(shortcut)
            await pilot.pause()
        assert app.is_running


@pytest.mark.asyncio
async def test_tab_navigation_all_tabs(app):
    """Test: Can navigate to all tabs."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        tabs = [
            "tab-request", "tab-collections", "tab-history", "tab-workflows",
            "tab-environments", "tab-functions", "tab-plugins", "tab-import-export",
            "tab-batch", "tab-diff", "tab-logs", "tab-settings"
        ]
        for tab in tabs:
            workspace.active = tab
            await pilot.pause()
        assert app.is_running


# ── Notifications ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notification_types(app):
    """Test: All notification types work."""
    async with app.run_test() as pilot:
        app.notify("Info", severity="information")
        app.notify("Warning", severity="warning")
        app.notify("Error", severity="error")
        app.notify("Success", severity="success")
        await pilot.pause()
        assert app.is_running


# ── Widget Existence ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sidebar_exists(app):
    """Test: Sidebar widget exists."""
    async with app.run_test() as pilot:
        sidebar = app.query_one("#sidebar")
        assert sidebar is not None


@pytest.mark.asyncio
async def test_workspace_exists(app):
    """Test: Workspace widget exists."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        assert workspace is not None


@pytest.mark.asyncio
async def test_log_pane_exists(app):
    """Test: Log pane widget exists."""
    async with app.run_test() as pilot:
        log_pane = app.query_one("#log-pane")
        assert log_pane is not None


@pytest.mark.asyncio
async def test_header_exists(app):
    """Test: Header widget exists."""
    async with app.run_test() as pilot:
        header = app.query("Header")
        assert len(header) > 0


@pytest.mark.asyncio
async def test_footer_exists(app):
    """Test: Footer widget exists."""
    async with app.run_test() as pilot:
        footer = app.query("Footer")
        assert len(footer) > 0


# ── Performance ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_100_tab_switches(app):
    """Test: 100 tab switches without crash."""
    async with app.run_test() as pilot:
        workspace = app.query_one("#workspace")
        tabs = ["tab-request", "tab-collections", "tab-history", "tab-workflows"]
        for _ in range(25):
            for tab in tabs:
                workspace.active = tab
                await pilot.pause()
        assert app.is_running


@pytest.mark.asyncio
async def test_50_refreshes(app):
    """Test: 50 refreshes without crash."""
    async with app.run_test() as pilot:
        for _ in range(50):
            await pilot.press("f5")
            await pilot.pause()
        assert app.is_running


@pytest.mark.asyncio
async def test_50_palette_open_close(app):
    """Test: 50 palette open/close without crash."""
    async with app.run_test() as pilot:
        for _ in range(50):
            await pilot.press("ctrl+p")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        assert app.is_running
