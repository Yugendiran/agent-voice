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
    path.write_text(text.replace("most messages", "OLD"), encoding="utf-8")
    assert instructions.install(path) == "updated"
    assert path.read_text(encoding="utf-8").count(BEGIN) == 1

    instructions.remove(path)
    assert path.read_text(encoding="utf-8") == "# My rules\n\nBe concise.\n"
    assert END not in path.read_text(encoding="utf-8")


def test_narrator_speaks_only_marked_lines_by_default():
    from agent_voice.config import Config
    from agent_voice.daemon import Narrator
    from agent_voice.sources import Utterance

    n = Narrator.__new__(Narrator)  # skip engine / port setup
    n.cfg = Config()
    marked = Utterance("claude", "Looked at `a.py`.\n🔊 Found the bug in the parser.", False, "1")
    plain = Utterance("claude", "Reading the files now.", False, "2")
    assert n.speech_for(marked) == "Found the bug in the parser."
    assert n.speech_for(plain) == ""

    n.cfg.speak = "all"
    assert n.speech_for(plain) == "Reading the files now."
