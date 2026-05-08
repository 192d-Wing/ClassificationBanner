"""
Audit log for banner-suppression events under the fullscreen allow list.

Prefers %ProgramData%\\ClassificationBanner\\audit.log (shared across
users; the PSADT installer is expected to pre-create the directory with
ACLs allowing user write but admin-only modify of existing files —
tamper-evident). If that path isn't writable, falls back to
%LOCALAPPDATA%\\ClassificationBanner\\audit.log so events are still
captured locally.
"""

import logging
import os
import socket
from logging.handlers import RotatingFileHandler

_LOGGER_NAME = "ClassificationBanner.audit"
_LOG_SUBDIR = "ClassificationBanner"
_LOG_FILE = "audit.log"
_MAX_BYTES = 1_048_576  # 1 MiB
_BACKUP_COUNT = 5

_logger: logging.Logger | None = None


def _candidate_dirs() -> list[str]:
    return [
        os.path.join(
            os.environ.get("ProgramData", r"C:\ProgramData"), _LOG_SUBDIR
        ),
        os.path.join(
            os.environ.get(
                "LOCALAPPDATA",
                os.path.join(os.path.expanduser("~"), "AppData", "Local"),
            ),
            _LOG_SUBDIR,
        ),
    ]


def _resolve_writable_log_path() -> str | None:
    """Return the first log path we can actually open for append, or None."""
    for d in _candidate_dirs():
        try:
            os.makedirs(d, exist_ok=True)
            path = os.path.join(d, _LOG_FILE)
            # Touch-test: verifies append works without leaving content.
            with open(path, "a", encoding="utf-8") as fh:
                fh.write("")
            return path
        except OSError:
            continue
    return None


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_path = _resolve_writable_log_path()
    if log_path is None:
        # No writable location — silently no-op so the banner keeps running.
        logger.addHandler(logging.NullHandler())
    else:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s host=%(hostname)s user=%(user)s %(message)s"
            )
        )
        logger.addHandler(handler)

    _logger = logger
    return logger


def _extra() -> dict:
    return {
        "hostname": socket.gethostname(),
        "user": os.environ.get("USERNAME", "unknown"),
    }


def log_banner_hidden(process_name: str, monitor: tuple[int, int, int, int]) -> None:
    """Record that the banner stepped aside for an allow-listed fullscreen app."""
    x, y, w, h = monitor
    _get_logger().info(
        "event=banner-hide process=%s monitor=%dx%d@%d,%d",
        process_name, w, h, x, y,
        extra=_extra(),
    )


def log_banner_restored(monitor: tuple[int, int, int, int]) -> None:
    """Record that the banner became visible again after a fullscreen exit."""
    x, y, w, h = monitor
    _get_logger().info(
        "event=banner-restore monitor=%dx%d@%d,%d",
        w, h, x, y,
        extra=_extra(),
    )
