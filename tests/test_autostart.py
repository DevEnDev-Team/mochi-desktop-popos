"""Comprehensive unit tests for Mochi's autostart configuration and menu option."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk  # noqa: E402

from mochi.autostart import (
    AUTOSTART_FILENAME,
    get_autostart_dir,
    get_autostart_file_path,
    get_mochi_executable,
    is_autostart_enabled,
    set_autostart_enabled,
)
from mochi.buddy_menu import BuddyMenuController
from mochi.config import ConfigStore
from mochi.i18n import get_language, set_language, tr


class AutostartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_get_autostart_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_home = Path(tmpdir)
            autostart_dir = get_autostart_dir(config_home)
            self.assertEqual(autostart_dir, config_home / "autostart")

            autostart_file = get_autostart_file_path(config_home)
            self.assertEqual(autostart_file, config_home / "autostart" / AUTOSTART_FILENAME)

    def test_get_mochi_executable_from_desktop_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_data_home = Path(tmpdir)
            apps_dir = fake_data_home / "applications"
            apps_dir.mkdir(parents=True)
            desktop_file = apps_dir / AUTOSTART_FILENAME
            desktop_file.write_text(
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Exec=/custom/path/to/mochi --flag\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"XDG_DATA_HOME": str(fake_data_home)}):
                exe = get_mochi_executable()
                self.assertEqual(exe, "/custom/path/to/mochi --flag")

    def test_get_mochi_executable_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_data_home = Path(tmpdir)
            with patch.dict("os.environ", {"XDG_DATA_HOME": str(fake_data_home)}):
                # When desktop file doesn't exist, which returns a path
                with patch("shutil.which", return_value="/bin/mochi"):
                    self.assertEqual(get_mochi_executable(), "/bin/mochi")

                # When which returns None
                with patch("shutil.which", return_value=None):
                    with patch("pathlib.Path.is_file", return_value=False):
                        exe = get_mochi_executable()
                        self.assertIn("-m mochi", exe)

    def test_is_autostart_enabled_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            autostart_file = Path(tmpdir) / "autostart" / AUTOSTART_FILENAME
            self.assertFalse(is_autostart_enabled(autostart_file))

    def test_set_autostart_enabled_creates_valid_desktop_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            autostart_file = Path(tmpdir) / "autostart" / AUTOSTART_FILENAME
            self.assertFalse(is_autostart_enabled(autostart_file))

            success = set_autostart_enabled(
                True,
                path=autostart_file,
                exec_cmd="/usr/bin/mochi",
            )
            self.assertTrue(success)
            self.assertTrue(autostart_file.is_file())
            self.assertTrue(is_autostart_enabled(autostart_file))

            content = autostart_file.read_text(encoding="utf-8")
            self.assertIn("[Desktop Entry]", content)
            self.assertIn("Exec=/usr/bin/mochi", content)
            self.assertIn("X-GNOME-Autostart-enabled=true", content)

    def test_set_autostart_disabled_removes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            autostart_file = Path(tmpdir) / "autostart" / AUTOSTART_FILENAME
            set_autostart_enabled(True, path=autostart_file, exec_cmd="/usr/bin/mochi")
            self.assertTrue(autostart_file.is_file())

            success = set_autostart_enabled(False, path=autostart_file)
            self.assertTrue(success)
            self.assertFalse(autostart_file.exists())
            self.assertFalse(is_autostart_enabled(autostart_file))

    def test_is_autostart_enabled_respects_hidden_and_gnome_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            autostart_file = Path(tmpdir) / "autostart" / AUTOSTART_FILENAME
            autostart_file.parent.mkdir(parents=True)

            # Hidden=true
            autostart_file.write_text("[Desktop Entry]\nHidden=true\n", encoding="utf-8")
            self.assertFalse(is_autostart_enabled(autostart_file))

            # X-GNOME-Autostart-enabled=false
            autostart_file.write_text(
                "[Desktop Entry]\nX-GNOME-Autostart-enabled=false\n",
                encoding="utf-8",
            )
            self.assertFalse(is_autostart_enabled(autostart_file))

    def test_config_store_autostart_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            autostart_file = Path(tmpdir) / "autostart" / AUTOSTART_FILENAME
            store = ConfigStore(path=config_file, autostart_path=autostart_file)

            self.assertFalse(store.load_autostart())

            store.save_autostart(True)
            self.assertTrue(store.load_autostart())
            self.assertTrue(autostart_file.is_file())

            store.save_autostart(False)
            self.assertFalse(store.load_autostart())
            self.assertFalse(autostart_file.exists())

    def test_buddy_menu_controller_autostart_row_and_toggle(self) -> None:
        mock_buddy = Mock()
        mock_buddy._autostart_enabled = False
        mock_buddy._config = Mock()
        mock_buddy._logger = Mock()

        controller = BuddyMenuController(mock_buddy)
        button, switch = controller._make_autostart_row()

        self.assertIsInstance(button, Gtk.Button)
        self.assertIsInstance(switch, Gtk.Switch)
        self.assertFalse(switch.get_active())

        mock_buddy._autostart_switch = switch

        # Toggle to True
        controller._toggle_autostart()
        self.assertTrue(mock_buddy._autostart_enabled)
        self.assertTrue(switch.get_active())
        mock_buddy._config.save_autostart.assert_called_with(True)

        # Toggle to False
        controller._toggle_autostart()
        self.assertFalse(mock_buddy._autostart_enabled)
        self.assertFalse(switch.get_active())
        mock_buddy._config.save_autostart.assert_called_with(False)

    def test_autostart_row_registered_in_context_menu(self) -> None:
        mock_buddy = Mock()
        mock_buddy._window = Gtk.Window()
        mock_buddy.get_width.return_value = 112
        mock_buddy.get_height.return_value = 112
        mock_buddy._dark_theme = False
        mock_buddy._autostart_enabled = False
        mock_buddy.CONTEXT_MENU_WIDTH = 244
        mock_buddy.CONTEXT_MENU_BASE_HEIGHT = 176
        mock_buddy.CONTEXT_MENU_UNKNOWN_ROW_HEIGHT = 44
        mock_buddy.CONTEXT_MENU_MIN_HEIGHTS = {}
        mock_buddy.CONTEXT_MENU_BASE_SIZED_ROWS = frozenset()
        mock_buddy._context_menu_rows = {}
        mock_buddy._context_menu_row_order = []
        mock_buddy._context_menu_animated_row_ids = set()

        controller = BuddyMenuController(mock_buddy)
        mock_buddy._initialize_context_menu_layout = controller._initialize_context_menu_layout
        mock_buddy._register_context_menu_row = controller._register_context_menu_row
        mock_buddy._recalculate_context_menu_layout = controller._recalculate_context_menu_layout

        def make_menu_button(label, icon_name, callback, destructive=False):
            return Gtk.Button(), Gtk.Label(label=label)

        mock_buddy._make_menu_button = make_menu_button

        menu = controller._build_context_menu()
        self.assertIsNotNone(menu)

        # Ensure autostart row is registered in the layout
        self.assertIn("autostart", mock_buddy._context_menu_rows)
        # Ensure autostart is placed before "close"
        autostart_idx = mock_buddy._context_menu_row_order.index("autostart")
        close_idx = mock_buddy._context_menu_row_order.index("close")
        self.assertLess(autostart_idx, close_idx)

    def test_i18n_autostart_translations(self) -> None:
        initial_lang = get_language()
        try:
            set_language("en")
            self.assertEqual(tr("menu.autostart"), "Start at login")
            self.assertEqual(
                tr("menu.autostart_tooltip"),
                "Launch Mochi automatically when you log in",
            )

            set_language("fr")
            self.assertEqual(tr("menu.autostart"), "Lancer au démarrage")
            self.assertEqual(
                tr("menu.autostart_tooltip"),
                "Lancer Mochi automatiquement à l'ouverture de session",
            )
        finally:
            set_language(initial_lang)


if __name__ == "__main__":
    unittest.main()
