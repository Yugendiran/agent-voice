"""Tails agent transcript files and yields new assistant messages."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from .sources import Source, Utterance, parse_line

log = logging.getLogger("agent_voice")

POLL_SECONDS = 0.25
RESCAN_SECONDS = 2.0
# Only files written to recently are tailed; old sessions are ignored.
ACTIVE_WINDOW_SECONDS = 30 * 60


@dataclass
class _Tail:
    source: Source
    offset: int
    mtime: float = 0.0
    partial: bytes = b""


@dataclass
class Watcher:
    sources: list[Source]
    _tails: dict[Path, _Tail] = field(default_factory=dict)
    _seen: dict[str, None] = field(default_factory=dict)
    # Byte offsets of files that are not being tailed right now. At startup every
    # existing file is recorded at its current size, so old history is never
    # spoken; files created later are unknown and read from the start.
    _offsets: dict[Path, int] = field(default_factory=dict)
    _last_scan: float = 0.0

    def _scan(self) -> None:
        now = time.time()
        first = not self._last_scan
        for source in self.sources:
            for path in source.files():
                if path in self._tails:
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                if first:
                    self._offsets[path] = stat.st_size
                if now - stat.st_mtime > ACTIVE_WINDOW_SECONDS:
                    continue
                offset = self._offsets.pop(path, 0)
                self._tails[path] = _Tail(source, offset, stat.st_mtime)
                log.debug("watching %s from byte %d", path, offset)
        self._last_scan = now

    def _read_new(self, path: Path, tail: _Tail) -> Iterator[Utterance]:
        try:
            stat = path.stat()
        except OSError:
            del self._tails[path]
            return
        if stat.st_size < tail.offset:  # truncated / rewritten
            tail.offset, tail.partial = 0, b""
        if stat.st_size == tail.offset:
            if time.time() - stat.st_mtime > ACTIVE_WINDOW_SECONDS:
                self._offsets[path] = tail.offset
                del self._tails[path]
            return
        with path.open("rb") as fh:
            fh.seek(tail.offset)
            data = fh.read()
        tail.offset += len(data)
        tail.mtime = stat.st_mtime
        data = tail.partial + data
        lines = data.split(b"\n")
        tail.partial = lines.pop()  # incomplete last line, finished on a later read
        for raw in lines:
            utterance = parse_line(tail.source, raw.decode("utf-8", errors="replace"))
            if utterance is None or utterance.key in self._seen:
                continue
            self._seen[utterance.key] = None
            if len(self._seen) > 5000:
                for old in list(self._seen)[:1000]:
                    del self._seen[old]
            yield utterance

    def poll(self) -> list[Utterance]:
        if time.time() - self._last_scan >= RESCAN_SECONDS:
            self._scan()
        out: list[Utterance] = []
        for path, tail in list(self._tails.items()):
            out.extend(self._read_new(path, tail))
        return out

    def run(self, stop) -> Iterator[Utterance]:
        """Yield utterances until ``stop()`` returns True."""
        self._scan()
        while not stop():
            yield from self.poll()
            time.sleep(POLL_SECONDS)
