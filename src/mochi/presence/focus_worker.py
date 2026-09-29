"""Background AT-SPI window focus monitor process.

Runs in an isolated child process to prevent any AT-SPI / D-Bus synchronous
calls from deadlocking or stalling the main GTK4 application event loop.
"""

from __future__ import annotations

import sys


def main() -> None:
    try:
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi, GLib
    except Exception as exc:
        sys.stderr.write(f"AT-SPI unavailable in worker: {exc}\n")
        sys.exit(1)

    try:
        Atspi.init()
    except Exception as exc:
        sys.stderr.write(f"Atspi.init failed: {exc}\n")
        sys.exit(1)

    last_active = ""

    def emit_focus(app_name: str, win_name: str = "") -> None:
        nonlocal last_active
        key = f"{app_name}|{win_name}"
        if key != last_active:
            last_active = key
            sys.stdout.write(f"FOCUS\t{app_name}\t{win_name}\n")
            sys.stdout.flush()

    def emit_defocus() -> None:
        nonlocal last_active
        if last_active:
            last_active = ""
            sys.stdout.write("DEFOCUS\n")
            sys.stdout.flush()

    def on_window_activate(event) -> None:
        try:
            src = getattr(event, "source", None)
            if not src:
                return
            app = src.get_application() if hasattr(src, "get_application") else None
            app_name = app.get_name() if app else ""
            win_name = src.get_name() or ""
            if app_name:
                emit_focus(app_name, win_name)
        except Exception:
            pass

    def check_active_window() -> bool:
        try:
            d = Atspi.get_desktop(0)
            if not d:
                return True
            for i in range(d.get_child_count()):
                app = d.get_child_at_index(i)
                if not app:
                    continue
                app_name = app.get_name() or ""
                for j in range(app.get_child_count()):
                    win = app.get_child_at_index(j)
                    if not win:
                        continue
                    st = win.get_state_set()
                    if st.contains(Atspi.StateType.ACTIVE) or st.contains(Atspi.StateType.FOCUSED):
                        win_name = win.get_name() or ""
                        emit_focus(app_name, win_name)
                        return True
            emit_defocus()
        except Exception:
            pass
        return True

    listener = Atspi.EventListener.new(on_window_activate)
    listener.register("window:activate")

    # Regular fallback check every 350ms in case an activation event was missed
    GLib.timeout_add(350, check_active_window)

    sys.stdout.write("READY\n")
    sys.stdout.flush()

    loop = GLib.MainLoop()
    try:
        loop.run()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
