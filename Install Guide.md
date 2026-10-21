# 📥 Agent Voice: Install Guide

Everything needed to install, check, update and remove Agent Voice.
It is written for people **and** for coding agents: if you are an AI agent asked to
install Agent Voice, follow the steps in order and finish with
[Step 4](#step-4-tell-the-user-to-restart-their-agent-sessions).

**Requirements:** Windows 10/11, macOS or Linux; internet access during install
(about 150 MB is downloaded); no admin rights needed (except for Linux system packages).
Python does not need to be installed: the installer brings its own through pyenv.

---

## Step 1: Run the installer

Pick the command for your OS. It takes 1 to 5 minutes. Run it in the foreground and
**don't cancel it early**; agents should use a timeout of at least 10 minutes.

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/Yugendiran/agent-voice/main/install.ps1 | iex
```

From a clone, double-click `install.cmd` or run:

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1             # add -NoAutostart to skip start-at-login
```

### macOS

```bash
curl -fsSL https://raw.githubusercontent.com/Yugendiran/agent-voice/main/install.sh | bash
```

If Homebrew is installed it is used to install pyenv; otherwise pyenv is installed from pyenv.run.

### Linux

pyenv builds Python from source, and sound needs PortAudio. Install these first
(Debian/Ubuntu shown; this needs `sudo`):

```bash
sudo apt-get install -y build-essential libssl-dev zlib1g-dev libbz2-dev \
  libreadline-dev libsqlite3-dev libffi-dev liblzma-dev libportaudio2
```

Then:

```bash
curl -fsSL https://raw.githubusercontent.com/Yugendiran/agent-voice/main/install.sh | bash
```

From a clone: `./install.sh` (add `--no-autostart` to skip start-at-login).

> **Agents:** if a step needs `sudo` or a password, don't guess. Stop and tell the user
> exactly which command to run, then continue once they've run it.

### What the installer does

1. Installs [pyenv](https://github.com/pyenv/pyenv) ([pyenv-win](https://github.com/pyenv-win/pyenv-win)
   on Windows) if missing, then the Python version in [`.python-version`](.python-version)
2. Creates a private virtualenv in `~/.agent-voice/venv`, leaving other Pythons alone
3. Downloads the Kokoro voice model (~120 MB) to `~/.agent-voice/models`
4. Adds the `agent-voice` command to PATH (`~/.agent-voice/bin` on Windows, `~/.local/bin` elsewhere)
5. Adds a *Voice updates* section to `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`,
   between `agent-voice:begin` / `end` markers; existing content is kept
6. Starts Agent Voice now and at every login, and says a short hello

Running it again updates an existing install and reuses everything already downloaded.

## Step 2: Check it works

A terminal opened **before** the install won't have `agent-voice` on its PATH yet. Either
open a new terminal or call it by its full path:

| OS | Full path |
|---|---|
| Windows | `~/.agent-voice/venv/Scripts/agent-voice.exe` |
| macOS / Linux | `~/.agent-voice/venv/bin/agent-voice` |

```bash
agent-voice status        # expect: running (speaking, speak=marked, ...)
agent-voice say "Agent Voice is installed and ready."
agent-voice instructions  # expect: Claude Code on / Codex on
```

If `status` says it isn't running, start it with `agent-voice start`.

## Step 3: If something failed

| Symptom | Fix |
|---|---|
| `say` is silent but `status` is running | Check the audio output device and volume; `agent-voice log` shows every `speaking: …` line |
| Windows: script execution is disabled | Use `powershell -ExecutionPolicy Bypass -File install.ps1` from a clone |
| Windows: pyenv-win failed to install | See [pyenv-win install](https://github.com/pyenv-win/pyenv-win#installation), then rerun the installer |
| Linux: Python build fails | Install the build packages from [Linux](#linux), then rerun |
| Linux: no sound / PortAudio error | `sudo apt-get install -y libportaudio2` (or your distro's `portaudio`) |
| Model download failed or was cut off | `agent-voice download --force` |
| Codex: network or permission errors | Codex's sandbox blocks network by default; approve the command or run it outside the sandbox |
| `agent-voice` not found | Use the full path from Step 2, or open a new terminal |

Logs: `agent-voice log`, or the file `~/.agent-voice/agent-voice.log`.

## Step 4: Tell the user to restart their agent sessions

The voice instructions in `CLAUDE.md` / `AGENTS.md` are only read when a session
**starts**. Sessions that were already open, including the one that ran this install,
won't speak until they are restarted.

> **Agents:** finish by telling the user, in a few sentences, what was installed and
> that the check passed, then ask them to **restart Claude Code / Codex** (every open
> session) to hear the agent's voice.

---

## Optional setup

```bash
agent-voice config narration quiet       # only alerts + end-of-task summary (default: live)
agent-voice config voice am_michael      # change voice; list them with: agent-voice voices
agent-voice config hotkey ctrl+alt+x     # stop-speech shortcut (default: shift+backspace)
agent-voice autostart off                # don't start at login
```

macOS: for the stop shortcut, allow your terminal (or Python) in
*System Settings → Privacy & Security → Accessibility*. Linux: the shortcut needs X11 (not Wayland).

## Update

Run the Step 1 command again, then `agent-voice restart`.

## Uninstall

```powershell
irm https://raw.githubusercontent.com/Yugendiran/agent-voice/main/uninstall.ps1 | iex   # Windows
```

```bash
curl -fsSL https://raw.githubusercontent.com/Yugendiran/agent-voice/main/uninstall.sh | bash   # macOS / Linux
```

This removes Agent Voice, its autostart entry, PATH entry and the agent instructions.
pyenv and its Python are kept, since other projects may use them.
