"""Turns agent markdown into something that sounds natural when read aloud.

Agents write for a screen: code blocks, file paths, commands, URLs, tables.
None of that is pleasant to hear, so it is dropped or replaced with a short
spoken stand-in, and long messages are cut to their first few sentences.
"""

from __future__ import annotations

import re
import unicodedata

_CODE_FENCE = re.compile(r"```.*?(```|$)", re.S)
_TABLE_ROW = re.compile(r"^\s*\|.*$", re.M)
_HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_URL = re.compile(r"\b(?:https?|ftp)://\S+|\bwww\.\S+", re.I)
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_WIN_PATH = re.compile(r"(?<![\w])(?:[A-Za-z]:)?(?:\\[^\s\\:*?\"<>|,;)]+){2,}\\?")
_POSIX_PATH = re.compile(r"(?<![\w.])(?:~|\.{1,2})?(?:/[\w.@+-]+){2,}/?")
_IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b")
_HEX = re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{12,}\b", re.I)
_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
_FILE_REF = re.compile(r"\b[\w-]+\.(?:py|ts|tsx|js|jsx|json|md|toml|ya?ml|kt|java|go|rs|cs|cpp|h|sh|ps1|gradle|xml|html|css|lock|txt|zip|jsonl)(?::\d+(?::\d+)?)?\b")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.M)
_BULLET = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+", re.M)
_EMPHASIS = re.compile(r"(\*\*|__|\*|_|~~)(?=\S)(.+?)(?<=\S)\1")
_HRULE = re.compile(r"^\s*([-*_])\1{2,}\s*$", re.M)
_ARROWS = {"→": " to ", "←": " from ", "⇒": " so ", "—": ", ", "–": ", ", "…": "..."}
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _inline_code(match: re.Match) -> str:
    code = match.group(1).strip()
    # Short identifiers read fine ("the `pyenv` command"); anything that looks
    # like a command, expression or path does not.
    if len(code) <= 24 and re.fullmatch(r"[\w.@+-]+(?: [\w.@+-]+)?", code) and "/" not in code:
        return code
    if " " not in code:
        if _URL.fullmatch(code):
            return "a link"
        if _WIN_PATH.fullmatch(code) or _POSIX_PATH.fullmatch(code) or re.fullmatch(r"[A-Za-z]:\\\S*", code):
            return "a file path"
    return "that"


def clean(text: str, max_chars: int = 400) -> str:
    """Return speakable text, or "" when nothing worth saying is left."""
    text = _CODE_FENCE.sub(" ", text)
    text = _TABLE_ROW.sub(" ", text)
    text = _HRULE.sub(" ", text)
    text = _HTML_TAG.sub(" ", text)
    text = _MD_IMAGE.sub(" ", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _INLINE_CODE.sub(_inline_code, text)
    text = _URL.sub("a link", text)
    text = _UUID.sub("an ID", text)
    text = _WIN_PATH.sub("a file path", text)
    text = _POSIX_PATH.sub("a file path", text)
    text = _IPV4.sub("an IP address", text)
    text = _HEX.sub("a hash", text)
    text = _FILE_REF.sub(lambda m: m.group(0).split(":")[0], text)
    text = _HEADING.sub("", text)
    text = _BULLET.sub("", text)
    text = _EMPHASIS.sub(r"\2", text)
    for symbol, spoken in _ARROWS.items():
        text = text.replace(symbol, spoken)
    # Emoji, bullets, box drawing, check marks... (Unicode "So"/"Sk" symbols).
    text = "".join(" " if unicodedata.category(c) in ("So", "Sk") else c for c in text)

    # Each remaining line becomes its own sentence.
    lines = [ln.strip() for ln in text.splitlines()]
    sentences = []
    for ln in lines:
        if not ln:
            continue
        if ln[-1] not in ".!?:;,":
            ln += "."
        sentences.append(ln)
    text = " ".join(sentences)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    text = re.sub(r"([.,!?;:])\1+", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip()

    if not re.search(r"[A-Za-z]{2,}", text):
        return ""
    return _truncate(text, max_chars)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    out = ""
    for sentence in _SENTENCE_END.split(text):
        if out and len(out) + len(sentence) + 1 > max_chars:
            break
        out = f"{out} {sentence}".strip()
    if len(out) > max_chars:  # a single very long sentence
        out = out[:max_chars].rsplit(" ", 1)[0] + "."
    return out
