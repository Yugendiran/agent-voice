# agent-voice

Hear what **Claude Code** and **Codex** say while they work.

Coding agents write a lot as they go, and hearing all of it is too much. So
agent-voice lets **the agent decide what's worth saying**. It teaches Claude
Code and Codex to write spoken lines, starting with 🔊, like a developer
talking you through their work:

```text
🔊 Opening the shop file to look at the cart total and tax code.
🔊 Found three bugs: quantity is ignored, rounding drops cents, and tax divides by ten.
   ...edits, test runs, diffs (shown on screen, not spoken)...
🔊 I fixed the cart total and the tax calculation. The total now multiplies each
   price by its quantity and keeps two decimal places, and the tax now treats
   eighteen as eighteen percent. My quick checks all passed. The tax result still
   isn't rounded, so tell me if you want it rounded to two decimals too.
```

That's **live narration** while it works, **alerts** when it needs you or is
blocked, and a **work summary** at the end: what was done, how it was checked,
and what's left. agent-voice speaks only those lines, with a small neural voice
that runs entirely on your machine.

- The agent picks the moments. Prefer only alerts and the summary? `agent-voice config narration quiet`
  (or `speak all` to hear every message in full)
- Never reads tool calls, command output, code or diffs
- Turns screen-only text into speech-friendly text: code blocks are skipped, URLs become "a link",
  paths become "a file path", IPs/hashes/UUIDs are named instead of spelled out
- Local and offline: [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) (~120 MB, CPU, ~3x faster than real time),
  or the built-in OS voice with no download at all
- Works with Claude Code (CLI, VS Code, desktop) and Codex (CLI, VS Code) at the same time
- Lines play in order and stale ones are dropped, so it never falls behind
- Press Shift+Backspace anywhere to stop the current speech (configurable)

## Install

One line, nothing to download first.

**Windows** (PowerShell):

```powershell
irm https://raw.githubusercontent.com/Yugendiran/agent-voice/main/install.ps1 | iex
```

**macOS / Linux**:

```bash
curl -fsSL https://raw.githubusercontent.com/Yugendiran/agent-voice/main/install.sh | bash
```

Or from a clone: double-click `install.cmd` on Windows, or run `./install.sh`.
To update later, run the same command again: it reuses what's already installed.

The installer:

1. installs [pyenv](https://github.com/pyenv/pyenv) ([pyenv-win](https://github.com/pyenv-win/pyenv-win) on Windows) if you don't have it,
   and the Python version in `.python-version` through it;
2. creates a private virtualenv in `~/.agent-voice/venv` (nothing touches your other Pythons);
3. downloads the voice model to `~/.agent-voice/models`;
4. adds the `agent-voice` command to your PATH;
5. adds a short "voice updates" section to `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`
   (between `agent-voice:begin`/`end` markers; your own content is kept);
6. starts agent-voice now and at every login. To skip this, run the installer from a clone with
   `-NoAutostart` (Windows) / `--no-autostart`, or turn it off later with `agent-voice autostart off`.

That's it. Start a **new** Claude Code or Codex session and you'll hear it when it has something to tell you.

## Use

```text
agent-voice status          is it running?
agent-voice start | stop | restart
agent-voice mute | unmute   (toggle flips it)
agent-voice skip            cut off the current sentence
                            (or press Shift+Backspace anywhere, see `hotkey` below)
agent-voice say "hello"     test the voice
agent-voice voices          list voices
agent-voice config          show settings
agent-voice config KEY VAL  change a setting (applies immediately)
agent-voice instructions on|off   add/remove the voice-line instructions for the agents
agent-voice autostart on|off
agent-voice log             recent log lines
agent-voice run             run in the foreground with console logging
```

### Settings

| key          | default     | meaning |
|--------------|-------------|---------|
| `speak`      | `marked`    | `marked`: only the 🔊 lines the agent chooses to write. `all`: every message |
| `narration` | `live`      | `live`: running commentary + alerts + end-of-task summary. `quiet`: alerts + summary only |
| `engine`     | `kokoro`    | `kokoro` (neural, local) or `system` (Windows SAPI / macOS `say` / espeak-ng) |
| `voice`      | `af_heart`  | Kokoro voice; `a`=American, `b`=British, then `f`/`m`. Try `am_michael`, `bf_emma`, `bm_george` |
| `speed`      | `1.1`       | speaking rate |
| `mode`       | `queue`     | `queue`: lines play in order (older backlog is dropped). `interrupt`: a new line cuts off the current one |
| `final_only` | `false`     | only speak each turn's final message, not the running commentary |
| `claude`     | `true`      | narrate Claude Code |
| `codex`      | `true`      | narrate Codex |
| `max_chars`  | `400`       | with `speak all`, long messages are trimmed to their first sentences |
| `muted`      | `false`     | same as `agent-voice mute` |
| `hotkey`     | `shift+backspace` | global shortcut that stops the speech playing right now; e.g. `ctrl+alt+x`, `f9`; `off` disables it |

Settings live in `~/.agent-voice/config.json`.

### Stop shortcut

Press the shortcut in any window to stop the current speech (anything queued is dropped too).
It only acts while something is being spoken. The key press still reaches the focused app,
so if Shift+Backspace deletes a character in your prompt, pick another combo:

```text
agent-voice config hotkey ctrl+alt+x
```

Names: `ctrl`, `alt` (`option`), `shift`, `win`/`cmd`, letters, digits, `f1`-`f20`, `space`,
`backspace`, `esc`, `enter`, `tab`, ... joined with `+`.
On macOS, allow your terminal (or Python) under *System Settings > Privacy & Security > Accessibility*.
On Linux it needs X11; global shortcuts are not available under Wayland.

## How it works

`agent-voice instructions on` (run by the installer) adds a "Voice updates"
section to the agents' global instructions (`~/.claude/CLAUDE.md`,
`~/.codex/AGENTS.md`), so the agent itself decides when to speak. In short:

> Only lines that start with `🔊 ` are spoken.
> **Live narration:** when you start a step, form a hypothesis, find a cause or see tests
> pass or fail, say it in one short first-person sentence. A few lines per task, not every tool call.
> **Quick alerts:** one sentence when you need input or approval, or are blocked.
> **Work summary:** at the end of a task, 2-4 sentences: what you did and why, how you
> checked it, and what's left or what you need from the user.
> Write for the ear: no code, paths, URLs or markdown.

`agent-voice config narration quiet` drops the live narration (alerts and summary
only) and rewrites the instructions; `live` brings it back. To change the wording,
edit `src/agent_voice/instructions.py` and rerun `agent-voice instructions on`.
Already-open agent sessions keep the old instructions until restarted.

Both agents already write every session to disk as JSON lines:

| agent       | transcript                                         | what is spoken |
|-------------|----------------------------------------------------|----------------|
| Claude Code | `~/.claude/projects/<project>/<session>.jsonl`     | `assistant` entries' `text` blocks (not `tool_use`, not `thinking`, not subagents) |
| Codex       | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`     | `response_item` messages with `role: assistant` (`phase: commentary` / `final_answer`) |

agent-voice is a small background process that tails the transcripts that are
being written to, picks out the 🔊 lines (or whole messages with `speak all`),
cleans them for speech (`src/agent_voice/cleaner.py`), and speaks them. No hooks
are involved, so it never slows the agent down. History that existed before it
started is never read out.

`CLAUDE_CONFIG_DIR` and `CODEX_HOME` are respected if you've moved those folders.
A localhost port (`47821`, override with `AGENT_VOICE_PORT`) is used for the
`mute`/`stop`/... commands and to make sure only one copy runs.

## Uninstall

`uninstall.ps1` (Windows) or `./uninstall.sh`. pyenv and its Python are left in
place since other projects may use them.

## Develop

```bash
~/.agent-voice/venv/Scripts/python -m pip install -e ".[dev]"   # bin/ on macOS/Linux
~/.agent-voice/venv/Scripts/python -m pytest
agent-voice run   # foreground, logs to the console
```
