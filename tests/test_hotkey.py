import pytest
from pynput.keyboard import HotKey, Key, Listener

from agent_voice.hotkey import to_pynput


def test_friendly_names_converted():
    assert to_pynput("shift+backspace") == "<shift>+<backspace>"
    assert to_pynput("Ctrl+Alt+X") == "<ctrl>+<alt>+x"
    assert to_pynput("win+escape") == "<cmd>+<esc>"
    assert to_pynput("f9") == "<f9>"


@pytest.mark.parametrize("bad", ["", "ctrl+", "ctrl++x", "shift+notakey", "ctrl+ctrl"])
def test_invalid_shortcuts_rejected(bad):
    with pytest.raises(ValueError):
        to_pynput(bad)


def test_default_shortcut_fires_only_on_the_full_combo():
    fired = []
    hk = HotKey(HotKey.parse(to_pynput("shift+backspace")), lambda: fired.append(1))
    canon = Listener().canonical  # what GlobalHotKeys does to every key event
    hk.press(canon(Key.backspace))  # backspace alone: no
    hk.release(canon(Key.backspace))
    assert fired == []
    hk.press(canon(Key.shift_r))  # either shift key
    hk.press(canon(Key.backspace))
    assert fired == [1]
