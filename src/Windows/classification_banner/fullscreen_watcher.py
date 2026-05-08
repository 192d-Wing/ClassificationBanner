"""
Detect when an allow-listed fullscreen app is on the same monitor as the
banner so the banner can step aside.

Two layers:

1. ``decide_hide`` — pure function that takes the foreground process name,
   foreground window rect, monitor rect, banner monitor rect, and the
   admin-configured allow set, and returns True/False. Unit-testable.

2. ``query_foreground`` — Win32 wrapper that produces the inputs to
   ``decide_hide`` from the live system. Not testable without mocks; kept
   thin on purpose.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from typing import Iterable

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_MONITOR_DEFAULTTONEAREST = 2

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", wintypes.DWORD),
    ]


# Tuple shape used by both the Win32 wrapper and decide_hide:
#   (left, top, right, bottom)
Rect = tuple[int, int, int, int]
# Banner monitor shape:
#   (x, y, width, height)
MonitorBox = tuple[int, int, int, int]


def normalize_allow_list(raw: str | None) -> tuple[str, ...]:
    """Parse a registry value like 'powerpnt.exe;chrome.exe' into a
    case-folded tuple of executable basenames.
    """
    if not raw:
        return ()
    parts = (p.strip().lower() for p in raw.split(";"))
    return tuple(p for p in parts if p)


def decide_hide(
    allowed: Iterable[str],
    foreground_proc: str | None,
    foreground_win_rect: Rect | None,
    foreground_mon_rect: Rect | None,
    banner_monitor: MonitorBox,
) -> bool:
    """Return True iff the banner should step aside on this monitor.

    The banner only hides when ALL of:
    - allow list is non-empty
    - foreground process basename is in the allow list (case-insensitive)
    - foreground window is on the same physical monitor as this banner
    - foreground window covers the full monitor rect (true fullscreen,
      not merely maximized — maximized respects the AppBar work area
      already and doesn't need this).
    """
    allowed_set = {a.lower() for a in allowed}
    if not allowed_set or not foreground_proc:
        return False
    if foreground_proc.lower() not in allowed_set:
        return False
    if foreground_win_rect is None or foreground_mon_rect is None:
        return False

    bx, by, bw, bh = banner_monitor
    mleft, mtop, mright, mbottom = foreground_mon_rect
    if (
        mleft != bx
        or mtop != by
        or (mright - mleft) != bw
        or (mbottom - mtop) != bh
    ):
        # Foreground app is on a different monitor than this banner.
        return False

    wleft, wtop, wright, wbottom = foreground_win_rect
    return (
        wleft <= mleft
        and wtop <= mtop
        and wright >= mright
        and wbottom >= mbottom
    )


def _foreground_process_name(hwnd: int) -> str | None:
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return None
    handle = _kernel32.OpenProcess(
        _PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
    )
    if not handle:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if not _kernel32.QueryFullProcessImageNameW(
            handle, 0, buf, ctypes.byref(size)
        ):
            return None
        return os.path.basename(buf.value)
    finally:
        _kernel32.CloseHandle(handle)


def query_foreground() -> tuple[str | None, Rect | None, Rect | None]:
    """Snapshot the live foreground window: (process basename, window rect,
    its monitor rect). Returns (None, None, None) if anything fails — the
    caller treats that as 'don't hide'.
    """
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return None, None, None

    proc = _foreground_process_name(hwnd)

    win = _RECT()
    if not _user32.GetWindowRect(hwnd, ctypes.byref(win)):
        return proc, None, None
    win_rect: Rect = (win.left, win.top, win.right, win.bottom)

    hmon = _user32.MonitorFromWindow(hwnd, _MONITOR_DEFAULTTONEAREST)
    if not hmon:
        return proc, win_rect, None
    mi = _MONITORINFO()
    mi.cbSize = ctypes.sizeof(_MONITORINFO)
    if not _user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
        return proc, win_rect, None
    mon_rect: Rect = (
        mi.rcMonitor.left,
        mi.rcMonitor.top,
        mi.rcMonitor.right,
        mi.rcMonitor.bottom,
    )
    return proc, win_rect, mon_rect
