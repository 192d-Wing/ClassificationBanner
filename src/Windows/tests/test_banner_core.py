# tests/test_banner_core.py
#
# Pytest coverage for core logic in the Windows Classification Banner.
# NOTE: Intentionally written without mocking – these tests exercise
# the real implementations and only rely on minimal, stable invariants.

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from classification_banner.constants import (
    DEFAULT_CLASSIFICATION,
    DEFAULT_BG_COLOR,
    DEFAULT_FG_COLOR,
    DEFAULT_BANNER_HEIGHT,
    DEFAULT_FONT_SIZE,
    DEFAULT_FONT_FAMILY,
    DEFAULT_ENABLED,
    DEFAULT_FPCON,
    DEFAULT_CPCON,
    COLOR_SCHEMES,
)
from classification_banner.settings import BannerSettings
from classification_banner.registry_manager import RegistryManager
from classification_banner.system_info import SystemInfoGatherer
from classification_banner.monitor_manager import MonitorManager


# ---------------------------------------------------------------------------
# BannerSettings tests
# ---------------------------------------------------------------------------


def test_banner_settings_defaults_match_constants():
    settings = BannerSettings()

    # Display settings
    assert settings.classification == DEFAULT_CLASSIFICATION
    assert settings.bg_color == DEFAULT_BG_COLOR
    assert settings.fg_color == DEFAULT_FG_COLOR
    assert settings.banner_height == DEFAULT_BANNER_HEIGHT
    assert settings.font_size == DEFAULT_FONT_SIZE
    assert settings.font_family == DEFAULT_FONT_FAMILY
    assert settings.enabled == DEFAULT_ENABLED

    # Threat levels
    assert settings.fpcon == DEFAULT_FPCON
    assert settings.cpcon == DEFAULT_CPCON

    # System info flags default to False
    assert settings.show_hostname is False
    assert settings.show_username is False
    assert settings.show_windows_version is False
    assert settings.show_ip_address is False
    assert settings.show_group_id is False

    # Monitoring
    assert isinstance(settings.check_interval, int)


def test_banner_settings_update_from_registry_and_show_flags():
    settings = BannerSettings()

    registry_values = {
        # String values
        "Classification": "SECRET",
        "BackgroundColor": "#112233",
        "TextColor": "#445566",
        "FPCON": "BRAVO",
        "CPCON": "3",
        "GroupID": "TEST-GROUP",
        "Caveats": "HCS",
        "DisseminationControls": "NOFORN",
        # Integer
        "Enabled": 1,
        # Booleans (all True)
        "ShowHostname": True,
        "ShowUsername": True,
        "ShowWindowsVersion": True,
        "ShowIPAddress": True,
        "ShowGroupID": True
    }

    settings.update_from_registry(registry_values)

    assert settings.classification == "SECRET"
    assert settings.bg_color == "#112233"
    assert settings.fg_color == "#445566"
    assert settings.fpcon == "BRAVO"
    assert settings.cpcon == "3"
    assert settings.group_id == "TEST-GROUP"
    assert settings.caveats == "HCS"
    assert settings.dissemination_controls == "NOFORN"
    assert settings.enabled == 1

    # Flags should mirror the registry values
    assert settings.show_hostname is True
    assert settings.show_username is True
    assert settings.show_windows_version is True
    assert settings.show_ip_address is True
    assert settings.show_group_id is True

    # get_show_flags() should reflect those attributes
    flags = settings.get_show_flags()
    assert flags == {
        "show_hostname": True,
        "show_username": True,
        "show_windows_version": True,
        "show_ip_address": True,
        "show_group_id": True,
    }


def test_banner_settings_store_state_and_has_changes_detects_diff():
    settings = BannerSettings()

    # Initial state: nothing stored yet
    settings.store_current_state()
    assert settings.has_changed() is False

    # Changing a single field should be detected
    settings.classification = "SECRET"
    assert settings.has_changed() is True

    # After re-storing state, no changes again
    settings.store_current_state()
    assert settings.has_changed() is False

    # Flip a boolean
    settings.show_hostname = True
    assert settings.has_changed() is True


def test_banner_settings_classification_text_for_plain_and_sci():
    settings = BannerSettings()

    # Plain classification with caveats and DC
    settings.classification = "SECRET"
    settings.caveats = "HCS"
    settings.dissemination_controls = "NOFORN"
    settings.get_classification_text()
    assert settings.classification_text == "SECRET//HCS//NOFORN"

    # SCI classification maps to TOP SECRET
    settings.classification = "SCI"
    settings.caveats = "HCS/SI/TK"
    settings.dissemination_controls = "NOFORN"
    settings.get_classification_text()
    assert settings.classification_text == "TOP SECRET//HCS/SI/TK//NOFORN"


def test_banner_settings_needs_system_info_reflects_flags():
    settings = BannerSettings()
    # All flags False -> no system info needed
    assert settings.needs_system_info() is False

    settings.show_hostname = True
    assert settings.needs_system_info() is True

    settings.show_hostname = False
    settings.show_ip_address = True
    assert settings.needs_system_info() is True


# ---------------------------------------------------------------------------
# RegistryManager tests (pure color-scheme logic only)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="RegistryManager is Windows-only")
def test_registry_manager_apply_color_schemes_uses_predefined_colors_when_not_customized():
    rm = RegistryManager()

    # No explicit colors – should pick from COLOR_SCHEMES
    settings = {"Classification": "SECRET"}
    result = rm._apply_color_schemes(dict(settings))

    scheme = COLOR_SCHEMES["SECRET"]
    assert result["BackgroundColor"] == scheme["bg"]
    assert result["TextColor"] == scheme["fg"]


@pytest.mark.skipif(sys.platform != "win32", reason="RegistryManager is Windows-only")
def test_registry_manager_apply_color_schemes_does_not_override_custom_colors():
    rm = RegistryManager()

    settings = {
        "Classification": "SECRET",
        "BackgroundColor": "#111111",
        "TextColor": "#222222",
    }
    result = rm._apply_color_schemes(dict(settings))

    # Custom colors should be preserved
    assert result["BackgroundColor"] == "#111111"
    assert result["TextColor"] == "#222222"


@pytest.mark.skipif(sys.platform != "win32", reason="RegistryManager is Windows-only")
def test_registry_manager_load_settings_returns_dict_without_crashing():
    """
    This intentionally does not assert specific values because that would
    depend on the actual registry contents on the machine running the tests.

    The invariant we care about (without mocking) is:
    - load_settings() returns a dict
    - It does not raise even if keys are absent.
    """
    rm = RegistryManager()
    settings = rm.load_settings()
    assert isinstance(settings, dict)


# ---------------------------------------------------------------------------
# SystemInfoGatherer tests
# ---------------------------------------------------------------------------


def test_system_info_gather_all_respects_flags_and_group_id():
    gatherer = SystemInfoGatherer()

    # Start with all False; nothing should be returned even with group_id
    flags = {
        "show_hostname": False,
        "show_username": False,
        "show_windows_version": False,
        "show_ip_address": False,
        "show_group_id": False,
    }

    info = gatherer.gather_all(flags, group_id="TESTGROUP")
    assert info == {}

    # Enable hostname only
    flags["show_hostname"] = True
    info = gatherer.gather_all(flags, group_id="TESTGROUP")
    assert "hostname" in info
    assert isinstance(info["hostname"], str)
    assert info["hostname"]  # non-empty

    # Enable group_id as well
    flags["show_group_id"] = True
    info = gatherer.gather_all(flags, group_id="TESTGROUP")
    assert info.get("group_id") == "TESTGROUP"


def test_system_info_build_display_text_orders_fields_correctly():
    gatherer = SystemInfoGatherer()

    data = {
        "hostname": "HOST",
        "username": "USER",
        "windows_version": "Win 11",
        "ip_address": "192.0.2.1",
        "group_id": "UNIT",
    }

    text = gatherer.build_display_text(data)
    assert text == "HOST | USER | Win 11 | 192.0.2.1 | Group: UNIT"


def test_system_info_build_display_text_skips_missing_values():
    gatherer = SystemInfoGatherer()

    # Only hostname and group_id present
    data = {
        "hostname": "HOST",
        "username": "",
        "windows_version": "",
        "ip_address": "",
        "group_id": "UNIT",
    }

    text = gatherer.build_display_text(data)
    # Only non-empty keys should be included
    assert text == "HOST | Group: UNIT"


# ---------------------------------------------------------------------------
# MonitorManager tests
# ---------------------------------------------------------------------------


def test_monitor_manager_fallback_monitor_shape():
    fallback = MonitorManager._create_fallback_monitor()

    assert fallback.x == 0
    assert fallback.y == 0
    assert fallback.width == 1920
    assert fallback.height == 1080


def test_monitor_manager_get_all_monitors_returns_objects_with_required_attributes():
    """
    This test intentionally does not assume anything about the actual
    monitors connected. The invariant is:

    - At least one monitor-like object is returned.
    - Each object has x, y, width, and height attributes.
    - If screeninfo.get_monitors() fails, the fallback monitor still satisfies
      these requirements.
    """
    monitors = MonitorManager.get_all_monitors()
    assert monitors, "Expected at least one monitor object"

    for m in monitors:
        for attr in ("x", "y", "width", "height"):
            assert hasattr(m, attr), f"Monitor is missing attribute {attr}"


# ---------------------------------------------------------------------------
# Fullscreen suppression allow-list (decision logic only — Win32 calls not
# exercised here). decide_hide and normalize_allow_list are pure functions.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="fullscreen_watcher imports ctypes.windll")
def test_normalize_allow_list_parses_and_lowercases():
    from classification_banner.fullscreen_watcher import normalize_allow_list
    assert normalize_allow_list(None) == ()
    assert normalize_allow_list("") == ()
    assert normalize_allow_list("PowerPnt.exe") == ("powerpnt.exe",)
    assert normalize_allow_list(" a.exe ; B.EXE ;;c.exe ") == (
        "a.exe", "b.exe", "c.exe"
    )


@pytest.mark.skipif(sys.platform != "win32", reason="fullscreen_watcher imports ctypes.windll")
def test_decide_hide_empty_allow_list_returns_false():
    from classification_banner.fullscreen_watcher import decide_hide
    # Even when everything else matches, an empty allow list never hides.
    assert decide_hide(
        allowed=(),
        foreground_proc="powerpnt.exe",
        foreground_win_rect=(0, 0, 1920, 1080),
        foreground_mon_rect=(0, 0, 1920, 1080),
        banner_monitor=(0, 0, 1920, 1080),
    ) is False


@pytest.mark.skipif(sys.platform != "win32", reason="fullscreen_watcher imports ctypes.windll")
def test_decide_hide_process_not_in_list_returns_false():
    from classification_banner.fullscreen_watcher import decide_hide
    assert decide_hide(
        allowed=("powerpnt.exe",),
        foreground_proc="notepad.exe",
        foreground_win_rect=(0, 0, 1920, 1080),
        foreground_mon_rect=(0, 0, 1920, 1080),
        banner_monitor=(0, 0, 1920, 1080),
    ) is False


@pytest.mark.skipif(sys.platform != "win32", reason="fullscreen_watcher imports ctypes.windll")
def test_decide_hide_different_monitor_returns_false():
    from classification_banner.fullscreen_watcher import decide_hide
    # Foreground app is fullscreen but on monitor 2; banner is on monitor 1.
    assert decide_hide(
        allowed=("powerpnt.exe",),
        foreground_proc="powerpnt.exe",
        foreground_win_rect=(1920, 0, 3840, 1080),
        foreground_mon_rect=(1920, 0, 3840, 1080),
        banner_monitor=(0, 0, 1920, 1080),
    ) is False


@pytest.mark.skipif(sys.platform != "win32", reason="fullscreen_watcher imports ctypes.windll")
def test_decide_hide_maximized_but_not_fullscreen_returns_false():
    from classification_banner.fullscreen_watcher import decide_hide
    # Maximized respects the work area (y=20 because of banner). Not fullscreen.
    assert decide_hide(
        allowed=("powerpnt.exe",),
        foreground_proc="powerpnt.exe",
        foreground_win_rect=(0, 20, 1920, 1080),
        foreground_mon_rect=(0, 0, 1920, 1080),
        banner_monitor=(0, 0, 1920, 1080),
    ) is False


@pytest.mark.skipif(sys.platform != "win32", reason="fullscreen_watcher imports ctypes.windll")
def test_decide_hide_true_fullscreen_on_banner_monitor_returns_true():
    from classification_banner.fullscreen_watcher import decide_hide
    assert decide_hide(
        allowed=("powerpnt.exe",),
        foreground_proc="POWERPNT.EXE",  # case-insensitive match
        foreground_win_rect=(0, 0, 1920, 1080),
        foreground_mon_rect=(0, 0, 1920, 1080),
        banner_monitor=(0, 0, 1920, 1080),
    ) is True
