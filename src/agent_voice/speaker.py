"""A background thread that speaks queued messages one at a time."""

from __future__ import annotations

import collections
import logging
import threading

log = logging.getLogger("agent_voice")

# In "queue" mode, anything older than this many pending messages is dropped:
# hearing a status update from a minute ago is worse than hearing nothing.
MAX_BACKLOG = 2


class Speaker:
    def __init__(self, engine, mode: str = "interrupt") -> None:
        self.engine = engine
        self.mode = mode
        self.muted = False
        self._pending: collections.deque[str] = collections.deque()
        self._cond = threading.Condition()
        self._cancel = threading.Event()
        self._stopped = False
        self._thread = threading.Thread(target=self._run, name="speaker", daemon=True)
        self._thread.start()

    def say(self, text: str) -> None:
        if self.muted or not text:
            return
        with self._cond:
            if self.mode == "interrupt":
                self._pending.clear()
                self._cancel.set()
            self._pending.append(text)
            while len(self._pending) > MAX_BACKLOG:
                self._pending.popleft()
            self._cond.notify()

    def skip(self) -> None:
        """Stop the current message (queued ones still play)."""
        self._cancel.set()

    def silence(self) -> None:
        """Stop the current message and drop everything queued."""
        with self._cond:
            self._pending.clear()
        self._cancel.set()

    def close(self) -> None:
        with self._cond:
            self._stopped = True
            self._pending.clear()
            self._cancel.set()
            self._cond.notify()

    def _run(self) -> None:
        while True:
            with self._cond:
                while not self._pending and not self._stopped:
                    self._cond.wait()
                if self._stopped:
                    return
                text = self._pending.popleft()
                self._cancel.clear()
            try:
                log.info("speaking: %s", text)
                self.engine.speak(text, self._cancel)
            except Exception:
                log.exception("speech failed")
