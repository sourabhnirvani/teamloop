"""Desk's computer kit. Importing it makes the process per-monitor DPI aware (v2), once, before pywinauto or
anything else reads a window rect: rects, screenshots and the mouse then all use physical pixels."""

import ctypes
import logging
import sys

log = logging.getLogger(__name__)


def _make_dpi_aware() -> int:
    """Ask for per-monitor v2 (it can only be set once per process; "already set" is fine). Returns what we got:
    0 unaware, 1 system, 2 per-monitor."""
    if sys.platform != "win32":
        return 2
    user32 = ctypes.windll.user32
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))   # PER_MONITOR_AWARE_V2
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass
    try:
        return int(user32.GetAwarenessFromDpiAwarenessContext(user32.GetThreadDpiAwarenessContext()))
    except (AttributeError, OSError):
        return -1


DPI_AWARENESS = _make_dpi_aware()
if DPI_AWARENESS != 2:
    log.warning("DPI awareness is %s, not per-monitor: clicks may land off on scaled screens", DPI_AWARENESS)
else:
    log.info("DPI awareness: per-monitor")
