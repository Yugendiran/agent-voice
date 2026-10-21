import pytest

from agent_voice import instructions
from agent_voice.instructions import BEGIN, END, voice_lines


def test_voice_lines_extracted():
    msg = "I checked the logs and found the cause.\n\n🔊 The build is fixed and all tests pass.\n\nDetails below."
    assert voice_lines(msg) == "The build is fixed and all tests pass."


def test_no_voice_line_means_silence():
    assert voice_lines("Reading the config files now.") == ""


def test_voice_line_variants():
    assert voice_lines("> 🔊 Need your approval to push.") == "Need your approval to push."
    assert voice_lines("**🔊 Tests are failing.**") == "Tests are failing."
    assert voice_lines("🔊️: Done.") == "Done."  # emoji variation selector
    assert voice_lines("🔊 One.\ntext\n🔊 Two.") == "One. Two."


def test_install_creates_updates_and_removes(tmp_path):
    path = tmp_path / "CLAUDE.md"
    assert instructions.install(path) == "added"
    assert instructions.installed(path)
    assert instructions.install(path) == "already up to date"
    assert instructions.remove(path)
    assert not path.exists()  # it only held our block


def test_install_keeps_user_content(tmp_path):
    path = tmp_path / "AGENTS.md"
    path.write_text("# My rules\n\nBe concise.\n", encoding="utf-8")
    instructions.install(path)
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# My rules\n\nBe concise.\n\n" + BEGIN)

    # An outdated block is replaced in place, not duplicated.
    path.write_text(text.replace("Voice updates", "OLD"), encoding="utf-8")
    assert instructions.install(path) == "updated"
    assert path.read_text(encoding="utf-8").count(BEGIN) == 1

    instructions.remove(path)
    assert path.read_text(encoding="utf-8") == "# My rules\n\nBe concise.\n"
    assert END not in path.read_text(encoding="utf-8")


def test_narrator_speech_per_narration_style():
    from agent_voice.config import Config
    from agent_voice.daemon import Narrator
    from agent_voice.sources import Utterance

    n = Narrator.__new__(Narrator)  # skip engine / port setup
    n.cfg = Config()
    marked = Utterance("claude", "Looked at `a.py`.\n🔊 Found the bug in the parser.", False, "1")
    plain = Utterance("claude", "Reading the files now.", False, "2")

    # live (default): a 🔊 line wins; in-between updates are spoken as written.
    assert n.speech_for(marked) == "Found the bug in the parser."
    assert n.speech_for(plain) == "Reading the files now."

    # quiet: only 🔊 lines.
    n.cfg.narration = "quiet"
    assert n.speech_for(marked) == "Found the bug in the parser."
    assert n.speech_for(plain) == ""

    n.cfg.speak = "all"
    assert n.speech_for(plain) == "Reading the files now."


def test_long_update_without_voice_line_is_cut_to_its_first_sentences():
    from agent_voice.config import Config
    from agent_voice.daemon import UPDATE_MAX_CHARS, Narrator
    from agent_voice.sources import Utterance

    n = Narrator.__new__(Narrator)
    n.cfg = Config()
    update = (
        "The test file is fixed. I'll re-read the instructions file and fix the f-string. "
        + "Then I will go through every other module in the package one by one. " * 10
        + "\n```python\nprint('code is never spoken')\n```"
    )
    spoken = n.speech_for(Utterance("claude", update, False, "u"))
    assert spoken.startswith("The test file is fixed. I'll re-read the instructions file")
    assert len(spoken) <= UPDATE_MAX_CHARS and "print" not in spoken


def test_marked_work_summary_is_not_trimmed():
    from agent_voice.config import Config
    from agent_voice.daemon import Narrator
    from agent_voice.sources import Utterance

    n = Narrator.__new__(Narrator)
    n.cfg = Config()
    summary = (
        "I fixed the join class flow. The join button was calling the old session endpoint, "
        "so I switched it to the new one and added a retry when the class has not started yet. "
        "All twelve tests pass and I checked it in the app. Nothing is committed yet, "
        "so tell me if you want me to commit it."
    )
    n.cfg.max_chars = 100  # speak=all would trim to this; voice lines are not
    assert n.speech_for(Utterance("claude", "Done.\n\n🔊 " + summary, True, "s")) == summary


def test_narration_styles(tmp_path):
    live, quiet = instructions.text("live"), instructions.text("quiet")
    assert "Live narration" in live and "Live narration" not in quiet
    assert "Work summary" in live and "Work summary" in quiet

    path = tmp_path / "CLAUDE.md"
    instructions.install(path, "quiet")
    assert instructions.install(path, "live") == "updated"
    assert "Live narration" in path.read_text(encoding="utf-8")
    assert path.read_text(encoding="utf-8").count(BEGIN) == 1

    with pytest.raises(ValueError):
        instructions.text("chatty")
