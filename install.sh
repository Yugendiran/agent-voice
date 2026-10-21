#!/usr/bin/env bash
# Installs agent-voice on macOS or Linux.
#
#   ./install.sh                 install, start now and at login
#   ./install.sh --no-autostart  install only
#
# Uses pyenv for Python (installs pyenv if it is missing), a private virtualenv
# in ~/.agent-voice/venv, and puts `agent-voice` in ~/.local/bin.
set -euo pipefail

AUTOSTART=1
for arg in "$@"; do
  case "$arg" in
    --no-autostart) AUTOSTART=0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
ok()   { printf '    \033[32m%s\033[0m\n' "$1"; }

REPO="Yugendiran/agent-voice"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
if [ ! -f "$HERE/pyproject.toml" ] && [ -z "${AGENT_VOICE_SOURCE:-}" ]; then
  # Not run from a checkout (e.g. `curl .../install.sh | bash`): fetch the
  # latest source from GitHub. No git needed.
  step "Downloading agent-voice from github.com/$REPO"
  TMP="$(mktemp -d)"
  curl -fsSL "https://github.com/$REPO/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP"
  HERE="$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -n1)"
fi
SOURCE="${AGENT_VOICE_SOURCE:-$HERE}"
PY_VERSION="$(head -n1 "$HERE/.python-version" 2>/dev/null || echo 3.12.10)"
APP_HOME="${AGENT_VOICE_HOME:-$HOME/.agent-voice}"
VENV="$APP_HOME/venv"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$APP_HOME" "$BIN_DIR"

[ -x "$VENV/bin/agent-voice" ] && "$VENV/bin/agent-voice" stop >/dev/null 2>&1 || true

# ------------------------------------------------------------------ audio libs
if [ "$(uname)" = "Linux" ] && ! ldconfig -p 2>/dev/null | grep -q libportaudio; then
  step "Installing PortAudio (needed to play sound)"
  if command -v apt-get >/dev/null; then sudo apt-get install -y libportaudio2
  elif command -v dnf >/dev/null; then sudo dnf install -y portaudio
  elif command -v pacman >/dev/null; then sudo pacman -S --noconfirm portaudio
  else echo "    Please install PortAudio with your package manager." >&2; fi
fi

# ------------------------------------------------------------------ pyenv
step "Checking pyenv"
export PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"
export PATH="$PYENV_ROOT/bin:$PATH"
if ! command -v pyenv >/dev/null; then
  if [ "$(uname)" = "Darwin" ] && command -v brew >/dev/null; then
    brew install pyenv
  else
    echo "    pyenv not found, installing it to $PYENV_ROOT ..."
    echo "    (building Python needs a compiler: on Debian/Ubuntu run"
    echo "     sudo apt-get install -y build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev libffi-dev liblzma-dev)"
    curl -fsSL https://pyenv.run | bash
  fi
fi
ok "pyenv: $(command -v pyenv)"

# ------------------------------------------------------------------ Python
step "Installing Python $PY_VERSION with pyenv"
pyenv install --skip-existing "$PY_VERSION"
PYTHON="$(pyenv root)/versions/$PY_VERSION/bin/python"
ok "$("$PYTHON" --version)"

# ------------------------------------------------------------------ venv + package
step "Installing agent-voice into $VENV"
if [ -x "$VENV/bin/python" ] && [ "$("$VENV/bin/python" -c 'import platform; print(platform.python_version())')" != "$PY_VERSION" ]; then
  rm -rf "$VENV"
fi
[ -x "$VENV/bin/python" ] || "$PYTHON" -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade pip
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade "$SOURCE"
ln -sf "$VENV/bin/agent-voice" "$BIN_DIR/agent-voice"
ok "installed; command: $BIN_DIR/agent-voice"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "    Add $BIN_DIR to your PATH (e.g. in ~/.zshrc or ~/.bashrc) to run agent-voice directly." ;;
esac

# ------------------------------------------------------------------ model
step "Downloading the voice model"
"$VENV/bin/agent-voice" download

# ------------------------------------------------------------------ start
if [ "$AUTOSTART" = 1 ]; then
  step "Starting agent-voice (and at every login)"
  "$VENV/bin/agent-voice" autostart on
  "$VENV/bin/agent-voice" start
  "$VENV/bin/agent-voice" say "agent-voice is ready. I will read out what Claude Code and Codex say."
else
  "$VENV/bin/agent-voice" autostart off >/dev/null
fi

printf '\n\033[32mDone!\033[0m Try: agent-voice status | mute | unmute | voices | help\n'
