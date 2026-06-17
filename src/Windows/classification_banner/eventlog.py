"""
Write diagnostic events to the ClassificationBanner ETW provider.

The banner runs windowed (``console=False``), so ``print`` output is
discarded and a crash leaves no trace. This module emits events through a
manifest-based ETW provider so unexpected exits are diagnosable in Event
Viewer under:

    Applications and Services Logs > ClassificationBanner > Operational

The provider, channel, and event descriptors are defined in
``EventManifest/ClassificationBanner.man`` and compiled into
``ClassificationBannerEvents.dll``, which the installer registers with
``wevtutil im``. The constants below MUST match that manifest byte-for-byte
(provider GUID, channel value, and each event's Id/Version/Level).

Dependency-free: uses ctypes against advapi32's EventRegister/EventWrite,
so it works inside the PyInstaller bundle with no extra packages.
Best-effort by design — any failure is swallowed so logging can never take
the banner down. If the manifest isn't registered (e.g. running from source
on a dev box), EventWrite still succeeds but the events have nowhere to land.
"""

from __future__ import annotations

import ctypes
import time
import uuid

# Mirror of EventManifest/ClassificationBanner.man — keep in sync.
_PROVIDER_GUID = uuid.UUID("34b8ff43-cbe0-4960-b499-a31859d10e47")
_CHANNEL_OPERATIONAL = 16  # <channel ... value="16"/>

# win: level values (winmeta).
_LEVEL_ERROR = 2
_LEVEL_WARNING = 3
_LEVEL_INFORMATIONAL = 4

# Event ids — one per <event> in the manifest.
_EVENT_STARTED = 1     # BANNER_STARTED   (Informational)
_EVENT_RECOVERED = 2   # BANNER_RECOVERED (Warning)
_EVENT_CRASHED = 3     # BANNER_CRASHED   (Error)

_ERROR_SUCCESS = 0


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_uuid(cls, u: uuid.UUID) -> "_GUID":
        d4 = (ctypes.c_ubyte * 8)(*u.bytes[8:])
        return cls(
            (u.int >> 96) & 0xFFFFFFFF,
            (u.int >> 80) & 0xFFFF,
            (u.int >> 64) & 0xFFFF,
            d4,
        )


class _EVENT_DESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("Id", ctypes.c_ushort),
        ("Version", ctypes.c_ubyte),
        ("Channel", ctypes.c_ubyte),
        ("Level", ctypes.c_ubyte),
        ("Opcode", ctypes.c_ubyte),
        ("Task", ctypes.c_ushort),
        ("Keyword", ctypes.c_ulonglong),
    ]


class _EVENT_DATA_DESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("Ptr", ctypes.c_ulonglong),
        ("Size", ctypes.c_ulong),
        ("Reserved", ctypes.c_ulong),
    ]


_REGHANDLE = ctypes.c_ulonglong

_advapi32 = ctypes.windll.advapi32
_advapi32.EventRegister.restype = ctypes.c_ulong
_advapi32.EventRegister.argtypes = [
    ctypes.POINTER(_GUID),  # ProviderId
    ctypes.c_void_p,        # EnableCallback
    ctypes.c_void_p,        # CallbackContext
    ctypes.POINTER(_REGHANDLE),
]
_advapi32.EventWrite.restype = ctypes.c_ulong
_advapi32.EventWrite.argtypes = [
    _REGHANDLE,
    ctypes.POINTER(_EVENT_DESCRIPTOR),
    ctypes.c_ulong,
    ctypes.POINTER(_EVENT_DATA_DESCRIPTOR),
]
_advapi32.EventUnregister.restype = ctypes.c_ulong
_advapi32.EventUnregister.argtypes = [_REGHANDLE]

_reg_handle: int | None = None


def _get_handle() -> int | None:
    """Register the provider once and cache the handle. None on failure."""
    global _reg_handle
    if _reg_handle is not None:
        return _reg_handle
    try:
        guid = _GUID.from_uuid(_PROVIDER_GUID)
        handle = _REGHANDLE(0)
        rc = _advapi32.EventRegister(
            ctypes.byref(guid), None, None, ctypes.byref(handle)
        )
        if rc != _ERROR_SUCCESS:
            return None
        _reg_handle = handle.value
        return _reg_handle
    except OSError:
        return None


# Collapse a repeated identical event (e.g. a persistent error firing on a
# 2-second Tk timer) to at most one write per this window, so a long-lived
# failure doesn't flood the channel. A different message, or the same one after
# the window elapses, writes immediately.
_THROTTLE_SECONDS = 60.0
_last_event: tuple[int, str] | None = None
_last_event_at = 0.0


def _write(event_id: int, level: int, message: str) -> None:
    """Best-effort single event write. Never raises."""
    global _last_event, _last_event_at
    now = time.monotonic()
    key = (event_id, message)
    if key == _last_event and (now - _last_event_at) < _THROTTLE_SECONDS:
        return
    _last_event = key
    _last_event_at = now

    handle = _get_handle()
    if not handle:
        return
    try:
        desc = _EVENT_DESCRIPTOR(
            Id=event_id,
            Version=0,
            Channel=_CHANNEL_OPERATIONAL,
            Level=level,
            Opcode=0,
            Task=0,
            Keyword=0,
        )
        # One UnicodeString payload (the "Message" template field). ETW
        # convention: include the terminating null in the byte count.
        buf = ctypes.create_unicode_buffer(message)
        data = _EVENT_DATA_DESCRIPTOR(
            Ptr=ctypes.cast(buf, ctypes.c_void_p).value,
            Size=ctypes.sizeof(buf),
            Reserved=0,
        )
        _advapi32.EventWrite(handle, ctypes.byref(desc), 1, ctypes.byref(data))
    except OSError:
        return


def log_error(message: str) -> None:
    """Record an error-level event (e.g. an unhandled crash)."""
    _write(_EVENT_CRASHED, _LEVEL_ERROR, message)


def log_warning(message: str) -> None:
    """Record a warning-level event (e.g. a recovered runtime error)."""
    _write(_EVENT_RECOVERED, _LEVEL_WARNING, message)


def log_info(message: str) -> None:
    """Record an informational event (e.g. startup/shutdown)."""
    _write(_EVENT_STARTED, _LEVEL_INFORMATIONAL, message)
