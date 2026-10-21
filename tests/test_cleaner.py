from agent_voice.cleaner import clean


def test_plain_sentence_unchanged():
    assert clean("Java can connect to those servers.") == "Java can connect to those servers."


def test_code_blocks_are_dropped():
    text = "I'll run the build.\n```bash\n./gradlew assembleDebug --stacktrace\n```\nThen check the output."
    assert clean(text) == "I'll run the build. Then check the output."


def test_code_only_message_is_silent():
    assert clean("```\nls -la\n```") == ""


def test_short_inline_code_kept_long_inline_code_replaced():
    assert clean("Run `pyenv` first.") == "Run pyenv first."
    assert clean("Run `curl -sSL -o /dev/null https://x.y/z` now.") == "Run that now."


def test_ips_paths_urls_hashes():
    text = (
        "GitHub's server at 185.199.109.133 is unreachable. "
        "See https://services.gradle.org/distributions for details. "
        "The cache is in C:\\Users\\dev\\.gradle\\wrapper\\dists and /home/dev/.gradle/wrapper. "
        "Commit 3f9a2c1d8e7b4a6f fixed it."
    )
    out = clean(text)
    assert "185.199" not in out and "an IP address" in out
    assert "https" not in out and "a link" in out
    assert "\\" not in out and "/home" not in out and "a file path" in out
    assert "3f9a2c1d8e7b4a6f" not in out and "a hash" in out


def test_markdown_formatting_removed():
    text = "## Summary\n- **Fixed** the `login` bug\n- Added [docs](http://x.io)"
    assert clean(text) == "Summary. Fixed the login bug. Added docs."


def test_tables_dropped():
    text = "Here are the options:\n| a | b |\n|---|---|\n| 1 | 2 |\nPick one."
    assert clean(text) == "Here are the options: Pick one."


def test_file_line_refs_shortened():
    assert clean("The bug is in watcher.py:42 now.") == "The bug is in watcher.py now."


def test_long_text_cut_at_sentence_boundary():
    text = " ".join(f"This is sentence number {i}." for i in range(50))
    out = clean(text, max_chars=100)
    assert len(out) <= 100
    assert out.endswith(".")
    assert out.startswith("This is sentence number 0.")


def test_symbols_and_emoji_dropped():
    assert clean("● Done ✅ — all tests pass 🎉") == "Done, all tests pass."


def test_inline_code_paths_and_links_named():
    assert clean(r"Created a folder under `D:\projects`.") == "Created a folder under a file path."
    assert clean("Open `https://x.io/a/b`.") == "Open a link."
    assert clean("It lives in `/usr/local/bin`.") == "It lives in a file path."
