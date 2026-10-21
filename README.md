# agent-voice

Hear what **Claude Code** and **Codex** say while they work.

Coding agents narrate a lot as they go. Hearing all of it is too much, so
agent-voice lets **the agent decide what's worth saying**: it teaches Claude
Code and Codex to add a short spoken line, starting with 🔊, only when it
matters: a task is done, it needs your decision, or it's blocked.

```text
I changed add() in calc.py from a - b to a + b and ran a check: add(2, 3) == 5 ...

🔊 The add bug is fixed, and the check passed.      <- only this is spoken
```

agent-voice speaks those lines with a small neural voice that runs entirely on
your machine, so you can look away from the terminal and still know when to come back.

- The agent picks the moments; routine progress stays silent
  (or set `speak all` to hear every message)
- Never reads tool calls, command output, code or diffs
- Turns screen-only text into speech-friendly text: code blocks are skipped, URLs become "a link",
  paths become "a file path", IPs/hashes/UUIDs are named instead of spelled out
- Local and offline: [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) (~120 MB, CPU, ~3x faster than real time),
  or the built-in OS voice with no download at all
- Works with Claude Code (CLI, VS Code, desktop) and Codex (CLI, VS Code) at the same time
- New messages interrupt stale ones, so it never falls behind

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
agent-voice start | stop
agent-voice mute | unmute   (toggle flips it)
agent-voice skip            cut off the current sentence
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
| `engine`     | `kokoro`    | `kokoro` (neural, local) or `system` (Windows SAPI / macOS `say` / espeak-ng) |
| `voice`      | `af_heart`  | Kokoro voice; `a`=American, `b`=British, then `f`/`m`. Try `am_michael`, `bf_emma`, `bm_george` |
| `speed`      | `1.1`       | speaking rate |
| `mode`       | `interrupt` | `interrupt`: a new message cuts off the current one. `queue`: finish, then speak the next |
| `final_only` | `false`     | only speak each turn's final message, not the running commentary |
| `claude`     | `true`      | narrate Claude Code |
| `codex`      | `true`      | narrate Codex |
| `max_chars`  | `400`       | long messages are trimmed to their first sentences |
| `muted`      | `false`     | same as `agent-voice mute` |

Settings live in `~/.agent-voice/config.json`.

## How it works

`agent-voice instructions on` (run by the installer) adds this to the agents'
global instructions, so the agent itself decides when to speak:

> Only lines that start with `🔊 ` are spoken. Add one only when the user would
> want to be told right away: the task or a major step is done, you need their
> input, you're blocked, or you found something important. Skip it for routine
> progress. One short sentence, no code, paths or URLs.

Edit the wording in `src/agent_voice/instructions.py` and rerun
`agent-voice instructions on` to update it.

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
