"""Laptop settings: volume, brightness, battery, Wi-Fi status, and power actions."""

from __future__ import annotations

import ctypes
import re
import subprocess

from teamloop.computer import com


def _ps(command: str, timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                          capture_output=True, text=True, timeout=timeout)


# ---- volume (COM, on the COM thread) ---------------------------------------------------------
def _endpoint():
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    speakers = AudioUtilities.GetSpeakers()
    endpoint = getattr(speakers, "EndpointVolume", None)
    if endpoint is not None:
        return endpoint
    from ctypes import POINTER, cast

    from comtypes import CLSCTX_ALL

    return cast(speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume))


def _get_volume() -> tuple[int, bool]:
    ep = _endpoint()
    return round(ep.GetMasterVolumeLevelScalar() * 100), bool(ep.GetMute())


def _set_volume(level: int | None, mute: bool | None) -> tuple[int, bool]:
    ep = _endpoint()
    if level is not None:
        ep.SetMasterVolumeLevelScalar(max(0, min(100, level)) / 100, None)
        if level > 0 and mute is None:
            ep.SetMute(0, None)
    if mute is not None:
        ep.SetMute(1 if mute else 0, None)
    return _get_volume()


async def get_volume() -> tuple[int, bool]:
    return await com.run(_get_volume)


async def set_volume(level: int | None = None, mute: bool | None = None) -> tuple[int, bool]:
    return await com.run(_set_volume, level, mute)


# ---- brightness (WMI; laptop screens only) --------------------------------------------------
def get_brightness() -> int | None:
    out = _ps("(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness -ErrorAction Stop).CurrentBrightness")
    match = re.search(r"\d+", out.stdout or "")
    return int(match.group(0)) if out.returncode == 0 and match else None


def set_brightness(level: int) -> int | None:
    level = max(0, min(100, int(level)))
    _ps("Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods -ErrorAction Stop | "
        f"Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Timeout=1; Brightness={level}}} | Out-Null")
    return get_brightness()


# ---- battery and Wi-Fi ------------------------------------------------------------------------
def battery() -> dict | None:
    import psutil

    b = psutil.sensors_battery()
    if b is None:
        return None
    return {"percent": round(b.percent), "plugged_in": bool(b.power_plugged)}


def wifi() -> dict:
    out = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=10)
    text = out.stdout or ""
    state = re.search(r"^\s*State\s*:\s*(.+)$", text, re.M)
    ssid = re.search(r"^\s*SSID\s*:\s*(.+)$", text, re.M)
    return {"state": state.group(1).strip() if state else "unknown", "network": ssid.group(1).strip() if ssid else None}


# ---- power --------------------------------------------------------------------------------------
def lock() -> None:
    ctypes.windll.user32.LockWorkStation()


def sleep() -> None:
    # SetSuspendState(Suspend) is real sleep; rundll32 powrprof hibernates when hibernation is on.
    _ps("Add-Type -AssemblyName System.Windows.Forms; "
        "[System.Windows.Forms.Application]::SetSuspendState([System.Windows.Forms.PowerState]::Suspend, $false, $false)")


def shutdown(restart: bool = False, delay: int = 60) -> None:
    subprocess.run(["shutdown", "/r" if restart else "/s", "/t", str(int(delay))], capture_output=True, timeout=10)


def cancel_shutdown() -> bool:
    return subprocess.run(["shutdown", "/a"], capture_output=True, timeout=10).returncode == 0
