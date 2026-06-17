"""
Main Classification Banner application
"""

import sys
from typing import List
from . import eventlog
from .settings import BannerSettings
from .registry_manager import RegistryManager
from .system_info import SystemInfoGatherer
from .monitor_manager import MonitorManager
from .banner_window import BannerWindow


class ClassificationBanner:
    """Main Classification Banner application"""

    def __init__(self):
        self.settings = BannerSettings()
        self.registry_manager = RegistryManager()
        self.system_info_gatherer = SystemInfoGatherer()
        self.windows: List[BannerWindow] = []
        self.system_info_text: str = ""

        # Track monitor layout (x, y, width, height for each monitor)
        self._last_monitor_layout: list[tuple[int, int, int, int]] | None = None

        # Load initial settings
        self._load_settings()
        self.settings.store_current_state()

        # Gather system info if needed
        if self.settings.needs_system_info():
            self._gather_system_info()

        # Generate Classification Text
        self.settings.get_classification_text()

        # Create banners if enabled
        if self.settings.enabled:
            self._create_banners()
            self._schedule_registry_check()
            self._schedule_monitor_check()

    def _load_settings(self):
        """Load settings from registry"""
        registry_settings = self.registry_manager.load_settings()
        self.settings.update_from_registry(registry_settings)

    def _gather_system_info(self):
        """Gather system information"""
        # Get group ID from registry if showing
        group_id = None
        if self.settings.show_group_id:
            group_id = self.registry_manager.read_group_id()

        # Gather info
        info = self.system_info_gatherer.gather_all(
            self.settings.get_show_flags(), group_id
        )

        # Build display text
        self.system_info_text = self.system_info_gatherer.build_display_text(info)

    def _create_banners(self):
        """(Re)create banner windows for all monitors via an atomic swap.

        The new banners are built BEFORE the old ones are destroyed. Tk's main
        loop runs only while at least one window exists across all interpreters
        (``Tk_GetNumMainWindows() > 0``); building first guarantees the count
        never drops to zero (which would make ``mainloop`` return and exit the
        app) and leaves the existing banner intact if construction fails part
        way through.
        """
        monitors = MonitorManager.get_all_monitors()
        new_layout = [(m.x, m.y, m.width, m.height) for m in monitors]

        new_windows: List[BannerWindow] = []
        try:
            for monitor in monitors:
                new_windows.append(
                    BannerWindow(monitor, self.settings, self.system_info_text)
                )
        except Exception:
            # Construction failed partway: tear down the partial set so we
            # don't leak orphaned windows, and leave the existing banner in
            # place (self.windows is untouched until the swap below).
            for window in new_windows:
                window.destroy()
            raise

        # Swap in the new set, then tear down the old one.
        old_windows = self.windows
        self.windows = new_windows
        self._last_monitor_layout = new_layout
        for window in old_windows:
            window.destroy()

    def _recreate_banners(self):
        """Rebuild all banners (atomic swap; see _create_banners)."""
        # Regather system info if needed
        if self.settings.needs_system_info():
            self._gather_system_info()

        # Regenerate Classification Text
        self.settings.get_classification_text()

        # Build the new banners and swap out the old ones.
        self._create_banners()

    def _close_all_windows(self):
        """Close all banner windows"""
        for window in self.windows:
            window.destroy()
        self.windows = []

    def _get_monitor_layout(self) -> list[tuple[int, int, int, int]]:
        """Return a simple list describing all monitors."""
        monitors = MonitorManager.get_all_monitors()
        return [(m.x, m.y, m.width, m.height) for m in monitors]

    def _schedule_monitor_check(self):
        """Schedule periodic checks for monitor/resolution changes."""
        if self.windows:
            # Every 2 seconds – tune as needed
            self.windows[0].get_window().after(2000, self._check_monitor_changes)

    def _check_monitor_changes(self):
        """Recreate banners if the monitor layout has changed."""
        try:
            current_layout = self._get_monitor_layout()

            if self._last_monitor_layout is None:
                # First time – just remember it
                self._last_monitor_layout = current_layout
            elif current_layout != self._last_monitor_layout:
                print("Monitor layout changed – recreating banners...")
                self._last_monitor_layout = current_layout
                self._recreate_banners()

            # Keep checking
            self._schedule_monitor_check()

        except Exception as e:
            # Monitor enumeration can fail transiently around sleep/resume
            # and display power-off (e.g. screeninfo raises ScreenInfoError).
            # Catch broadly so a transient error never escapes the Tk
            # callback and kills the main loop; just retry next tick.
            print(f"Error checking monitor layout: {e}")
            eventlog.log_warning(f"Recovered from monitor-check error: {e!r}")
            # Try again next time even on error
            self._schedule_monitor_check()
    
    def _schedule_registry_check(self):
        """Schedule next registry check"""
        if self.windows:
            self.windows[0].get_window().after(
                self.settings.check_interval, self._check_registry_changes
            )

    def _check_registry_changes(self):
        """Check for registry changes and update if needed"""
        try:
            # Reload settings
            self._load_settings()

            # Check if changed
            if self.settings.has_changed():
                print("Registry settings changed - updating banner...")

                # If disabled, close everything
                if not self.settings.enabled:
                    print("Banner disabled - closing...")
                    self._close_all_windows()
                    sys.exit(0)

                # Recreate banners
                self._recreate_banners()

                # Update stored settings
                self.settings.store_current_state()

                print("Banner updated successfully")

            # Schedule next check
            self._schedule_registry_check()

        except Exception as e:
            # Catch broadly so a transient registry/recreate error can't
            # escape the Tk callback and tear down the main loop.
            print(f"Error checking registry changes: {e}")
            eventlog.log_warning(f"Recovered from registry-check error: {e!r}")
            # Continue checking even on error
            self._schedule_registry_check()

    def run(self):
        """Start the banner application"""
        if self.windows:
            self.windows[0].get_window().mainloop()
