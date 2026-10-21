# agent-voice

Hear what **Claude Code** and **Codex** say while they work.

Coding agents narrate as they go ("The Gradle download redirects to GitHub's
servers, so I'll test those next..."). agent-voice reads those updates out
loud with a small neural voice that runs entirely on your machine, so you can
look away from the terminal and still follow along.

- Speaks only the agent's own words, never tool calls, command output, code or diffs
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
5. starts agent-voice now and at every login. To skip this, run the installer from a clone with
   `-NoAutostart` (Windows) / `--no-autostart`, or turn it off later with `agent-voice autostart off`.

That's it. Start Claude Code or Codex and you'll hear it.

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
agent-voice autostart on|off
agent-voice log             recent log lines
agent-voice run             run in the foreground with console logging
```

### Settings

| key          | default     | meaning |
|--------------|-------------|---------|
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

Both agents already write every session to disk as JSON lines:

| agent       | transcript                                         | what is spoken |
|-------------|----------------------------------------------------|----------------|
| Claude Code | `~/.claude/projects/<project>/<session>.jsonl`     | `assistant` entries' `text` blocks (not `tool_use`, not `thinking`, not subagents) |
| Codex       | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`     | `response_item` messages with `role: assistant` (`phase: commentary` / `final_answer`) |

agent-voice is a small background process that tails the transcripts that are
being written to, cleans each new message for speech
(`src/agent_voice/cleaner.py`), and speaks it. No hooks or agent configuration
are needed, and it never slows the agent down. History that existed before it
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
