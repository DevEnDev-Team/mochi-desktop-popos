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

        # Toggle to False
        controller._toggle_dark_theme()
        self.assertFalse(mock_buddy._dark_theme)
        self.assertFalse(switch.get_active())
        mock_buddy._config.save_dark_theme.assert_called_with(False)
        mock_context_menu.set_dark_theme.assert_called_with(False)
        mock_dev_menu.set_dark_theme.assert_called_with(False)
        mock_bubble.set_dark_theme.assert_called_with(False)
        mock_catalogue.set_dark_theme.assert_called_with(False)


if __name__ == "__main__":
    unittest.main()
