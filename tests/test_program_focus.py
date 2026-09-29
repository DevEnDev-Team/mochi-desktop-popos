from __future__ import annotations

import time
from unittest.mock import Mock, patch

import pytest

from mochi.config import ConfigStore
from mochi.presence.bond_meter import BondMeter, BondState
from mochi.emotes import EMOTE_CATALOGUE
from mochi.presence.integration import PresenceBuddyMixin
from mochi.presence.program_focus import (
    ProgramFocusMonitor,
    get_installed_applications,
    matches_program,
)


class TestProgramMatching:
    def test_exact_match_case_insensitive(self) -> None:
        assert matches_program("code", ["code"])
        assert matches_program("Code", ["code"])
        assert matches_program("CODE", ["Code"])

    def test_alias_category_matching(self) -> None:
        # Category alias: vscode matches code, code-oss, vscodium
        assert matches_program("vscode", ["code-oss"])
        assert matches_program("vscode", ["vscodium"])
        assert matches_program("editor", ["nvim"])
        assert matches_program("terminal", ["ptyxis", "org.gnome.Ptyxis"])
        assert matches_program("terminal", ["kitty"])
        assert matches_program("browser", ["google-chrome"])
        assert matches_program("browser", ["firefox"])
        assert matches_program("pixel_art", ["aseprite"])

    def test_substring_and_identifier_matching(self) -> None:
        assert matches_program("blender", ["org.blender.Blender", "blender-bin"])
        assert matches_program("steam", ["steamwebhelper", "Steam"])
        assert not matches_program("blender", ["firefox", "code"])

    def test_empty_targets(self) -> None:
        assert not matches_program("", ["firefox"])
        assert not matches_program("   ", ["firefox"])
        assert not matches_program("firefox", [])


class TestInstalledApplications:
    def test_returns_list_of_tuples(self) -> None:
        apps = get_installed_applications()
        assert isinstance(apps, list)
        assert len(apps) > 0
        for name, identifier in apps:
            assert isinstance(name, str)
            assert isinstance(identifier, str)
            assert len(name) > 0
            assert len(identifier) > 0


from types import SimpleNamespace
import logging

from mochi.state import MochiState


class TestProgramFocusMonitor:
    def test_filters_out_mochi_itself(self) -> None:
        callback = Mock()
        monitor = ProgramFocusMonitor(on_program_focused=callback)
        monitor.start()
        with patch("mochi.presence.program_focus.query_x11_active_window", return_value=["mochi-desktop"]):
            monitor._poll_focus()
        callback.assert_not_called()
        monitor.stop()

    def test_triggers_callback_when_external_app_focused(self) -> None:
        callback = Mock()
        monitor = ProgramFocusMonitor(on_program_focused=callback)
        monitor.start()
        with patch("mochi.presence.program_focus.query_x11_active_window", return_value=["code", "Code"]):
            monitor._poll_focus()
        callback.assert_called_once_with(["code", "Code"])
        monitor.stop()

    def test_triggers_callback_from_worker_focus(self) -> None:
        callback = Mock()
        monitor = ProgramFocusMonitor(on_program_focused=callback)
        monitor.start()

        monitor._handle_worker_focus(["Firefox", "Firefox - Choose a profile"])
        callback.assert_called_once_with(["Firefox", "Firefox - Choose a profile"])
        monitor.stop()

    def test_worker_defocus_clears_focus(self) -> None:
        callback = Mock()
        monitor = ProgramFocusMonitor(on_program_focused=callback)
        monitor.start()

        monitor._handle_worker_focus(["Firefox"])
        callback.assert_called_with(["Firefox"])

        monitor._handle_worker_focus([])
        callback.assert_called_with([])
        monitor.stop()

    def test_poll_falls_back_to_x11_when_worker_not_running(self) -> None:
        callback = Mock()
        monitor = ProgramFocusMonitor(on_program_focused=callback)
        monitor.start()
        # Simulate worker terminated or not running
        monitor._worker_process = None

        with patch("mochi.presence.program_focus.query_x11_active_window", return_value=["code"]):
            monitor._poll_focus()

        callback.assert_called_once_with(["code"])
        monitor.stop()

    def test_category_signal_notification(self) -> None:
        callback = Mock()
        monitor = ProgramFocusMonitor(on_program_focused=callback)
        monitor.start()
        monitor.notify_app_category("terminal")
        callback.assert_called_once_with(["terminal"])
        monitor.stop()


class DummyBuddy(PresenceBuddyMixin):
    def __init__(self, config: ConfigStore, bond_level: int = 1) -> None:
        self._config = config
        self._bond_state = BondState(level=bond_level, xp=0)
        self.state = SimpleNamespace(current=MochiState.IDLE)
        self._active_program_emote: str | None = None
        self._current_program_identifiers: list[str] = []
        self._logger = logging.getLogger("dummy")
        self._presence_shutting_down = False
        self._drag_started = False
        self._dev_unlock_all_emotes = False
        self._catalogue_animations_played: list[tuple[str, bool]] = []
        self._animations_played: list[str] = []

    def _play_autonomous_catalogue_emote(self, animation: str, *, looping: bool = False) -> bool:
        self._catalogue_animations_played.append((animation, looping))
        self.state.current = MochiState.IDLE_EMOTE
        return True

    def _transition_to(self, target: MochiState) -> bool:
        self.state.current = target
        return True

    def _play_animation(self, name: str) -> None:
        self._animations_played.append(name)


class TestPresenceProgramFocusIntegration:
    def test_on_program_focused_loops_matching_unlocked_emote(self, tmp_path) -> None:
        config = ConfigStore(tmp_path / "config.json")
        # Find first unlocked emote in catalogue (level 1)
        unlocked_emote = None
        for emote in EMOTE_CATALOGUE:
            if emote.required_bond_level == 1 and emote.animation:
                unlocked_emote = emote
                break
        assert unlocked_emote is not None

        # Assign it to "blender"
        config.save_emote_assignment(unlocked_emote.id, random=False, program="blender")

        buddy = DummyBuddy(config, bond_level=1)
        # Trigger focus with blender
        buddy._on_program_focused(["org.blender.Blender", "blender"])

        assert len(buddy._catalogue_animations_played) == 1
        assert buddy._catalogue_animations_played[0] == (unlocked_emote.animation, True)
        assert buddy._active_program_emote == unlocked_emote.animation

        # While still on the same program, repeated poll does not re-trigger or restart the animation
        buddy._on_program_focused(["blender"])
        assert len(buddy._catalogue_animations_played) == 1

    def test_on_program_focused_stops_loop_when_unfocused(self, tmp_path) -> None:
        config = ConfigStore(tmp_path / "config.json")
        unlocked_emote = next(e for e in EMOTE_CATALOGUE if e.required_bond_level == 1 and e.animation)
        config.save_emote_assignment(unlocked_emote.id, random=False, program="firefox")

        buddy = DummyBuddy(config, bond_level=1)
        buddy._on_program_focused(["firefox"])
        assert buddy._active_program_emote == unlocked_emote.animation

        # Switching to desktop or unassigned app stops the loop and returns to idle
        buddy._on_program_focused([])
        assert buddy._active_program_emote is None
        assert buddy.state.current is MochiState.IDLE
        assert "idle" in buddy._animations_played

    def test_maybe_resume_program_focus_emote(self, tmp_path) -> None:
        config = ConfigStore(tmp_path / "config.json")
        unlocked_emote = next(e for e in EMOTE_CATALOGUE if e.required_bond_level == 1 and e.animation)
        config.save_emote_assignment(unlocked_emote.id, random=False, program="code")

        buddy = DummyBuddy(config, bond_level=1)
        buddy._on_program_focused(["code"])
        assert buddy._active_program_emote == unlocked_emote.animation

        # Simulate returning from an interaction (state back to IDLE)
        buddy.state.current = MochiState.IDLE
        buddy._catalogue_animations_played.clear()

        resumed = buddy._maybe_resume_program_focus_emote()
        assert resumed is True
        assert len(buddy._catalogue_animations_played) == 1
        assert buddy._catalogue_animations_played[0] == (unlocked_emote.animation, True)

    def test_on_program_focused_ignores_locked_emote(self, tmp_path) -> None:
        config = ConfigStore(tmp_path / "config.json")
        # Find a locked emote (requires higher bond level, e.g. level 3)
        locked_emote = next(e for e in EMOTE_CATALOGUE if (e.required_bond_level or 0) > 1 and e.animation)
        config.save_emote_assignment(locked_emote.id, random=False, program="gimp")

        buddy = DummyBuddy(config, bond_level=1)
        # Bond meter at level 1, emote requires higher level
        buddy._on_program_focused(["gimp"])
        assert len(buddy._catalogue_animations_played) == 0
        assert buddy._active_program_emote is None

