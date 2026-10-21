"""Teach the agents to write their own spoken lines.

Instead of reading every message aloud, agent-voice asks Claude Code and Codex
(through their global instruction files) to add a short line starting with
VOICE_MARK whenever something is worth saying out loud, and speaks only those.
The instructions live between BEGIN/END markers so they can be updated or
removed without touching the rest of the user's file.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

VOICE_MARK = "🔊"

BEGIN = "<!-- agent-voice:begin -->"
END = "<!-- agent-voice:end -->"

TEXT = f"""\
## Voice updates (agent-voice)

The user hears your work through text-to-speech while looking away from the
screen. Only lines that start with `{VOICE_MARK} ` are spoken; everything else is
read on screen only. You decide when a voice line is worth it. Add one, on its
own line, only when the user would want to be told right away:

- you finished the task, or a major step of it (say the outcome)
- you need the user's input, approval or a decision
- you hit a blocker or error you cannot work around
- you found something important or changed the plan

Skip it for routine progress ("reading files", "running tests"): most messages
should have none. At most one per message. Keep it to one short sentence that
sounds natural spoken aloud, under 20 words, with no code, file paths, URLs,
commands or markdown.

Example: `{VOICE_MARK} The build is fixed and all tests pass.`
"""

BLOCK = f"{BEGIN}\n{TEXT}{END}\n"
_BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", re.S)


def targets() -> dict[str, Path]:
    home = Path.home()
    claude = Path(os.environ.get("CLAUDE_CONFIG_DIR", home / ".claude"))
    codex = Path(os.environ.get("CODEX_HOME", home / ".codex"))
    return {"Claude Code": claude / "CLAUDE.md", "Codex": codex / "AGENTS.md"}


def install(path: Path) -> str:
    """Add or refresh the block. Returns what happened."""
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if BEGIN in current:
        updated = _BLOCK_RE.sub(BLOCK, current, count=1)
        if updated == current:
            return "already up to date"
        path.write_text(updated, encoding="utf-8")
        return "updated"
    path.parent.mkdir(parents=True, exist_ok=True)
    sep = "" if not current else ("\n" if current.endswith("\n") else "\n\n")
    path.write_text(current + sep + BLOCK, encoding="utf-8")
    return "added"


def remove(path: Path) -> bool:
    if not path.exists():
        return False
    current = path.read_text(encoding="utf-8")
    if BEGIN not in current:
        return False
    updated = _BLOCK_RE.sub("", current).rstrip("\n")
    if updated:
        path.write_text(updated + "\n", encoding="utf-8")
    else:
        path.unlink()  # the file only ever held our block
    return True


def installed(path: Path) -> bool:
    return path.exists() and BEGIN in path.read_text(encoding="utf-8")


_VOICE_LINE = re.compile(r"^[\s>*_`-]*" + VOICE_MARK + r"️?[\s:*_]*(.+?)[\s*_`]*$", re.M)


def voice_lines(text: str) -> str:
    """The text of every voice line in a message, joined; "" if there are none."""
    return " ".join(m.group(1).strip() for m in _VOICE_LINE.finditer(text))
