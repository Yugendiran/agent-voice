"""A global keyboard shortcut that stops the speech playing right now.

Shortcuts are written like ``shift+backspace`` or ``ctrl+alt+x``. They work in
any window. The key press is not swallowed, so the focused app still gets it.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

log = logging.getLogger("agent_voice")

# Friendly names -> pynput key names.
_ALIASES = {
    "control": "ctrl",
    "option": "alt",
    "opt": "alt",
    "win": "cmd",
    "windows": "cmd",
    "super": "cmd",
    "meta": "cmd",
    "command": "cmd",
    "escape": "esc",
    "return": "enter",
    "del": "delete",
    "bksp": "backspace",
    "pgup": "page_up",
    "pgdn": "page_down",
}


def to_pynput(shortcut: str) -> str:
    """``shift+backspace`` -> ``<shift>+<backspace>``; raises ValueError if invalid."""
    keys = [k.strip().lower() for k in shortcut.split("+")]
    if not shortcut.strip() or any(not k for k in keys):
        raise ValueError(f"invalid shortcut: {shortcut!r}")
    parts = []
    for key in keys:
        key = _ALIASES.get(key, key)
        parts.append(key if len(key) == 1 else f"<{key}>")
    combo = "+".join(parts)
    from pynput.keyboard import HotKey

    try:
        HotKey.parse(combo)
    except ValueError as exc:
        raise ValueError(f"invalid shortcut {shortcut!r}: {exc}") from None
    return combo


class Hotkey:
    """Runs ``callback`` whenever ``shortcut`` is pressed, until ``stop()``."""

    def __init__(self, shortcut: str, callback: Callable[[], None]) -> None:
        self.shortcut = shortcut
        self._listener: Optional[object] = None
        if not shortcut:
            return
        try:
            from pynput.keyboard import GlobalHotKeys

            self._listener = GlobalHotKeys({to_pynput(shortcut): callback})
            self._listener.daemon = True
            self._listener.start()
            log.info("stop-speech shortcut: %s", shortcut)
        except Exception as exc:  # bad shortcut, Wayland, no macOS accessibility permission...
            self._listener = None
            log.warning("could not register shortcut %r: %s", shortcut, exc)

    @property
    def active(self) -> bool:
        return self._listener is not None

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
