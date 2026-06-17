"""
Monitor detection and management
"""

from typing import Any
from screeninfo import get_monitors
from . import eventlog


class MonitorManager:
    """Manages monitor detection"""

    @staticmethod
    def get_all_monitors() -> Any:
        """Get all connected monitors"""
        try:
            return get_monitors()
        except Exception as e:
            # screeninfo raises its own ScreenInfoError (not a SystemError)
            # when monitor enumeration fails, which happens transiently
            # around sleep/resume and display power-off. Catch broadly so a
            # transient failure degrades to a fallback monitor instead of
            # propagating out of the Tk callback and killing the banner.
            # Emit a diagnostic so the degraded single-monitor fallback isn't
            # silent (print goes nowhere in the windowed exe).
            print(f"Error detecting monitors: {e}")
            eventlog.log_warning(
                f"Monitor enumeration failed; using fallback monitor: {e!r}"
            )
            # Fallback to single monitor
            return [MonitorManager._create_fallback_monitor()]

    @staticmethod
    def _create_fallback_monitor():
        """Create a fallback monitor object"""
        return type("Monitor", (), {"x": 0, "y": 0, "width": 1920, "height": 1080})()
