"""
Banner window creation and management
"""

import tkinter as tk
from tkinter import font
from . import audit
from .appbar import register_appbar_for_window, remove_appbar_for_window
from .constants import (
    ABE_TOP,
    FULLSCREEN_CHECK_INTERVAL,
    INNER_PADX,
    INNER_PADY,
    KEEP_ON_TOP_INTERVAL,
)
from .fullscreen_watcher import decide_hide, query_foreground


class BannerWindow:
    """Manages a single banner window"""

    def __init__(self, monitor, settings, system_info_text: str = ""):
        self.monitor = monitor
        self.settings = settings
        self.system_info_text = system_info_text
        self.window: tk.Tk | None = None
        self.hwnd = None
        self._hidden_for_fullscreen = False

        self._create_window()

    def _create_window(self):
        """Create the banner window"""
        self.window = tk.Tk()

        # Position at top of monitor
        self.window.geometry(
            f"{self.monitor.width}x{self.settings.banner_height}"
            f"+{self.monitor.x}+{self.monitor.y}"
        )

        # Remove window decorations
        self.window.overrideredirect(True)

        # Set background color
        self.window.configure(bg=self.settings.bg_color)

        # Always on top
        self.window.attributes("-topmost", True)

        # Register as AppBar
        self.window.update_idletasks()
        self.hwnd = self.window.winfo_id()

        register_appbar_for_window(
            self.hwnd,
            self.monitor.x,
            self.monitor.y,
            self.monitor.width,
            self.settings.banner_height,
            edge=ABE_TOP,
        )

        # Create UI
        self._create_ui()

        # Keep on top
        self._keep_on_top()

        # Step aside for allow-listed fullscreen apps on this monitor
        self._schedule_fullscreen_check()

        # Cleanup on close
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_ui(self):
        """Create the banner UI elements"""
        # Main frame
        main_frame = tk.Frame(self.window, bg=self.settings.bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Configure grid
        main_frame.grid_rowconfigure(0, weight=1)

        # 🔧 Key change: left & right expand, center stays fixed
        main_frame.grid_columnconfigure(0, weight=1, uniform="sides")  # left grows
        main_frame.grid_columnconfigure(1, weight=0)  # center stays natural size
        main_frame.grid_columnconfigure(2, weight=1, uniform="sides")  # right grows

        # Create font
        label_font = font.Font(
            family=self.settings.font_family,
            size=self.settings.font_size,
            weight="bold",
        )

        # Left side: System information
        if self.system_info_text:
            self._create_left_panel(main_frame, label_font)

        # Center: Classification
        self._create_center_panel(main_frame, label_font)

        # Right side: FPCON/CPCON
        if self.settings.fpcon or self.settings.cpcon:
            self._create_right_panel(main_frame, label_font)

    def _create_left_panel(self, parent, label_font):
        """Create left panel with system info"""
        left_frame = tk.Frame(parent, bg=self.settings.bg_color)
        left_frame.grid(
            row=0,
            column=0,
            sticky="nsw",
            padx=(INNER_PADX, INNER_PADX),
            pady=INNER_PADY,
        )

        sys_info_label = tk.Label(
            left_frame,
            text=self.system_info_text,
            bg=self.settings.bg_color,
            fg=self.settings.fg_color,
            font=label_font,
            anchor="w",
        )
        sys_info_label.pack(fill=tk.BOTH, expand=True)

    def _create_center_panel(self, parent, label_font):
        """Create center panel with classification"""
        center_frame = tk.Frame(parent, bg=self.settings.bg_color)
        center_frame.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=INNER_PADX,
            pady=INNER_PADY,
        )

        classification_label = tk.Label(
            center_frame,
            text=self.settings.classification_text,
            bg=self.settings.bg_color,
            fg=self.settings.fg_color,
            font=label_font,
            anchor="center",
        )
        classification_label.pack(expand=True, fill=tk.BOTH)

    def _create_right_panel(self, parent, label_font):
        """Create right panel with FPCON/CPCON"""
        right_frame = tk.Frame(parent, bg=self.settings.bg_color)
        right_frame.grid(
            row=0,
            column=2,
            sticky="nse",
            padx=(INNER_PADX, INNER_PADX),
            pady=INNER_PADY,
        )

        # Build text
        right_text_parts = []
        if self.settings.fpcon:
            right_text_parts.append(f"FPCON: {self.settings.fpcon}")
        if self.settings.cpcon:
            right_text_parts.append(f"CPCON: {self.settings.cpcon}")

        right_text = " | ".join(right_text_parts)

        right_label = tk.Label(
            right_frame,
            text=right_text,
            bg=self.settings.bg_color,
            fg=self.settings.fg_color,
            font=label_font,
            anchor="e",
        )
        right_label.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)

    def _keep_on_top(self):
        """Keep window on top"""
        try:
            self.window.attributes("-topmost", True)
            self.window.lift()
            self.window.after(KEEP_ON_TOP_INTERVAL, self._keep_on_top)
        except:
            pass

    def _monitor_box(self) -> tuple[int, int, int, int]:
        return (
            self.monitor.x, self.monitor.y,
            self.monitor.width, self.monitor.height,
        )

    def _schedule_fullscreen_check(self):
        if self.window:
            self.window.after(
                FULLSCREEN_CHECK_INTERVAL, self._check_fullscreen
            )

    def _check_fullscreen(self):
        try:
            allowed = self.settings.allowed_fullscreen_processes
            if not allowed:
                # Fast path: no allow list configured, ensure visible.
                if self._hidden_for_fullscreen:
                    self._restore_for_fullscreen()
                return

            proc, win_rect, mon_rect = query_foreground()
            should_hide = decide_hide(
                allowed, proc, win_rect, mon_rect, self._monitor_box()
            )

            if should_hide and not self._hidden_for_fullscreen:
                self._hide_for_fullscreen(proc or "?")
            elif not should_hide and self._hidden_for_fullscreen:
                self._restore_for_fullscreen()
        except tk.TclError:
            # Window is being destroyed — stop polling.
            return
        except OSError as e:
            # Win32 call failed; log once-per-tick to audit but keep polling.
            print(f"fullscreen watcher error: {e}")
        finally:
            self._schedule_fullscreen_check()

    def _hide_for_fullscreen(self, process_name: str):
        try:
            self.window.withdraw()
        except tk.TclError:
            return
        self._hidden_for_fullscreen = True
        audit.log_banner_hidden(process_name, self._monitor_box())

    def _restore_for_fullscreen(self):
        try:
            self.window.deiconify()
            self.window.attributes("-topmost", True)
            self.window.lift()
        except tk.TclError:
            return
        self._hidden_for_fullscreen = False
        audit.log_banner_restored(self._monitor_box())

    def _on_close(self):
        """Handle window close"""
        try:
            remove_appbar_for_window(self.hwnd)
        except:
            pass
        self.window.destroy()

    def destroy(self):
        """Destroy the window"""
        try:
            remove_appbar_for_window(self.hwnd)
        except:
            pass

        try:
            self.window.destroy()
        except:
            pass

    def get_window(self):
        """Get the Tk window object"""
        return self.window
