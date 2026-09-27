"""Regression coverage for presentation-priority speech suppression."""

from unittest.mock import Mock

from mochi.presence.bubble import SpeechBubble, _disable_focus_tree


def test_speech_bubble_rejects_quip_when_presentation_priority_blocks_it() -> None:
    bubble = object.__new__(SpeechBubble)
    bubble._can_show = Mock(return_value=False)
    bubble._logger = Mock()

    assert bubble.show("not now", duration_seconds=2.0) is False
    bubble._can_show.assert_called_once_with()


def test_speech_bubble_focus_tree_is_disabled_for_passive_surfaces() -> None:
    widget = Mock()

    _disable_focus_tree(widget)

    widget.set_focusable.assert_called_once_with(False)
    widget.set_can_focus.assert_called_once_with(False)


def test_speech_bubble_sets_override_redirect_in_x11(monkeypatch) -> None:
    bubble = object.__new__(SpeechBubble)
    bubble._can_show = None
    bubble._logger = Mock()
    bubble._window = Mock()
    bubble._window.get_visible.return_value = False
    bubble._popover = Mock()
    bubble._popover.get_visible.return_value = False
    bubble._cancel_sources = Mock()
    bubble._set_text = Mock()
    bubble._schedule_hide = Mock()
    bubble._position_x11 = Mock()
    bubble._fade = Mock()
    bubble._animation_serial = 0
    bubble._owner = Mock()

    mock_set_override = Mock()
    monkeypatch.setattr("mochi.presence.bubble.set_override_redirect", mock_set_override)
    monkeypatch.setattr("mochi.presence.bubble.get_window_position", lambda _owner: (100, 200))
    monkeypatch.setattr("mochi.presence.bubble.GLib.idle_add", Mock())
    monkeypatch.setattr("mochi.presence.bubble.GLib.timeout_add", Mock())

    res = bubble.show("hello", duration_seconds=3.0)
    assert res is True
    bubble._window.realize.assert_called_once()
    mock_set_override.assert_called_once_with(bubble._window, True)
    bubble._window.set_visible.assert_called_once_with(True)


def test_raise_window_returns_false_for_non_x11_surface() -> None:
    from mochi.x11 import raise_window

    window = Mock()
    window.get_surface.return_value = Mock()  # not GdkX11.X11Surface
    assert raise_window(window) is False

