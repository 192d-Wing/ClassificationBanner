"""
Windows AppBar management for Classification Banner
"""

import ctypes
from ctypes import wintypes
from typing import Literal, Any
from .constants import ABM_NEW, ABM_REMOVE, ABM_SETPOS, ABE_TOP


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class APPBARDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uCallbackMessage", wintypes.UINT),
        ("uEdge", wintypes.UINT),
        ("rc", RECT),
        ("lParam", wintypes.LPARAM),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]


_shell32 = ctypes.windll.shell32
_user32 = ctypes.windll.user32

# SetWindowPos flags
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010
_SWP_NOOWNERZORDER = 0x0200
_SWP_FRAMECHANGED = 0x0020

_MONITOR_DEFAULTTONULL = 0x00000000

# Declare prototypes so 64-bit handles aren't truncated to c_int.
_user32.MonitorFromWindow.restype = wintypes.HMONITOR
_user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
_user32.GetMonitorInfoW.restype = wintypes.BOOL
_user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
_user32.IsWindowVisible.argtypes = [wintypes.HWND]
_user32.IsZoomed.argtypes = [wintypes.HWND]
_user32.IsIconic.argtypes = [wintypes.HWND]
_user32.SetWindowPos.restype = wintypes.BOOL
_user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, wintypes.UINT,
]


def register_appbar_for_window(hwnd: Any, x: int, y: int, width: int, height: int, edge: Literal[1]=ABE_TOP) -> APPBARDATA:
    """Register/position a window as an AppBar so maximized windows avoid it."""
    abd = APPBARDATA()
    abd.cbSize = ctypes.sizeof(APPBARDATA)
    abd.hWnd = hwnd
    abd.uCallbackMessage = 0
    abd.uEdge = edge

    abd.rc.left = x
    abd.rc.top = y
    abd.rc.right = x + width
    abd.rc.bottom = y + height

    _shell32.SHAppBarMessage(ABM_NEW, ctypes.byref(abd))
    _shell32.SHAppBarMessage(ABM_SETPOS, ctypes.byref(abd))

    _user32.MoveWindow(
        hwnd,
        abd.rc.left,
        abd.rc.top,
        abd.rc.right - abd.rc.left,
        abd.rc.bottom - abd.rc.top,
        True,
    )

    # Reserving the work area does not re-flow windows that were ALREADY
    # maximized before this AppBar existed (e.g. a window maximized while the
    # workstation was locked and the banner wasn't running). Nudge them so
    # they shrink to the new, reduced work area instead of overlapping us.
    reflow_maximized_windows(hwnd)

    return abd


# EnumWindows callback type: BOOL CALLBACK(HWND, LPARAM)
_ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def reflow_maximized_windows(skip_hwnd: Any = None) -> None:
    """Resize already-maximized top-level windows to their monitor work area.

    Windows only re-flows maximized windows when they receive a work-area
    change; a fresh AppBar registration doesn't deliver one to pre-existing
    maximized windows. We enumerate them and resize each to its monitor's
    current ``rcWork`` (which now excludes the banner), without activating or
    changing z-order so we don't steal focus.
    """
    skip = int(skip_hwnd) if skip_hwnd else 0

    def _callback(hwnd: int, _lparam: int) -> bool:
        try:
            if hwnd == skip:
                return True
            if not _user32.IsWindowVisible(hwnd):
                return True
            # Only touch maximized windows; leave normal/minimized alone.
            if not _user32.IsZoomed(hwnd) or _user32.IsIconic(hwnd):
                return True

            monitor = _user32.MonitorFromWindow(hwnd, _MONITOR_DEFAULTTONULL)
            if not monitor:
                return True

            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if not _user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                return True

            work = info.rcWork
            _user32.SetWindowPos(
                hwnd,
                0,
                work.left,
                work.top,
                work.right - work.left,
                work.bottom - work.top,
                _SWP_NOZORDER | _SWP_NOACTIVATE | _SWP_NOOWNERZORDER
                | _SWP_FRAMECHANGED,
            )
        except OSError:
            # A window can vanish mid-enumeration; keep going.
            pass
        return True

    _user32.EnumWindows(_ENUM_PROC(_callback), 0)


def remove_appbar_for_window(hwnd: Any) -> None:
    """Unregister the AppBar."""
    abd = APPBARDATA()
    abd.cbSize = ctypes.sizeof(APPBARDATA)
    abd.hWnd = hwnd
    _shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(abd))
