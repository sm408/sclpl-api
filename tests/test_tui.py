from __future__ import annotations


class TestTUIModuleImports:
    """Verify the TUI module structure imports correctly."""

    def test_import_tui_module(self) -> None:
        import app.ui.tui as tui_module
        assert tui_module is not None

    def test_import_logo_module(self) -> None:
        import app.ui.logo as logo_module
        assert logo_module is not None

    def test_import_version_from_logo(self) -> None:
        from app.ui.logo import VERSION
        assert VERSION is not None

    def test_import_logos_from_logo(self) -> None:
        from app.ui.logo import COMPACT_LOGO, LOGO
        assert LOGO is not None
        assert COMPACT_LOGO is not None


class TestLogoConstants:
    """Verify logo and branding constants."""

    def test_logo_is_string(self) -> None:
        from app.ui.logo import LOGO
        assert isinstance(LOGO, str)

    def test_logo_contains_project_name(self) -> None:
        from app.ui.logo import LOGO
        assert "API Workflow Studio" in LOGO

    def test_compact_logo_is_string(self) -> None:
        from app.ui.logo import COMPACT_LOGO
        assert isinstance(COMPACT_LOGO, str)

    def test_version_is_string(self) -> None:
        from app.ui.logo import VERSION
        assert isinstance(VERSION, str)

    def test_version_format(self) -> None:
        from app.ui.logo import VERSION
        assert VERSION.startswith("v")

    def test_divider_constant_exists(self) -> None:
        from app.ui.logo import DIVIDER
        assert isinstance(DIVIDER, str)

    def test_thin_divider_constant_exists(self) -> None:
        from app.ui.logo import THIN_DIVIDER
        assert isinstance(THIN_DIVIDER, str)


class TestStatusConstants:
    """Verify status icon constants exist and are strings."""

    def test_pending_constant(self) -> None:
        from app.ui.tui import PENDING
        assert isinstance(PENDING, str)

    def test_running_constant(self) -> None:
        from app.ui.tui import RUNNING
        assert isinstance(RUNNING, str)

    def test_success_constant(self) -> None:
        from app.ui.tui import SUCCESS
        assert isinstance(SUCCESS, str)

    def test_failed_constant(self) -> None:
        from app.ui.tui import FAILED
        assert isinstance(FAILED, str)

    def test_skipped_constant(self) -> None:
        from app.ui.tui import SKIPPED
        assert isinstance(SKIPPED, str)

    def test_status_map_keys(self) -> None:
        from app.ui.tui import STATUS_MAP
        assert "pending" in STATUS_MAP
        assert "running" in STATUS_MAP
        assert "success" in STATUS_MAP
        assert "failed" in STATUS_MAP
        assert "skipped" in STATUS_MAP


class TestStepStateDataclass:
    """Verify StepState dataclass works correctly."""

    def test_step_state_import(self) -> None:
        from app.ui.tui import StepState
        assert StepState is not None

    def test_step_state_creation(self) -> None:
        from app.ui.tui import StepState
        step = StepState(id="s1", name="Step One", step_type="request")
        assert step.id == "s1"
        assert step.name == "Step One"
        assert step.step_type == "request"
        assert step.status == "pending"
        assert step.started_at == 0.0
        assert step.completed_at == 0.0
        assert step.duration_ms == 0
        assert step.error is None
        assert step.output_summary == ""
        assert step.depends_on == []
        assert step.group_index == 0

    def test_step_state_with_custom_values(self) -> None:
        from app.ui.tui import StepState
        step = StepState(
            id="s2",
            name="Step Two",
            step_type="function",
            status="success",
            started_at=1.0,
            completed_at=2.5,
            duration_ms=1500,
            output_summary="ok",
            depends_on=["s1"],
            group_index=1,
        )
        assert step.status == "success"
        assert step.duration_ms == 1500
        assert step.depends_on == ["s1"]
        assert step.group_index == 1

    def test_step_state_is_dataclass(self) -> None:
        from dataclasses import fields

        from app.ui.tui import StepState
        field_names = {f.name for f in fields(StepState)}
        assert "id" in field_names
        assert "name" in field_names
        assert "step_type" in field_names
        assert "status" in field_names
        assert "depends_on" in field_names


class TestTUIClass:
    """Verify TUI class exists and can be instantiated."""

    def test_tui_class_import(self) -> None:
        from app.ui.tui import TUI
        assert TUI is not None

    def test_tui_instantiation(self) -> None:
        from app.ui.tui import TUI
        tui = TUI()
        assert tui is not None

    def test_tui_has_run_method(self) -> None:
        from app.ui.tui import TUI
        tui = TUI()
        assert hasattr(tui, "run")
        assert callable(tui.run)

    def test_tui_default_db_path(self) -> None:
        from app.ui.tui import TUI
        tui = TUI()
        assert tui.db_path == "data/sclplapi.db"

    def test_tui_custom_db_path(self) -> None:
        from app.ui.tui import TUI
        tui = TUI(db_path="/tmp/test.db")
        assert tui.db_path == "/tmp/test.db"


class TestLaunchTuiFunction:
    """Verify launch_tui function exists and is callable."""

    def test_launch_tui_import(self) -> None:
        from app.ui.tui import launch_tui
        assert launch_tui is not None

    def test_launch_tui_is_callable(self) -> None:
        from app.ui.tui import launch_tui
        assert callable(launch_tui)
