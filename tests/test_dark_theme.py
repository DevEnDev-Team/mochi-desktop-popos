"""Comprehensive tests for Mochi's toggleable dark theme."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk  # noqa: E402

from mochi.buddy_menu import BuddyMenuController
from mochi.config import ConfigStore
from mochi.menu_window import MenuWindow
from mochi.presence.bubble import SpeechBubble
from mochi.presence.emote_catalogue import EmoteCatalogueWindow


class DarkThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_config_store_dark_theme_defaults_off_and_persists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            store = ConfigStore(config_file)
            self.assertFalse(store.load_dark_theme())

            store.save_dark_theme(True)
            self.assertTrue(store.load_dark_theme())

            store.save_dark_theme(False)
            self.assertFalse(store.load_dark_theme())

    def test_menu_window_dark_theme_toggle_and_initial_flag(self) -> None:
        owner = Gtk.Window()
        anchor = Gtk.Box()

        # Defaults to light (no mochi-dark-theme class)
        menu_light = MenuWindow(
            owner=owner,
            anchor_widget=anchor,
            preferred_width=244,
            preferred_height=176,
            dark_theme=False,
        )
        self.assertTrue(menu_light.window.has_css_class("mochi-menu-window"))
        self.assertFalse(menu_light.window.has_css_class("mochi-dark-theme"))

        # Enable dark theme dynamically
        menu_light.set_dark_theme(True)
        self.assertTrue(menu_light.window.has_css_class("mochi-dark-theme"))

        # Disable dark theme dynamically
        menu_light.set_dark_theme(False)
        self.assertFalse(menu_light.window.has_css_class("mochi-dark-theme"))

        # Initialize with dark_theme=True
        menu_dark = MenuWindow(
            owner=owner,
            anchor_widget=anchor,
            preferred_width=244,
            preferred_height=176,
            dark_theme=True,
        )
        self.assertTrue(menu_dark.window.has_css_class("mochi-dark-theme"))

    def test_speech_bubble_dark_theme_toggle_and_initial_flag(self) -> None:
        owner = Gtk.Window()
        anchor = Gtk.Box()

        # Defaults to light
        bubble_light = SpeechBubble(
            owner=owner,
            anchor_widget=anchor,
            dark_theme=False,
        )
        self.assertFalse(bubble_light._window.has_css_class("mochi-dark-theme"))
        self.assertFalse(bubble_light._popover.has_css_class("mochi-dark-theme"))

        # Enable dark theme dynamically
        bubble_light.set_dark_theme(True)
        self.assertTrue(bubble_light._window.has_css_class("mochi-dark-theme"))
        self.assertTrue(bubble_light._popover.has_css_class("mochi-dark-theme"))

        # Disable dark theme dynamically
        bubble_light.set_dark_theme(False)
        self.assertFalse(bubble_light._window.has_css_class("mochi-dark-theme"))
        self.assertFalse(bubble_light._popover.has_css_class("mochi-dark-theme"))

        # Initialize with dark_theme=True
        bubble_dark = SpeechBubble(
            owner=owner,
            anchor_widget=anchor,
            dark_theme=True,
        )
        self.assertTrue(bubble_dark._window.has_css_class("mochi-dark-theme"))
        self.assertTrue(bubble_dark._popover.has_css_class("mochi-dark-theme"))

    def test_emote_catalogue_window_dark_theme_toggle(self) -> None:
        from mochi.sprites import SpriteAtlas

        owner = Gtk.Window()
        atlas = SpriteAtlas()
        catalogue = EmoteCatalogueWindow(owner=owner, atlas=atlas)

        self.assertFalse(catalogue.window.has_css_class("mochi-dark-theme"))
        catalogue.set_dark_theme(True)
        self.assertTrue(catalogue.window.has_css_class("mochi-dark-theme"))
        catalogue.set_dark_theme(False)
        self.assertFalse(catalogue.window.has_css_class("mochi-dark-theme"))

    def test_buddy_menu_controller_dark_theme_row_and_toggle(self) -> None:
        mock_buddy = Mock()
        mock_buddy._dark_theme = False
        mock_buddy._config = Mock()
        mock_buddy._logger = Mock()

        mock_context_menu = Mock()
        mock_dev_menu = Mock()
        mock_bubble = Mock()
        mock_catalogue = Mock()

        mock_buddy._context_menu = mock_context_menu
        mock_buddy._developer_menu = mock_dev_menu
        mock_buddy._presence_bubble = mock_bubble
        mock_buddy._emote_catalogue_window = mock_catalogue

        mock_nameplate = Mock()
        mock_bond_overlay = Mock()
        mock_quick_start = Mock()
        mock_focus = Mock()

        mock_buddy._nameplate = mock_nameplate
        mock_buddy._bond_progress_overlay = mock_bond_overlay
        mock_buddy._quick_start_window = mock_quick_start
        mock_buddy._focus_window = mock_focus

        controller = BuddyMenuController(mock_buddy)
        button, switch = controller._make_dark_theme_row()

        self.assertIsInstance(button, Gtk.Button)
        self.assertIsInstance(switch, Gtk.Switch)
        self.assertFalse(switch.get_active())

        mock_buddy._dark_theme_switch = switch

        # Toggle to True
        controller._toggle_dark_theme()
        self.assertTrue(mock_buddy._dark_theme)
        self.assertTrue(switch.get_active())
        mock_buddy._config.save_dark_theme.assert_called_with(True)
        mock_context_menu.set_dark_theme.assert_called_with(True)
        mock_dev_menu.set_dark_theme.assert_called_with(True)
        mock_bubble.set_dark_theme.assert_called_with(True)
        mock_catalogue.set_dark_theme.assert_called_with(True)
        mock_nameplate.set_dark_theme.assert_called_with(True)
        mock_bond_overlay.set_dark_theme.assert_called_with(True)
        mock_quick_start.set_dark_theme.assert_called_with(True)
        mock_focus.set_dark_theme.assert_called_with(True)

        # Toggle to False
        controller._toggle_dark_theme()
        self.assertFalse(mock_buddy._dark_theme)
        self.assertFalse(switch.get_active())
        mock_buddy._config.save_dark_theme.assert_called_with(False)
        mock_context_menu.set_dark_theme.assert_called_with(False)
        mock_dev_menu.set_dark_theme.assert_called_with(False)
        mock_bubble.set_dark_theme.assert_called_with(False)
        mock_catalogue.set_dark_theme.assert_called_with(False)
        mock_nameplate.set_dark_theme.assert_called_with(False)
        mock_bond_overlay.set_dark_theme.assert_called_with(False)
        mock_quick_start.set_dark_theme.assert_called_with(False)
        mock_focus.set_dark_theme.assert_called_with(False)

    def test_nameplate_dark_theme_toggle_and_initial_flag(self) -> None:
        from mochi.presence.nameplate import Nameplate

        owner = Gtk.Window()
        anchor = Gtk.Box()

        plate_light = Nameplate(owner=owner, anchor_widget=anchor, dark_theme=False)
        self.assertFalse(plate_light._window.has_css_class("mochi-dark-theme"))
        self.assertFalse(plate_light._popover.has_css_class("mochi-dark-theme"))

        plate_light.set_dark_theme(True)
        self.assertTrue(plate_light._window.has_css_class("mochi-dark-theme"))
        self.assertTrue(plate_light._popover.has_css_class("mochi-dark-theme"))

        plate_light.set_dark_theme(False)
        self.assertFalse(plate_light._window.has_css_class("mochi-dark-theme"))
        self.assertFalse(plate_light._popover.has_css_class("mochi-dark-theme"))

        plate_dark = Nameplate(owner=owner, anchor_widget=anchor, dark_theme=True)
        self.assertTrue(plate_dark._window.has_css_class("mochi-dark-theme"))
        self.assertTrue(plate_dark._popover.has_css_class("mochi-dark-theme"))

    def test_bond_progress_overlay_dark_theme_toggle(self) -> None:
        from mochi.presence.bond_progress_overlay import BondProgressOverlay

        owner = Gtk.Window()
        anchor = Gtk.Box()

        overlay_light = BondProgressOverlay(owner=owner, anchor_widget=anchor, dark_theme=False)
        self.assertFalse(overlay_light._window.has_css_class("mochi-dark-theme"))
        self.assertFalse(overlay_light._popover.has_css_class("mochi-dark-theme"))

        overlay_light.set_dark_theme(True)
        self.assertTrue(overlay_light._window.has_css_class("mochi-dark-theme"))
        self.assertTrue(overlay_light._popover.has_css_class("mochi-dark-theme"))

        overlay_light.set_dark_theme(False)
        self.assertFalse(overlay_light._window.has_css_class("mochi-dark-theme"))
        self.assertFalse(overlay_light._popover.has_css_class("mochi-dark-theme"))

        overlay_dark = BondProgressOverlay(owner=owner, anchor_widget=anchor, dark_theme=True)
        self.assertTrue(overlay_dark._window.has_css_class("mochi-dark-theme"))
        self.assertTrue(overlay_dark._popover.has_css_class("mochi-dark-theme"))

    def test_quick_start_window_dark_theme_toggle(self) -> None:
        from mochi.quick_start import QuickStartWindow

        owner = Gtk.Window()
        qs_light = QuickStartWindow(owner=owner, dark_theme=False)
        self.assertFalse(qs_light.window.has_css_class("mochi-dark-theme"))

        qs_light.set_dark_theme(True)
        self.assertTrue(qs_light.window.has_css_class("mochi-dark-theme"))

        qs_light.set_dark_theme(False)
        self.assertFalse(qs_light.window.has_css_class("mochi-dark-theme"))

        qs_dark = QuickStartWindow(owner=owner, dark_theme=True)
        self.assertTrue(qs_dark.window.has_css_class("mochi-dark-theme"))

    def test_focus_window_dark_theme_toggle(self) -> None:
        from mochi.presence.focus_session import FocusWindow

        owner = Gtk.Window()
        fw_light = FocusWindow(
            owner=owner,
            on_start=Mock(),
            on_pause=Mock(),
            on_cancel=Mock(),
            on_hidden=Mock(),
            on_rain_enabled=Mock(),
            on_rain_volume_changed=Mock(),
            rain_available=False,
            rain_enabled=False,
            rain_volume=0.5,
            dark_theme=False,
        )
        self.assertFalse(fw_light.window.has_css_class("mochi-dark-theme"))

        fw_light.set_dark_theme(True)
        self.assertTrue(fw_light.window.has_css_class("mochi-dark-theme"))

        fw_light.set_dark_theme(False)
        self.assertFalse(fw_light.window.has_css_class("mochi-dark-theme"))

        fw_dark = FocusWindow(
            owner=owner,
            on_start=Mock(),
            on_pause=Mock(),
            on_cancel=Mock(),
            on_hidden=Mock(),
            on_rain_enabled=Mock(),
            on_rain_volume_changed=Mock(),
            rain_available=False,
            rain_enabled=False,
            rain_volume=0.5,
            dark_theme=True,
        )
        self.assertTrue(fw_dark.window.has_css_class("mochi-dark-theme"))


if __name__ == "__main__":
    unittest.main()
