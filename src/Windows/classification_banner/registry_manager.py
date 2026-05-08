"""
Windows Registry management for Classification Banner
"""

from typing import Dict, Any, Optional, List, Tuple
import winreg
from .constants import COLOR_SCHEMES


class RegistryManager:
    """Handles reading configuration from Windows Registry"""

    def __init__(self):
        self.registry_locations: List[Tuple[int, str]] = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\ClassificationBanner"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\ClassificationBanner"),
        ]

    def load_settings(self) -> Dict[str, Any]:
        """Load all settings from registry"""
        settings = {}

        for hkey, subkey in self.registry_locations:
            try:
                key = winreg.OpenKey(hkey, subkey, 0, winreg.KEY_READ)
                settings = self._read_all_values(key)
                winreg.CloseKey(key)
                break  # Successfully read, don't try next location
            except FileNotFoundError:
                continue
            except SystemError as e:
                print(f"Error reading registry at {hkey}\\{subkey}: {e}")
                continue

        return self._apply_color_schemes(settings)

    def _read_all_values(self, key: winreg.HKEYType) -> Dict[str, Any]:
        """Read all registry values from an open key"""
        settings: Dict[str, Any] = {}

        # String values
        for name in [
            "Classification",
            "BackgroundColor",
            "TextColor",
            "Caveats",
            "DisseminationControls",
            "FPCON",
            "CPCON",
            "GroupID",
            "FontFamily",
            "AllowedFullscreenProcesses",
        ]:
            settings[name] = self._read_string(key, name)

        # Integer values
        for name in ["Enabled", "FontSize", "BannerHeight"]:
            settings[name] = self._read_int(key, name)

        # Boolean values (stored as DWORD)
        for name in [
            "ShowHostname",
            "ShowUsername",
            "ShowWindowsVersion",
            "ShowIPAddress",
            "ShowGroupID",
        ]:
            settings[name] = self._read_bool(key, name)

        return settings

    def _read_string(self, key: winreg.HKEYType, name: str) -> Optional[str]:
        """Read a string value from registry"""
        try:
            value, _ = winreg.QueryValueEx(key, name)
            return value if value else None
        except FileNotFoundError:
            return None

    def _read_int(self, key: winreg.HKEYType, name: str) -> Optional[int]:
        """Read an integer value from registry"""
        try:
            value, _ = winreg.QueryValueEx(key, name)
            return int(value)
        except FileNotFoundError:
            return None

    def _read_bool(self, key: winreg.HKEYType, name: str) -> Optional[bool]:
        """Read a boolean value from registry (stored as DWORD)"""
        try:
            value, _ = winreg.QueryValueEx(key, name)
            return bool(int(value))
        except FileNotFoundError:
            return None

    def _apply_color_schemes(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Apply predefined color schemes based on classification"""
        classification = settings.get("Classification", "").upper()

        if classification in COLOR_SCHEMES:
            scheme = COLOR_SCHEMES[classification]
            # Only apply if custom colors not set
            if not settings.get("BackgroundColor"):
                settings["BackgroundColor"] = scheme["bg"]
            if not settings.get("TextColor"):
                settings["TextColor"] = scheme["fg"]

        return settings

    def read_group_id(self) -> Optional[str]:
        """Read GroupID from registry"""
        for hkey, subkey in self.registry_locations:
            try:
                key = winreg.OpenKey(hkey, subkey, 0, winreg.KEY_READ)
                value, _ = winreg.QueryValueEx(key, "GroupID")
                winreg.CloseKey(key)
                if value:
                    return value
            except FileNotFoundError:
                continue
        return None
