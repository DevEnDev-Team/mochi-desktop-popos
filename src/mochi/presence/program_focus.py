"""Program focus detection and emote triggering for Mochi."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import ctypes
import ctypes.util
import logging
import os
import subprocess
import sys
import threading
import time

from gi.repository import GLib

_XERRORHANDLER_T = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)


def _ignore_x11_error(_display: ctypes.c_void_p, _event: ctypes.c_void_p) -> int:
    return 0


_c_ignore_x11_error = _XERRORHANDLER_T(_ignore_x11_error)

try:
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi
    HAS_ATSPI = True
except Exception:
    HAS_ATSPI = False

from mochi.emotes import EMOTE_CATALOGUE, EmoteDefinition

# Known category aliases so general terms like "terminal" or "browser"
# automatically match popular program names.
CATEGORY_APP_MAP: dict[str, frozenset[str]] = {
    "terminal": frozenset((
        "terminal", "kitty", "alacritty", "gnome-terminal", "konsole",
        "xterm", "cosmic-term", "wezterm", "foot", "urxvt", "pty",
        "tilix", "terminator", "xfce4-terminal",
    )),
    "vscode": frozenset((
        "code", "vscode", "visual studio code", "cursor", "vscodium", "code-oss",
    )),
    "browser": frozenset((
        "firefox", "chrome", "google-chrome", "chromium", "brave",
        "microsoft-edge", "edge", "vivaldi", "opera", "epiphany",
    )),
    "editor": frozenset((
        "gedit", "kate", "subl", "sublime_text", "atom", "texteditor",
        "xed", "mousepad", "featherpad", "pluma", "emacs", "vim", "nvim",
    )),
    "media": frozenset((
        "vlc", "mpv", "totem", "celluloid", "spotify", "rhythmbox",
        "showtime", "audacious",
    )),
    "pixel_art": frozenset((
        "aseprite", "pixelorama", "libresprite",
    )),
}


def matches_program(configured_target: str, app_identifiers: Iterable[str]) -> bool:
    """Return whether any candidate app identifier matches the configured program.

    Matching is case-insensitive and tolerant of extensions (.desktop, .exe).
    It supports category aliases (e.g. 'terminal' matching 'kitty') and substring matching.
    """
    target = configured_target.strip().lower()
    if not target:
        return False

    target_clean = target.removesuffix(".desktop").removesuffix(".exe")

    # If target is a category or known group
    category_members = CATEGORY_APP_MAP.get(target_clean, frozenset())

    for identifier in app_identifiers:
        if not identifier:
            continue
        ident_lower = identifier.strip().lower()
        ident_clean = ident_lower.removesuffix(".desktop").removesuffix(".exe")

        # Direct match or substring match
        if (
            target_clean == ident_clean
            or target_clean in ident_clean
            or ident_clean in target_clean
        ):
            return True

        # Check if candidate matches any member of the category alias set
        if category_members:
            if any(m == ident_clean or m in ident_clean or ident_clean in m for m in category_members):
                return True

        # Reverse check: if identifier is a category name
        if ident_clean in CATEGORY_APP_MAP:
            if any(m == target_clean or m in target_clean or target_clean in m for m in CATEGORY_APP_MAP[ident_clean]):
                return True

    return False


def get_installed_applications() -> list[tuple[str, str]]:
    """Return a curated list of (display_name, program_id) for UI selection."""
    presets = [
        ("Visual Studio Code (code)", "code"),
        ("Terminal (terminal)", "terminal"),
        ("Navigateur Web (browser)", "browser"),
        ("Firefox (firefox)", "firefox"),
        ("Google Chrome (google-chrome)", "google-chrome"),
        ("Discord (discord)", "discord"),
        ("Éditeur de texte (editor)", "editor"),
        ("Lecteur multimédia (media)", "media"),
        ("GIMP (gimp)", "gimp"),
        ("Blender (blender)", "blender"),
        ("Steam (steam)", "steam"),
    ]

    discovered: dict[str, str] = {}
    try:
        from gi.repository import Gio
        for app in Gio.AppInfo.get_all():
            if not app.should_show():
                continue
            name = app.get_name()
            app_id = (app.get_id() or "").removesuffix(".desktop").lower()
            exec_name = (app.get_executable() or "").split("/")[-1].lower()
            target_id = exec_name or app_id
            if target_id and name and target_id not in discovered:
                discovered[target_id] = f"{name} ({target_id})"
    except Exception:
        pass

    results = list(presets)
    preset_ids = {p[1] for p in presets}
    for tid in sorted(discovered.keys(), key=lambda k: discovered[k].lower()):
        if tid not in preset_ids:
            results.append((discovered[tid], tid))

    return results


def query_x11_active_window() -> list[str]:
    """Query X11/XWayland active window identifiers via ctypes."""
    library_name = ctypes.util.find_library("X11")
    if library_name is None:
        return []

    try:
        x11 = ctypes.CDLL(library_name)
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        display = x11.XOpenDisplay(None)
        if not display:
            return []

        x11.XDefaultScreen.argtypes = [ctypes.c_void_p]
        x11.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x11.XRootWindow.restype = ctypes.c_ulong
        x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        x11.XInternAtom.restype = ctypes.c_ulong
        x11.XGetWindowProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long,
            ctypes.c_long, ctypes.c_int, ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XSetErrorHandler.argtypes = [ctypes.c_void_p]
        x11.XSetErrorHandler.restype = ctypes.c_void_p
        x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]

        prev_handler = x11.XSetErrorHandler(_c_ignore_x11_error)
        try:
            root = x11.XRootWindow(display, x11.XDefaultScreen(display))
            atom_active = x11.XInternAtom(display, b"_NET_ACTIVE_WINDOW", False)
            atom_class = x11.XInternAtom(display, b"WM_CLASS", False)
            atom_pid = x11.XInternAtom(display, b"_NET_WM_PID", False)
            atom_name = x11.XInternAtom(display, b"_NET_WM_NAME", False)

            def _get(w, atom, req_type, length=1024):
                actual_type = ctypes.c_ulong()
                actual_format = ctypes.c_int()
                nitems = ctypes.c_ulong()
                bytes_after = ctypes.c_ulong()
                prop = ctypes.c_void_p()
                ret = x11.XGetWindowProperty(
                    display, w, atom, 0, length, False, req_type,
                    ctypes.byref(actual_type), ctypes.byref(actual_format),
                    ctypes.byref(nitems), ctypes.byref(bytes_after), ctypes.byref(prop)
                )
                if ret == 0 and prop.value:
                    return prop, nitems.value
                return None, 0

            identifiers: list[str] = []
            p_act, _ = _get(root, atom_active, 33, 1)  # XA_WINDOW=33
            if p_act:
                win_id = ctypes.cast(p_act, ctypes.POINTER(ctypes.c_ulong)).contents.value
                if win_id != 0:
                    p_cls, n_cls = _get(win_id, atom_class, 31)  # XA_STRING=31
                    if p_cls:
                        raw = ctypes.string_at(p_cls.value, n_cls)
                        classes = [s.decode("utf-8", errors="ignore") for s in raw.split(b"\x00") if s]
                        identifiers.extend(classes)

                    p_pid, _ = _get(win_id, atom_pid, 6, 1)  # XA_CARDINAL=6
                    if p_pid:
                        pid = ctypes.cast(p_pid, ctypes.POINTER(ctypes.c_ulong)).contents.value
                        comm_path = f"/proc/{pid}/comm"
                        if os.path.exists(comm_path):
                            try:
                                with open(comm_path, encoding="utf-8") as f:
                                    comm = f.read().strip()
                                    if comm:
                                        identifiers.append(comm)
                            except Exception:
                                pass

                    p_name, n_name = _get(win_id, atom_name, 0)
                    if p_name:
                        raw_name = ctypes.string_at(p_name.value, n_name).decode("utf-8", errors="ignore")
                        if raw_name:
                            identifiers.append(raw_name)
            x11.XSync(display, False)
            return identifiers
        finally:
            x11.XSetErrorHandler(prev_handler)
            x11.XCloseDisplay(display)
    except Exception:
        return []


def query_atspi_active_window() -> list[str]:
    """Query currently focused/active desktop application via AT-SPI."""
    if not HAS_ATSPI:
        return []
    try:
        count = Atspi.get_desktop_count()
        for d_idx in range(count):
            desktop = Atspi.get_desktop(d_idx)
            if not desktop:
                continue
            child_count = desktop.get_child_count()
            for i in range(child_count):
                app = desktop.get_child_at_index(i)
                if not app:
                    continue
                app_name = app.get_name() or ""
                win_count = app.get_child_count()
                for j in range(win_count):
                    win = app.get_child_at_index(j)
                    if not win:
                        continue
                    try:
                        st = win.get_state_set()
                        if st.contains(Atspi.StateType.ACTIVE) or st.contains(
                            Atspi.StateType.FOCUSED
                        ):
                            win_name = win.get_name() or ""
                            idents = [app_name]
                            if win_name and win_name != app_name:
                                idents.append(win_name)
                            return [x for x in idents if x]
                    except Exception:
                        continue
    except Exception:
        pass
    return []


class ProgramFocusMonitor:
    """Monitor window focus changes across X11, Wayland, and GNOME Shell without blocking."""

    POLL_INTERVAL_MS = 400

    def __init__(
        self,
        *,
        on_program_focused: Callable[[list[str]], None],
        logger: logging.Logger | None = None,
    ) -> None:
        self._on_program_focused = on_program_focused
        self._logger = logger or logging.getLogger(__name__)
        self._poll_source_id: int | None = None
        self._last_identifiers: list[str] = []
        self._running = False
        self._worker_process: subprocess.Popen | None = None
        self._worker_thread: threading.Thread | None = None

    def start(self) -> bool:
        if self._running:
            return True
        self._running = True

        # Start isolated AT-SPI focus monitor in an independent child process
        self._start_worker_process()

        self._poll_source_id = GLib.timeout_add(
            self.POLL_INTERVAL_MS,
            self._poll_focus,
            priority=GLib.PRIORITY_LOW,
        )
        return True

    def _start_worker_process(self) -> None:
        try:
            worker_path = os.path.join(
                os.path.dirname(__file__), "focus_worker.py"
            )
            if not os.path.exists(worker_path):
                return
            proc = subprocess.Popen(
                [sys.executable, worker_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            self._worker_process = proc
            thread = threading.Thread(
                target=self._read_worker_output,
                args=(proc,),
                daemon=True,
            )
            self._worker_thread = thread
            thread.start()
        except Exception as exc:
            self._logger.debug("Failed to spawn focus worker: %s", exc)

    def _read_worker_output(self, proc: subprocess.Popen) -> None:
        try:
            for line in iter(proc.stdout.readline, ""):
                if not self._running:
                    break
                line = line.strip()
                if not line or line == "READY":
                    continue
                if line.startswith("FOCUS\t"):
                    parts = [p.strip() for p in line.split("\t")[1:] if p.strip()]
                    GLib.idle_add(self._handle_worker_focus, parts)
                elif line == "DEFOCUS":
                    GLib.idle_add(self._handle_worker_focus, [])
        except Exception:
            pass

    def _handle_worker_focus(self, idents: list[str]) -> bool:
        if not self._running:
            return GLib.SOURCE_REMOVE
        if idents != self._last_identifiers:
            self._last_identifiers = list(idents)
            self._process_identifiers(idents)
        return GLib.SOURCE_REMOVE

    def stop(self) -> None:
        self._running = False
        if self._poll_source_id is not None:
            try:
                GLib.source_remove(self._poll_source_id)
            except Exception:
                pass
            self._poll_source_id = None

        if self._worker_process is not None:
            try:
                self._worker_process.terminate()
                self._worker_process.wait(timeout=0.2)
            except Exception:
                pass
            self._worker_process = None

        self._last_identifiers.clear()

    def notify_app_category(self, category: str) -> None:
        """Receive external app category notifications (e.g. from GNOME extension)."""
        if not self._running or not category or category == "unknown":
            return
        self._process_identifiers([category])

    def _poll_focus(self) -> bool:
        if not self._running:
            return GLib.SOURCE_REMOVE
        try:
            identifiers = query_x11_active_window()
            if identifiers and identifiers != self._last_identifiers:
                self._last_identifiers = list(identifiers)
                self._process_identifiers(identifiers)
        except Exception as exc:
            self._logger.debug("Focus polling error: %s", exc)
        return GLib.SOURCE_CONTINUE

    def _process_identifiers(self, identifiers: list[str]) -> None:
        # Ignore focus transitions to Mochi itself
        if any(
            i.lower() in ("mochi", "mochi-desktop", "mochi desktop")
            for i in identifiers
        ):
            return

        cleaned = [i for i in identifiers if i.strip()]
        self._on_program_focused(cleaned)
