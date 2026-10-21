"""Teach the agents to write their own spoken lines.

Instead of reading every message aloud, agent-voice asks Claude Code and Codex
(through their global instruction files) to add lines starting with VOICE_MARK
whenever something is worth saying out loud (live narration, alerts and an
end-of-task work summary), and speaks only those.
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

NARRATION_STYLES = ("live", "quiet")

_INTRO = f"""## Voice updates (agent-voice)

The user hears your work through text-to-speech while looking away from the
screen. Only lines that start with `{VOICE_MARK} ` are spoken; everything else is
read on screen only. Write each voice line as a single paragraph on one line,
at most one per message.
"""

_LIVE = f"""
**Live narration (while you work).** Talk the user through your work the way a
developer pairing with them would think out loud. Add a short voice line when
you start a new step, form a hypothesis, find the cause of a problem, see a
test fail or pass, or change approach. One sentence, under 15 words, first
person, present tense. Don't narrate every tool call and don't repeat yourself;
a few lines per task is right.

Examples: `{VOICE_MARK} Looking at how the join button talks to the server.`
`{VOICE_MARK} Found it, the button still calls the old session endpoint.`
`{VOICE_MARK} Two tests fail now, checking why.`
"""

_QUIET = """
**No running commentary.** Skip voice lines for routine progress ("reading
files", "running tests"): most messages should have none.
"""

_REST = f"""
**Quick alerts.** One short sentence whenever the user would want to know right
away: you need their input or approval, or you hit a blocker you cannot work
around.

**Work summary (end of a task).** When you finish a task or a major part of
it, end your message with a spoken summary: 2 to 4 sentences (about 40 to 80
words) telling the user, as you would tell a colleague, what you did and why,
the result and how you checked it, and what is left, any risk, or the decision
you need from them.

Write for the ear: plain sentences, no code, file paths, URLs, commands, lists
or markdown. Name things the way you'd say them ("the login screen", "the
payment service").

Examples: `{VOICE_MARK} I need your approval before I delete the old migration files.`
`{VOICE_MARK} I fixed the join class flow. The join button was calling the old session endpoint, so I switched it to the new one and added a retry when the class hasn't started yet. All twelve tests pass and I checked it in the app. Nothing is committed yet, so tell me if you want me to commit it.`
"""


def text(narration: str = "live") -> str:
    if narration not in NARRATION_STYLES:
        raise ValueError(f"narration must be one of {', '.join(NARRATION_STYLES)}")
    return _INTRO + (_LIVE if narration == "live" else _QUIET) + _REST


def block(narration: str = "live") -> str:
    return f"{BEGIN}\n{text(narration)}{END}\n"


_BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", re.S)


def targets() -> dict[str, Path]:
    home = Path.home()
    claude = Path(os.environ.get("CLAUDE_CONFIG_DIR", home / ".claude"))
    codex = Path(os.environ.get("CODEX_HOME", home / ".codex"))
    return {"Claude Code": claude / "CLAUDE.md", "Codex": codex / "AGENTS.md"}


def install(path: Path, narration: str = "live") -> str:
    """Add or refresh the block. Returns what happened."""
    new_block = block(narration)
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if BEGIN in current:
        updated = _BLOCK_RE.sub(lambda _: new_block, current, count=1)
        if updated == current:
            return "already up to date"
        path.write_text(updated, encoding="utf-8")
        return "updated"
    path.parent.mkdir(parents=True, exist_ok=True)
    sep = "" if not current else ("\n" if current.endswith("\n") else "\n\n")
    path.write_text(current + sep + new_block, encoding="utf-8")
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
