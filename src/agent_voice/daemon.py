"""The long-running narrator: watch transcripts, clean text, speak it."""

from __future__ import annotations

import logging
import socket
import socketserver
import threading

from .cleaner import clean
from .config import CONTROL_PORT, Config
from .hotkey import Hotkey
from .instructions import voice_lines
from .sources import Utterance, default_sources
from .speaker import Speaker
from .tts import make_engine
from .watcher import Watcher

log = logging.getLogger("agent_voice")


class AlreadyRunning(RuntimeError):
    pass


class Narrator:
    def __init__(self) -> None:
        self.cfg = Config.load()
        self.engine = None
        self._stop = threading.Event()
        # Bind the control port first: it is the single-instance lock, and a
        # second copy should exit before spending seconds loading the model.
        self._server = _start_control_server(self)
        self.engine = make_engine(self.cfg)
        self.speaker = Speaker(self.engine, self.cfg.mode)
        self.speaker.muted = self.cfg.muted
        self.hotkey = Hotkey(self.cfg.hotkey, self.on_hotkey)

    def on_hotkey(self) -> None:
        # Only act mid-speech, so the shortcut is harmless the rest of the time.
        if self.speaker.speaking:
            log.info("stopped by shortcut")
            self.speaker.silence()

    # -- control commands -------------------------------------------------
    def handle(self, command: str) -> str:
        cmd, _, arg = command.strip().partition(" ")
        if self.engine is None:
            return "starting"
        if cmd == "status":
            state = "muted" if self.speaker.muted else "speaking"
            shortcut = self.cfg.hotkey if self.hotkey.active else "off"
            return (
                f"running ({state}, speak={self.cfg.speak}, engine={self.engine.name}, "
                f"voice={self.cfg.voice}, mode={self.cfg.mode}, stop shortcut={shortcut})"
            )
        if cmd in ("mute", "unmute", "toggle"):
            muted = {"mute": True, "unmute": False}.get(cmd, not self.speaker.muted)
            self.speaker.muted = self.cfg.muted = muted
            if muted:
                self.speaker.silence()
            self.cfg.save()
            return "muted" if muted else "unmuted"
        if cmd == "skip":
            self.speaker.skip()
            return "skipped"
        if cmd == "say":
            self.speaker.say(clean(arg, self.cfg.max_chars) or arg)
            return "ok"
        if cmd == "reload":
            self.reload()
            return "reloaded"
        if cmd == "stop":
            self._stop.set()
            return "stopping"
        return f"unknown command: {cmd}"

    def reload(self) -> None:
        new = Config.load()
        engine_changed = new.engine != self.cfg.engine
        hotkey_changed = new.hotkey != self.cfg.hotkey
        # Engines hold a reference to self.cfg, so update it in place.
        self.cfg.__dict__.update(new.__dict__)
        if engine_changed:
            self.speaker.silence()
            self.engine = self.speaker.engine = make_engine(self.cfg)
        self.speaker.mode = self.cfg.mode
        self.speaker.muted = self.cfg.muted
        if hotkey_changed:
            self.hotkey.stop()
            self.hotkey = Hotkey(self.cfg.hotkey, self.on_hotkey)

    # -- main loop ---------------------------------------------------------
    def wants(self, u: Utterance) -> bool:
        if not getattr(self.cfg, u.agent, True):
            return False
        if self.cfg.final_only and not u.final:
            return False
        return True

    def speech_for(self, u: Utterance) -> str:
        """What to say for a message, or "" to stay silent."""
        if not self.wants(u):
            return ""
        text = voice_lines(u.text) if self.cfg.speak == "marked" else u.text
        return clean(text, self.cfg.max_chars) if text else ""

    def run(self) -> None:
        server = self._server
        log.info("agent-voice running (engine=%s, port=%d)", self.engine.name, CONTROL_PORT)
        try:
            for utterance in Watcher(default_sources()).run(self._stop.is_set):
                text = self.speech_for(utterance)
                if text:
                    self.speaker.say(text)
        except KeyboardInterrupt:
            pass
        finally:
            server.shutdown()
            server.server_close()
            self.hotkey.stop()
            self.speaker.close()
            log.info("agent-voice stopped")


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        line = self.rfile.readline().decode("utf-8", errors="replace")
        reply = self.server.narrator.handle(line)  # type: ignore[attr-defined]
        self.wfile.write((reply + "\n").encode("utf-8"))


class _Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = False


def _start_control_server(narrator: Narrator) -> _Server:
    try:
        server = _Server(("127.0.0.1", CONTROL_PORT), _Handler)
    except OSError as exc:
        raise AlreadyRunning(f"port {CONTROL_PORT} is in use; is agent-voice already running?") from exc
    server.narrator = narrator  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, name="control", daemon=True).start()
    return server


def send(command: str, timeout: float = 3.0) -> str | None:
    """Send a command to a running daemon. Returns None if none is running."""
    try:
        with socket.create_connection(("127.0.0.1", CONTROL_PORT), timeout=timeout) as sock:
            sock.sendall((command + "\n").encode("utf-8"))
            return sock.makefile("r", encoding="utf-8").readline().strip()
    except OSError:
        return None
