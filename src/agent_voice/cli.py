"""Command line interface: ``agent-voice <command>``."""

from __future__ import annotations

import argparse
import logging
import platform
import subprocess
import sys
import threading
import time

from . import autostart, instructions
from .cleaner import clean
from .config import CONFIG_PATH, HOME, LOG_PATH, Config
from .daemon import AlreadyRunning, Narrator, send

USAGE = """\
agent-voice: hear what Claude Code and Codex say while they work.

commands:
  start             start narrating in the background
  stop              stop the background narrator
  restart           stop and start again (e.g. after updating agent-voice)
  status            show whether it is running
  mute | unmute     silence / resume speech (toggle flips it)
  skip              stop the message being spoken right now
                    (or press the shortcut, shift+backspace by default:
                     agent-voice config hotkey ctrl+alt+x  /  ... hotkey off)
  say TEXT          speak some text (useful to test your voice settings)
  run               run in the foreground, logging to the console (Ctrl+C stops)
  config            show settings;  config KEY VALUE  changes one
  voices            list available voices
  instructions on|off
                    teach Claude Code and Codex to write short 🔊 voice lines
                    (adds a block to ~/.claude/CLAUDE.md and ~/.codex/AGENTS.md)
  autostart on|off  start automatically when you log in
  download          (re)download the voice model
  log               show the last lines of the log
"""


def _setup_logging(console: bool) -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.FileHandler(LOG_PATH, encoding="utf-8")]
    if console:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )


def cmd_run(console: bool = True) -> int:
    _setup_logging(console)
    try:
        narrator = Narrator()
    except AlreadyRunning as exc:
        print(exc)
        return 1
    if console:
        print("Listening to Claude Code and Codex. Press Ctrl+C to stop.")
    narrator.run()
    return 0


def cmd_start() -> int:
    if send("status") is not None:
        print("agent-voice is already running.")
        return 0
    HOME.mkdir(parents=True, exist_ok=True)
    args = [autostart.background_python(), "-m", "agent_voice", "run", "--quiet"]
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if platform.system() == "Windows":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(args, **kwargs)
    # Loading the voice model takes a few seconds (longer on first run, when
    # it is downloaded).
    for _ in range(240):
        time.sleep(0.5)
        reply = send("status")
        if reply and reply != "starting":
            print(f"agent-voice started: {reply}")
            return 0
    print(f"agent-voice did not report in; see the log: {LOG_PATH}")
    return 1


def cmd_restart() -> int:
    if send("stop") is not None:
        # Wait for the old process to release the control port before starting.
        for _ in range(40):
            time.sleep(0.25)
            if send("status", timeout=0.5) is None:
                break
        else:
            print("the running narrator did not stop; see: agent-voice log")
            return 1
        print("agent-voice stopped.")
    return cmd_start()


def cmd_config(args: list[str]) -> int:
    cfg = Config.load()
    if len(args) >= 2:
        value = " ".join(args[1:])
        try:
            if args[0] == "narration" and value not in instructions.NARRATION_STYLES:
                raise ValueError(f"narration must be one of: {', '.join(instructions.NARRATION_STYLES)}")
            if args[0] == "hotkey":
                if value.strip().lower() in ("off", "none", "disable", "disabled"):
                    value = ""
                else:
                    from .hotkey import to_pynput

                    to_pynput(value)  # reject typos before saving
            cfg.set(args[0], value)
        except (KeyError, ValueError) as exc:
            print(exc)
            return 1
        cfg.save()
        if args[0] == "narration":
            for agent, path in instructions.targets().items():
                if instructions.installed(path):
                    instructions.install(path, cfg.narration)
                    print(f"  {agent} instructions updated (new sessions use them)")
        if send("reload") is not None:
            print("saved; running narrator reloaded.")
        else:
            print("saved.")
    for key, value in cfg.__dict__.items():
        print(f"  {key:<11} {value}")
    print(f"\n  file: {CONFIG_PATH}")
    return 0


def cmd_voices() -> int:
    from .tts import make_engine

    engine = make_engine(Config.load())
    voices = engine.voices()
    print(" ".join(voices))
    if engine.name == "kokoro":
        print("\nFirst letter: a = American, b = British; second: f = female, m = male.")
        print("Try one:  agent-voice config voice am_michael  then  agent-voice say hello")
    return 0


def cmd_say(text: str) -> int:
    reply = send(f"say {text}")
    if reply is not None:
        return 0
    # No daemon running: speak directly in this process.
    from .tts import make_engine

    _setup_logging(console=True)
    engine = make_engine(Config.load())
    engine.speak(clean(text) or text, threading.Event())
    return 0


def cmd_instructions(choice: str) -> int:
    for agent, path in instructions.targets().items():
        if choice == "on":
            print(f"  {agent:<12} {instructions.install(path, Config.load().narration)}: {path}")
        elif choice == "off":
            print(f"  {agent:<12} {'removed' if instructions.remove(path) else 'not present'}: {path}")
        else:
            print(f"  {agent:<12} {'on' if instructions.installed(path) else 'off'}: {path}")
    if choice == "on":
        print(f"\nNew Claude Code / Codex sessions will add 🔊 voice lines (narration={Config.load().narration});")
        print("agent-voice speaks only those. Switch style: agent-voice config narration live|quiet")
        print("Sessions that are already open keep their old instructions until restarted.")
    if choice == "off" and Config.load().speak == "marked":
        print("\nNote: speak=marked, so nothing will be spoken. Use: agent-voice config speak all")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Windows pipes default to cp1252, which cannot print 🔊; don't crash on it.
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(prog="agent-voice", usage=USAGE, add_help=False)
    parser.add_argument("command", nargs="?", default="help")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    parser.add_argument("--quiet", action="store_true", help=argparse.SUPPRESS)
    ns = parser.parse_args(argv)
    cmd, args = ns.command, ns.args
    if "--quiet" in args:
        args.remove("--quiet")
        ns.quiet = True

    if cmd in ("help", "-h", "--help"):
        print(USAGE)
        return 0
    if cmd == "run":
        return cmd_run(console=not ns.quiet and sys.stdout is not None)
    if cmd == "start":
        return cmd_start()
    if cmd == "restart":
        return cmd_restart()
    if cmd in ("stop", "status", "mute", "unmute", "toggle", "skip"):
        reply = send(cmd)
        if reply is None:
            print("agent-voice is not running. Start it with:  agent-voice start")
            return 0 if cmd in ("status", "stop") else 1
        print(reply)
        return 0
    if cmd == "say":
        return cmd_say(" ".join(args) or "Hello! I will read out what your coding agents say.")
    if cmd == "config":
        return cmd_config(args)
    if cmd == "voices":
        return cmd_voices()
    if cmd == "autostart":
        choice = (args[0] if args else "status").lower()
        if choice == "on":
            print(f"autostart enabled: {autostart.enable()}")
        elif choice == "off":
            print("autostart disabled." if autostart.disable() else "autostart was not enabled.")
        else:
            print("autostart is", "on" if autostart.enabled() else "off")
        return 0
    if cmd == "instructions":
        return cmd_instructions((args[0] if args else "status").lower())
    if cmd == "download":
        from .tts import download_models

        download_models(force="--force" in args)
        return 0
    if cmd == "log":
        if LOG_PATH.exists():
            lines = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
            print("\n".join(lines[-40:]))
        return 0
    print(f"unknown command: {cmd}\n\n{USAGE}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
