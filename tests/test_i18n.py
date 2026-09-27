"""Tests for Mochi's internationalization (i18n) system."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from mochi.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    detect_system_language,
    get_language,
    set_language,
    tr,
)
from mochi.presence.phrases import PhraseBank


class I18nTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_lang = get_language()

    def tearDown(self) -> None:
        set_language(self.original_lang)

    def test_languages_dict(self) -> None:
        self.assertIn("en", LANGUAGES)
        self.assertIn("fr", LANGUAGES)
        self.assertEqual(LANGUAGES["en"], "English")
        self.assertEqual(LANGUAGES["fr"], "Français")

    def test_set_and_get_language(self) -> None:
        set_language("fr")
        self.assertEqual(get_language(), "fr")
        set_language("en")
        self.assertEqual(get_language(), "en")
        # Unknown language resets to default
        set_language("de")
        self.assertEqual(get_language(), DEFAULT_LANGUAGE)

    def test_detect_system_language(self) -> None:
        with patch.dict(os.environ, {"LANG": "fr_FR.UTF-8"}):
            self.assertEqual(detect_system_language(), "fr")

        with patch.dict(os.environ, {"LANG": "en_US.UTF-8", "LC_ALL": "", "LC_MESSAGES": ""}):
            self.assertEqual(detect_system_language(), "en")

    def test_tr_english(self) -> None:
        set_language("en")
        self.assertEqual(tr("menu.sleep"), "Sleep")
        self.assertEqual(tr("menu.feed"), "Feed")
        self.assertEqual(tr("menu.close"), "Close")
        self.assertEqual(tr("menu.bond_level", level=2), "Bond Lv. 2")
        self.assertEqual(tr("dialogue.wheee"), "wheee!")

    def test_tr_french(self) -> None:
        set_language("fr")
        self.assertEqual(tr("menu.sleep"), "Dormir")
        self.assertEqual(tr("menu.feed"), "Nourrir")
        self.assertEqual(tr("menu.close"), "Fermer")
        self.assertEqual(tr("menu.emotes"), "Émotes")
        self.assertEqual(tr("menu.stay_put"), "Ne pas bouger")
        self.assertEqual(tr("menu.bond_level", level=3), "Lien Niv. 3")
        self.assertEqual(tr("dialogue.wheee"), "ouiii !")

    def test_tr_fallback_for_unknown_key(self) -> None:
        set_language("fr")
        self.assertEqual(tr("unknown.key.here"), "unknown.key.here")

    def test_phrase_bank_french_phrases(self) -> None:
        bank = PhraseBank()
        
        set_language("en")
        en_phrase = bank.choose("startup")
        self.assertIsInstance(en_phrase, str)
        self.assertTrue(len(en_phrase) > 0)
        
        set_language("fr")
        fr_phrase = bank.choose("startup")
        self.assertIsInstance(fr_phrase, str)
        self.assertTrue(len(fr_phrase) > 0)

        # Context phrase
        fr_context = bank.choose_context("build_succeeded")
        self.assertIn(fr_context, (
            "build réussi ! 🎉",
            "tout compile à merveille",
            "zéro erreur, que du bonheur",
        ))

    def test_toggle_language_controller(self) -> None:
        from unittest.mock import Mock
        from mochi.buddy_menu import BuddyMenuController

        mock_buddy = Mock()
        mock_buddy._config = Mock()
        mock_buddy._logger = Mock()

        controller = BuddyMenuController(mock_buddy)
        controller._rebuild_context_menu = Mock()

        set_language("en")
        controller._toggle_language()
        self.assertEqual(get_language(), "fr")
        mock_buddy._config.save_language.assert_called_with("fr")
        controller._rebuild_context_menu.assert_called_once()

        controller._toggle_language()
        self.assertEqual(get_language(), "en")
        mock_buddy._config.save_language.assert_called_with("en")


if __name__ == "__main__":
    unittest.main()
