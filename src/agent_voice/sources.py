"""Where each agent writes its transcript, and how to pull spoken text out of it."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional


@dataclass(frozen=True)
class Utterance:
    agent: str  # "claude" or "codex"
    text: str
    final: bool  # last message of the agent's turn
    key: str  # unique id, used to avoid speaking the same text twice


@dataclass(frozen=True)
class Source:
    name: str
    root: Path
    # Glob relative to root. Kept shallow for Claude so subagent transcripts
    # (<session>/subagents/*.jsonl) are not narrated.
    pattern: str
    parse: Callable[[dict], Optional[Utterance]]

    def files(self) -> Iterable[Path]:
        if not self.root.is_dir():
            return []
        if self.name == "codex":
            # sessions/YYYY/MM/DD/rollout-*.jsonl: only look at the newest days.
            days = sorted(self.root.glob("*/*/*"), reverse=True)[:2]
            return [f for day in days for f in day.glob(self.pattern)]
        return self.root.glob(self.pattern)


def parse_claude(entry: dict) -> Optional[Utterance]:
    # Each content block of an assistant message is written as its own line:
    # {"type":"assistant","isSidechain":false,"message":{"role":"assistant",
    #   "stop_reason":"tool_use"|"end_turn",...,"content":[{"type":"text","text":"..."}]}}
    if entry.get("type") != "assistant" or entry.get("isSidechain"):
        return None
    message = entry.get("message") or {}
    texts = [
        block.get("text", "")
        for block in message.get("content") or []
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    text = "\n".join(t for t in texts if t.strip())
    if not text:
        return None
    return Utterance(
        agent="claude",
        text=text,
        final=message.get("stop_reason") == "end_turn",
        key=entry.get("uuid") or f"{message.get('id')}:{hash(text)}",
    )


def parse_codex(entry: dict) -> Optional[Utterance]:
    # {"type":"response_item","payload":{"type":"message","role":"assistant",
    #   "phase":"commentary"|"final_answer","content":[{"type":"output_text","text":"..."}]}}
    if entry.get("type") != "response_item":
        return None
    payload = entry.get("payload") or {}
    if payload.get("type") != "message" or payload.get("role") != "assistant":
        return None
    texts = [
        block.get("text", "")
        for block in payload.get("content") or []
        if isinstance(block, dict) and block.get("type") in ("output_text", "text")
    ]
    text = "\n".join(t for t in texts if t.strip())
    if not text:
        return None
    return Utterance(
        agent="codex",
        text=text,
        final=payload.get("phase") == "final_answer",
        key=payload.get("id") or f"{entry.get('timestamp')}:{hash(text)}",
    )


def default_sources() -> list[Source]:
    home = Path.home()
    claude_root = Path(os.environ.get("CLAUDE_CONFIG_DIR", home / ".claude")) / "projects"
    codex_root = Path(os.environ.get("CODEX_HOME", home / ".codex")) / "sessions"
    return [
        Source("claude", claude_root, "*/*.jsonl", parse_claude),
        Source("codex", codex_root, "*.jsonl", parse_codex),
    ]


def parse_line(source: Source, line: str) -> Optional[Utterance]:
    line = line.strip()
    if not line:
        return None
    try:
        entry = json.loads(line)
    except ValueError:
        return None
    if not isinstance(entry, dict):
        return None
    return source.parse(entry)
