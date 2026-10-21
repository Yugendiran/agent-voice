"""Start the narrator in the background when the user logs in."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

LABEL = "agent-voice"


def background_python() -> str:
    """The interpreter to run in the background (pythonw on Windows: no console)."""
    exe = Path(sys.executable)
    if platform.system() == "Windows":
        windowless = exe.with_name("pythonw.exe")
        if windowless.exists():
            return str(windowless)
    return str(exe)


def _windows_path() -> Path:
    startup = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup"
    return startup / f"{LABEL}.vbs"


def _mac_path() -> Path:
    return Path.home() / f"Library/LaunchAgents/com.{LABEL}.plist"


def _linux_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / f"autostart/{LABEL}.desktop"


def path() -> Path:
    system = platform.system()
    if system == "Windows":
        return _windows_path()
    if system == "Darwin":
        return _mac_path()
    return _linux_path()


def enable() -> Path:
    py = background_python()
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    system = platform.system()
    if system == "Windows":
        # A .vbs launcher runs pythonw with no console window flashing up.
        cmd = f'""{py}"" -m agent_voice run --quiet'
        target.write_text(f'CreateObject("WScript.Shell").Run "{cmd}", 0, False\r\n', encoding="utf-8")
    elif system == "Darwin":
        target.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.{LABEL}</string>
  <key>ProgramArguments</key>
  <array><string>{py}</string><string>-m</string><string>agent_voice</string><string>run</string><string>--quiet</string></array>
  <key>RunAtLoad</key><true/>
</dict>
</plist>
""",
            encoding="utf-8",
        )
    else:
        target.write_text(
            f"""[Desktop Entry]
Type=Application
Name=agent-voice
Comment=Speaks what Claude Code and Codex say while they work
Exec="{py}" -m agent_voice run --quiet
X-GNOME-Autostart-enabled=true
NoDisplay=true
""",
            encoding="utf-8",
        )
    return target


def disable() -> bool:
    target = path()
    if target.exists():
        target.unlink()
        return True
    return False


def enabled() -> bool:
    return path().exists()
