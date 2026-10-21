import json
import time

from agent_voice.sources import Source, parse_claude, parse_codex
from agent_voice.watcher import Watcher


def claude_line(text=None, tool=None, stop="tool_use", uuid="u1", sidechain=False):
    content = []
    if text is not None:
        content.append({"type": "text", "text": text})
    if tool is not None:
        content.append({"type": "tool_use", "id": "t", "name": "Bash", "input": {"command": tool}})
    return {
        "type": "assistant",
        "uuid": uuid,
        "isSidechain": sidechain,
        "message": {"id": "m", "role": "assistant", "stop_reason": stop, "content": content},
    }


def codex_line(text, phase="commentary", role="assistant", id="msg_1"):
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "id": id,
            "role": role,
            "phase": phase,
            "content": [{"type": "output_text", "text": text}],
        },
    }


def test_claude_text_block():
    u = parse_claude(claude_line("Checking the network."))
    assert u.agent == "claude" and u.text == "Checking the network." and not u.final


def test_claude_final_and_tool_use_and_sidechain():
    assert parse_claude(claude_line("Done.", stop="end_turn")).final
    assert parse_claude(claude_line(tool="ls")) is None
    assert parse_claude(claude_line("subagent", sidechain=True)) is None
    assert parse_claude({"type": "user", "message": {"content": "hi"}}) is None
    thinking = claude_line()
    thinking["message"]["content"] = [{"type": "thinking", "thinking": "secret"}]
    assert parse_claude(thinking) is None


def test_codex_messages():
    u = parse_codex(codex_line("I'll inspect the CSVs first."))
    assert u.agent == "codex" and not u.final
    assert parse_codex(codex_line("All done.", phase="final_answer")).final
    assert parse_codex(codex_line("user text", role="user")) is None
    assert parse_codex({"type": "response_item", "payload": {"type": "reasoning"}}) is None
    assert parse_codex({"type": "event_msg", "payload": {"type": "item_completed"}}) is None


def _append(path, *entries, newline=True):
    with path.open("a", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + ("\n" if newline else ""))


def test_watcher_skips_history_reads_new_lines_and_partial_writes(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    old = project / "old.jsonl"
    _append(old, claude_line("history, never spoken", uuid="h"))

    w = Watcher([Source("claude", tmp_path, "*/*.jsonl", parse_claude)])
    w._scan()
    assert w.poll() == []

    _append(old, claude_line("first new message", uuid="a"))
    assert [u.text for u in w.poll()] == ["first new message"]

    # A line written in two pieces is only parsed once it is complete.
    line = json.dumps(claude_line("split line", uuid="b"))
    with old.open("a", encoding="utf-8") as fh:
        fh.write(line[:20])
    assert w.poll() == []
    with old.open("a", encoding="utf-8") as fh:
        fh.write(line[20:] + "\n")
    assert [u.text for u in w.poll()] == ["split line"]


def test_watcher_reads_new_session_files_from_start(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    w = Watcher([Source("claude", tmp_path, "*/*.jsonl", parse_claude)])
    w._scan()

    new = project / "new.jsonl"
    _append(new, claude_line("hello from a new session", uuid="n"))
    w._last_scan = time.time() - 10  # force a rescan
    assert [u.text for u in w.poll()] == ["hello from a new session"]
    # Duplicate ids are not repeated.
    _append(new, claude_line("hello from a new session", uuid="n"))
    assert w.poll() == []
