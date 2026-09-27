"""Internationalization (i18n) support for Mochi."""

from __future__ import annotations

import locale
import os
from typing import Any

LANGUAGES = {
    "en": "English",
    "fr": "Français",
}

DEFAULT_LANGUAGE = "en"
_current_language = DEFAULT_LANGUAGE

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # Context menu
        "menu.title": "Mochi",
        "menu.subtitle": "your tiny desktop buddy",
        "menu.sleep": "Sleep",
        "menu.wake_up": "Wake up",
        "menu.close": "Close",
        "menu.feed": "Feed",
        "menu.emotes": "Emotes",
        "menu.stay_put": "Stay put",
        "menu.stay_put_tooltip": "Prevent Mochi from wandering on his own",
        "menu.edge_roam": "Edge roam",
        "menu.edge_roam_tooltip": "Keep Mochi's autonomous wandering along the screen edge",
        "menu.focus": "Focus with Mochi",
        "menu.focus_tooltip": "Start a gentle focus session with Mochi",
        "menu.language": "Language: English",
        "menu.language_switch": "Français",
        "menu.language_tooltip": "Switch to French",
        "menu.dark_theme": "Dark theme",
        "menu.dark_theme_tooltip": "Toggle dark theme for menu and speech bubbles",
        "menu.quick_start": "What can Mochi do?",
        "menu.quick_start_tooltip": "A quick introduction to Mochi",
        "menu.check_updates": "Check for updates",
        "menu.status_title": "Mochi status",
        "menu.status_state": "MochiState",
        "menu.status_mood": "Mood",
        "menu.bond_level": "Bond Lv. {level}",
        
        # Dialogue & Reactions
        "dialogue.wheee": "wheee!",
        "click.owie": "owie!",
        "click.soft": "hey, i'm soft!",
        "click.gentle": "gentle!",
        "click.eep": "eep!",
        "click.tiny_creature": "tiny creature here!",
        
        # Emote catalogue
        "catalogue.title": "Mochi Emote Catalogue",
        "catalogue.header_title": "Emote Catalogue",
        "catalogue.unlocked": "UNLOCKED",
        "catalogue.coming_soon": "COMING SOON",
        "catalogue.bond_req": "BOND LV. {level}",
        "catalogue.page": "Page {current} of {total}",
        "catalogue.prev_tooltip": "Previous emote page",
        "catalogue.next_tooltip": "Next emote page",
        "catalogue.all_unlocked_dev": "Bond Lv. {level} · all available emotes unlocked (developer) ✦",
        "catalogue.all_unlocked": "Bond Lv. {level} · all current emotes unlocked ✦",
        "catalogue.next_unlock": "Bond Lv. {level} · Next: {name} at Lv. {target} · {remaining:,} XP to go",
    },
    "fr": {
        # Menu contextuel
        "menu.title": "Mochi",
        "menu.subtitle": "ton petit compagnon de bureau",
        "menu.sleep": "Dormir",
        "menu.wake_up": "Se réveiller",
        "menu.close": "Fermer",
        "menu.feed": "Nourrir",
        "menu.emotes": "Émotes",
        "menu.stay_put": "Ne pas bouger",
        "menu.stay_put_tooltip": "Empêcher Mochi de se déplacer tout seul",
        "menu.edge_roam": "Rôder sur les bords",
        "menu.edge_roam_tooltip": "Garder les déplacements de Mochi le long des bords de l'écran",
        "menu.focus": "Session focus avec Mochi",
        "menu.focus_tooltip": "Démarrer une session de concentration avec Mochi",
        "menu.language": "Langue : Français",
        "menu.language_switch": "English",
        "menu.language_tooltip": "Passer en anglais",
        "menu.dark_theme": "Thème sombre",
        "menu.dark_theme_tooltip": "Activer ou désactiver le thème sombre pour le menu et les bulles de discussion",
        "menu.quick_start": "Que sait faire Mochi ?",
        "menu.quick_start_tooltip": "Une brève introduction à Mochi",
        "menu.check_updates": "Vérifier les mises à jour",
        "menu.status_title": "Statut de Mochi",
        "menu.status_state": "État",
        "menu.status_mood": "Humeur",
        "menu.bond_level": "Lien Niv. {level}",
        
        # Dialogues et réactions
        "dialogue.wheee": "ouiii !",
        "click.owie": "aïe !",
        "click.soft": "hé, je suis tout mou !",
        "click.gentle": "doucement !",
        "click.eep": "oups !",
        "click.tiny_creature": "attention, créature fragile !",
        
        # Catalogue d'émotes
        "catalogue.title": "Catalogue d'émotes de Mochi",
        "catalogue.header_title": "Catalogue d'émotes",
        "catalogue.unlocked": "DÉBLOQUÉ",
        "catalogue.coming_soon": "BIENTÔT",
        "catalogue.bond_req": "LIEN NIV. {level}",
        "catalogue.page": "Page {current} sur {total}",
        "catalogue.prev_tooltip": "Page d'émotes précédente",
        "catalogue.next_tooltip": "Page d'émotes suivante",
        "catalogue.all_unlocked_dev": "Lien Niv. {level} · toutes les émotes disponibles débloquées (développeur) ✦",
        "catalogue.all_unlocked": "Lien Niv. {level} · toutes les émotes actuelles débloquées ✦",
        "catalogue.next_unlock": "Lien Niv. {level} · Suivant : {name} au Niv. {target} · {remaining:,} XP restants",
    },
}


def detect_system_language() -> str:
    """Detect whether system language is French or defaults to English."""
    for env_var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(env_var, "").strip()
        if val:
            return "fr" if val.casefold().startswith("fr") else "en"
    try:
        loc = locale.getlocale()[0]
        if loc and loc.casefold().startswith("fr"):
            return "fr"
    except Exception:
        pass
    return "en"


def get_language() -> str:
    """Return the currently active language code ('en' or 'fr')."""
    return _current_language


def set_language(lang: str) -> str:
    """Set the currently active language code."""
    global _current_language
    if lang in LANGUAGES:
        _current_language = lang
    else:
        _current_language = DEFAULT_LANGUAGE
    return _current_language


def tr(key: str, **kwargs: Any) -> str:
    """Translate a text key with optional formatting arguments."""
    lang_dict = TRANSLATIONS.get(_current_language, TRANSLATIONS["en"])
    text = lang_dict.get(key)
    if text is None:
        text = TRANSLATIONS["en"].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
