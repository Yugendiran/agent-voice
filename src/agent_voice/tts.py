"""Text-to-speech engines.

Every engine exposes ``speak(text, cancel)``, which blocks until the text has
been spoken or ``cancel`` is set, in which case it stops as soon as it can.
"""

from __future__ import annotations

import logging
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from .config import MODELS_DIR, Config

log = logging.getLogger("agent_voice")
# kokoro's phonemizer warns "words count mismatch" on most sentences; it is harmless.
logging.getLogger("phonemizer").setLevel(logging.ERROR)

KOKORO_RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
KOKORO_FILES = {
    "kokoro-v1.0.int8.onnx": f"{KOKORO_RELEASE}/kokoro-v1.0.int8.onnx",
    "voices-v1.0.bin": f"{KOKORO_RELEASE}/voices-v1.0.bin",
}

_SENTENCE = re.compile(r"(?<=[.!?;:])\s+")


def download_models(force: bool = False) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in KOKORO_FILES.items():
        target = MODELS_DIR / name
        if target.exists() and target.stat().st_size > 0 and not force:
            continue
        print(f"Downloading {name} ...", flush=True)
        tmp = target.with_suffix(target.suffix + ".part")
        shown = [-1]

        def progress(blocks: int, block_size: int, total: int) -> None:
            if total <= 0:
                return
            pct = min(100, blocks * block_size * 100 // total)
            # Redraw only on change; a terminal shows one updating line, a log
            # file gets at most ~10 lines.
            step = 1 if sys.stdout.isatty() else 10
            if pct // step != shown[0] // step:
                shown[0] = pct
                if step == 1:
                    print(f"\r  {pct:3d}% of {total / 1e6:.0f} MB", end="", flush=True)
                else:
                    print(f"  {pct:3d}% of {total / 1e6:.0f} MB", flush=True)

        urllib.request.urlretrieve(url, tmp, progress)
        tmp.replace(target)
        print()


def models_present() -> bool:
    return all((MODELS_DIR / name).exists() for name in KOKORO_FILES)


def _chunks(text: str, limit: int = 180) -> list[str]:
    """Split into sentence-sized pieces so the first audio starts quickly."""
    out: list[str] = []
    for sentence in _SENTENCE.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if out and len(out[-1]) + len(sentence) < 60:
            out[-1] = f"{out[-1]} {sentence}"  # glue very short sentences together
        elif len(sentence) > limit:
            words, piece = sentence.split(), ""
            for word in words:
                if piece and len(piece) + len(word) > limit:
                    out.append(piece)
                    piece = word
                else:
                    piece = f"{piece} {word}".strip()
            if piece:
                out.append(piece)
        else:
            out.append(sentence)
    return out


class KokoroEngine:
    name = "kokoro"

    def __init__(self, cfg: Config) -> None:
        if not models_present():
            download_models()
        from kokoro_onnx import Kokoro  # imported lazily: it is slow to load
        import sounddevice

        self._sd = sounddevice
        self._cfg = cfg
        self._kokoro = Kokoro(
            str(MODELS_DIR / "kokoro-v1.0.int8.onnx"),
            str(MODELS_DIR / "voices-v1.0.bin"),
        )
        voices = set(self._kokoro.get_voices())
        if cfg.voice not in voices:
            log.warning("voice %r not found, using af_heart", cfg.voice)
            cfg.voice = "af_heart"

    def voices(self) -> list[str]:
        return sorted(self._kokoro.get_voices())

    def _synth(self, text: str):
        lang = "en-gb" if self._cfg.voice.startswith("b") else "en-us"
        return self._kokoro.create(text, voice=self._cfg.voice, speed=self._cfg.speed, lang=lang)

    def speak(self, text: str, cancel: threading.Event) -> None:
        pieces = _chunks(text)
        if not pieces:
            return
        audio, rate = self._synth(pieces[0])
        for i in range(len(pieces)):
            if cancel.is_set():
                return
            self._sd.play(audio, rate)
            # Synthesize the next piece while this one plays.
            nxt = self._synth(pieces[i + 1]) if i + 1 < len(pieces) else None
            ends_at = time.monotonic() + len(audio) / rate
            while time.monotonic() < ends_at:
                if cancel.is_set():
                    self._sd.stop()
                    return
                time.sleep(0.03)
            self._sd.wait()
            if nxt is not None:
                audio, rate = nxt


class SystemEngine:
    """The voice built into the OS. No downloads, more robotic."""

    name = "system"

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        system = platform.system()
        if system == "Windows":
            rate = max(-10, min(10, round((cfg.speed - 1.0) * 10)))
            script = (
                "[Console]::InputEncoding = [Text.Encoding]::UTF8;"
                "Add-Type -AssemblyName System.Speech;"
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                f"$s.Rate = {rate};"
                "$s.Speak([Console]::In.ReadToEnd())"
            )
            self._cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
            self._stdin = True
        elif system == "Darwin":
            self._cmd = ["say", "-r", str(int(190 * cfg.speed))]
            self._stdin = True
        else:
            exe = shutil.which("espeak-ng") or shutil.which("espeak")
            if exe:
                self._cmd = [exe, "-s", str(int(170 * cfg.speed)), "--stdin"]
                self._stdin = True
            elif shutil.which("spd-say"):
                self._cmd = ["spd-say", "-w"]
                self._stdin = False
            else:
                raise RuntimeError("no system TTS found; install espeak-ng or use the kokoro engine")

    def voices(self) -> list[str]:
        return ["(system default)"]

    def speak(self, text: str, cancel: threading.Event) -> None:
        cmd = self._cmd if self._stdin else [*self._cmd, text]
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if self._stdin else subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        if self._stdin:
            proc.stdin.write(text.encode("utf-8"))
            proc.stdin.close()
        while proc.poll() is None:
            if cancel.is_set():
                proc.kill()
                return
            time.sleep(0.05)


def make_engine(cfg: Config):
    if cfg.engine == "kokoro":
        try:
            return KokoroEngine(cfg)
        except Exception as exc:  # missing model, no audio device, import error...
            log.error("kokoro engine unavailable (%s); falling back to system voice", exc)
    return SystemEngine(cfg)
