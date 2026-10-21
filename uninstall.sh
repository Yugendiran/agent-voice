#!/usr/bin/env bash
# Removes agent-voice (keeps pyenv and its Python, which other projects may use).
APP_HOME="${AGENT_VOICE_HOME:-$HOME/.agent-voice}"
CLI="$APP_HOME/venv/bin/agent-voice"
if [ -x "$CLI" ]; then
  "$CLI" stop
  "$CLI" autostart off
fi
rm -f "$HOME/.local/bin/agent-voice"
rm -rf "$APP_HOME"
echo "agent-voice removed."
