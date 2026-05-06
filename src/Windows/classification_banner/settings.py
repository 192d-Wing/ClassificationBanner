"""
Settings management for Classification Banner
"""

from typing import Dict, Any
from .constants import (
    DEFAULT_CLASSIFICATION,
    DEFAULT_BG_COLOR,
    DEFAULT_FG_COLOR,
    DEFAULT_BANNER_HEIGHT,
    DEFAULT_FONT_SIZE,
    DEFAULT_FONT_FAMILY,
    DEFAULT_ENABLED,
    DEFAULT_FPCON,
    DEFAULT_CPCON,
    DEFAULT_CHECK_INTERVAL,
    DEFAULT_CAVEATS,
    DEFAULT_DISSEMINATION_CONTROLS,
)


class BannerSettings:
    """Manages banner configuration settings"""

    def __init__(self):
        # Display settings
        self.classification: str = DEFAULT_CLASSIFICATION
        self.bg_color: str = DEFAULT_BG_COLOR
        self.fg_color: str = DEFAULT_FG_COLOR
        self.banner_height: int = DEFAULT_BANNER_HEIGHT
        self.font_size: int = DEFAULT_FONT_SIZE
        self.font_family: str = DEFAULT_FONT_FAMILY
        self.enabled: int = DEFAULT_ENABLED
        self.caveats: str | None = DEFAULT_CAVEATS
        self.dissemination_controls: str | None = (
            DEFAULT_DISSEMINATION_CONTROLS
        )
        self.classification_text: str = DEFAULT_CLASSIFICATION

        # Threat levels
        self.fpcon: str = DEFAULT_FPCON
        self.cpcon: str = DEFAULT_CPCON

        # System info flags
        self.show_hostname: bool = False
        self.show_username: bool = False
        self.show_windows_version: bool = False
        self.show_ip_address: bool = False
        self.show_group_id: bool = False

        # Group ID value
        self.group_id: str = ""

        # Monitoring
        self.check_interval: int = DEFAULT_CHECK_INTERVAL

        # Storage for change detection
        self.previous_settings: Dict[str, str | bool | int] = {}

    _REGISTRY_ATTR_MAP: Dict[str, str] = {
        "Classification": "classification",
        "BackgroundColor": "bg_color",
        "TextColor": "fg_color",
        "FPCON": "fpcon",
        "GroupID": "group_id",
        "Caveats": "caveats",
        "DisseminationControls": "dissemination_controls",
        "Enabled": "enabled",
        "FontSize": "font_size",
        "BannerHeight": "banner_height",
        "FontFamily": "font_family",
        "ShowHostname": "show_hostname",
        "ShowUsername": "show_username",
        "ShowWindowsVersion": "show_windows_version",
        "ShowIPAddress": "show_ip_address",
        "ShowGroupID": "show_group_id",
    }

    def update_from_registry(self, registry_settings: Dict[str, Any]) -> None:
        """Update settings from registry values"""
        for reg_name, attr_name in self._REGISTRY_ATTR_MAP.items():
            value = registry_settings.get(reg_name)
            if value is not None:
                setattr(self, attr_name, value)

        # CPCON is special-cased: stored as int in registry, used as str
        if registry_settings.get("CPCON") is not None:
            self.cpcon = str(registry_settings["CPCON"])

    # Attributes watched for change detection. Anything that should trigger a
    # banner recreate when its registry value changes belongs here.
    _WATCHED_ATTRS = (
        "classification",
        "bg_color",
        "fg_color",
        "enabled",
        "fpcon",
        "cpcon",
        "caveats",
        "dissemination_controls",
        "show_hostname",
        "show_username",
        "show_windows_version",
        "show_ip_address",
        "show_group_id",
        "group_id",
        "font_size",
        "banner_height",
        "font_family",
    )

    def _snapshot(self) -> Dict[str, Any]:
        return {name: getattr(self, name) for name in self._WATCHED_ATTRS}

    def store_current_state(self) -> None:
        """Store current settings for change detection"""
        self.previous_settings = self._snapshot()

    def has_changed(self) -> bool:
        """Check if settings have changed since last store"""
        return self._snapshot() != self.previous_settings

    def needs_system_info(self) -> bool:
        """Check if any system info should be displayed"""
        return any(
            [
                self.show_hostname,
                self.show_username,
                self.show_windows_version,
                self.show_ip_address,
                self.show_group_id,
            ]
        )

    def get_show_flags(self) -> Dict[str, bool]:
        """Get dictionary of system info display flags"""
        return {
            "show_hostname": self.show_hostname,
            "show_username": self.show_username,
            "show_windows_version": self.show_windows_version,
            "show_ip_address": self.show_ip_address,
            "show_group_id": self.show_group_id,
        }

    def get_classification_text(self) -> None:
        """Generates the classification text for the center banner"""
        classification = ""
        if self.classification == "SCI":
            classification = classification + "TOP SECRET"
        else:
            classification = classification + f"{self.classification}"

        if self.caveats:
            classification = classification + fr"//{self.caveats}"
        if self.dissemination_controls:
            classification = classification + \
                fr"//{self.dissemination_controls}"

        self.classification_text = classification
