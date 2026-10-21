"""User configuration, stored as JSON in ~/.agent-voice/config.json."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

HOME = Path(os.environ.get("AGENT_VOICE_HOME", Path.home() / ".agent-voice"))
CONFIG_PATH = HOME / "config.json"
MODELS_DIR = HOME / "models"
LOG_PATH = HOME / "agent-voice.log"

# Control port on localhost. Binding it also acts as the single-instance lock.
CONTROL_PORT = int(os.environ.get("AGENT_VOICE_PORT", "47821"))


@dataclass
class Config:
    # "kokoro" (local neural TTS) or "system" (Windows SAPI / macOS say / espeak).
    engine: str = "kokoro"
    # "marked": speak only the short 🔊 lines the agents write for you (see
    # `agent-voice instructions`). "all": speak every message.
    speak: str = "marked"
    # What the agents are told to say (rewrites their instructions when changed):
    # "live": short running commentary while working, plus alerts and a work
    # summary at the end. "quiet": only alerts and the end-of-task summary.
    narration: str = "live"
    voice: str = "af_heart"
    speed: float = 1.1
    # "interrupt": a new message cuts off the one being spoken.
    # "queue": messages are spoken in order (stale backlog is still dropped).
    mode: str = "queue"
    # Which agents to listen to.
    claude: bool = True
    codex: bool = True
    # Speak only the final answer of each turn (Codex marks these; for Claude
    # this means the last text before the turn ends) instead of every update.
    final_only: bool = False
    # With speak=all, longer messages are cut at a sentence boundary near this
    # many characters. (Agent-written voice lines may run up to 1200.)
    max_chars: int = 400
    muted: bool = False
    # Global shortcut that stops the speech playing right now ("" disables it).
    # Examples: shift+backspace, ctrl+alt+x, ctrl+shift+space, f9.
    hotkey: str = "shift+backspace"

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            known = {f.name for f in fields(cls)}
            for key, value in data.items():
                if key in known:
                    setattr(cfg, key, value)
        return cfg

    def save(self) -> None:
        HOME.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def set(self, key: str, raw: str) -> None:
        field = next((f for f in fields(self) if f.name == key), None)
        if field is None:
            raise KeyError(f"unknown setting '{key}' (valid: {', '.join(f.name for f in fields(self))})")
        current = getattr(self, key)
        if isinstance(current, bool):
            value = raw.strip().lower() in ("1", "true", "yes", "on")
        elif isinstance(current, int):
            value = int(raw)
        elif isinstance(current, float):
            value = float(raw)
        else:
            value = raw
        setattr(self, key, value)
