"""Manage XDG autostart configuration for Mochi."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import shutil
import sys

logger = logging.getLogger(__name__)

AUTOSTART_FILENAME = "io.github.mochi_desktop.Mochi.desktop"


def get_autostart_dir(config_home: Path | None = None) -> Path:
    """Return the XDG autostart directory path."""
    base = config_home or Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "autostart"


def get_autostart_file_path(config_home: Path | None = None) -> Path:
    """Return the desktop file path for Mochi's autostart entry."""
    return get_autostart_dir(config_home) / AUTOSTART_FILENAME


def get_mochi_executable() -> str:
    """Resolve the best command or executable path to launch Mochi."""
    # 1. Check if the installed desktop file exists and extract its Exec command
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    installed_desktop = data_home / "applications" / AUTOSTART_FILENAME
    if installed_desktop.is_file():
        try:
            for line in installed_desktop.read_text(encoding="utf-8").splitlines():
                if line.startswith("Exec="):
                    exec_val = line[len("Exec="):].strip()
                    if exec_val:
                        return exec_val
        except OSError as err:
            logger.debug("Failed to read installed desktop file %s: %s", installed_desktop, err)

    # 2. Check if 'mochi' is found in PATH
    which_mochi = shutil.which("mochi")
    if which_mochi:
        return which_mochi

    # 3. Check ~/.local/bin/mochi
    local_bin_mochi = Path.home() / ".local" / "bin" / "mochi"
    if local_bin_mochi.is_file() and os.access(local_bin_mochi, os.X_OK):
        return str(local_bin_mochi)

    # 4. Check sys.prefix/bin/mochi
    prefix_bin_mochi = Path(sys.prefix) / "bin" / "mochi"
    if prefix_bin_mochi.is_file() and os.access(prefix_bin_mochi, os.X_OK):
        return str(prefix_bin_mochi)

    # 5. Fallback to current python module execution
    return f"{sys.executable} -m mochi"


def is_autostart_enabled(path: Path | None = None) -> bool:
    """Check whether autostart is currently enabled."""
    target = path or get_autostart_file_path()
    if not target.is_file():
        return False

    try:
        content = target.read_text(encoding="utf-8")
        lines = [line.strip().casefold() for line in content.splitlines()]
        if "hidden=true" in lines:
            return False
        if "x-gnome-autostart-enabled=false" in lines:
            return False
        return True
    except OSError as err:
        logger.warning("Could not read autostart file %s: %s", target, err)
        return False


def set_autostart_enabled(
    enabled: bool,
    path: Path | None = None,
    exec_cmd: str | None = None,
) -> bool:
    """Enable or disable autostart at login."""
    target = path or get_autostart_file_path()

    if enabled:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            executable = exec_cmd or get_mochi_executable()
            desktop_content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Mochi\n"
                "GenericName=Desktop Companion\n"
                "Comment=A tiny friend for your Linux desktop\n"
                f"Exec={executable}\n"
                "Icon=io.github.mochi_desktop.Mochi\n"
                "Terminal=false\n"
                "Categories=Utility;Game;\n"
                "Keywords=desktop;companion;pet;mochi;\n"
                "StartupNotify=false\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
            target.write_text(desktop_content, encoding="utf-8")
            logger.info("Autostart desktop entry created at %s", target)
            return True
        except OSError as err:
            logger.error("Failed to enable autostart at %s: %s", target, err)
            return False
    else:
        try:
            if target.is_file():
                target.unlink()
                logger.info("Autostart desktop entry removed from %s", target)
            return True
        except OSError as err:
            logger.error("Failed to remove autostart file %s: %s", target, err)
            return False
