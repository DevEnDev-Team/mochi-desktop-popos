import logging
import unittest

from mochi.typing_activity import (
    AtspiDeviceActivityBackend,
    AtspiTextActivityBackend,
    CosmicCompKeyboardBackend,
    GnomeShellTypingPulseBackend,
    TypingActivityMonitor,
    TypingBurstDetector,
)


class TypingBurstDetectorTests(unittest.TestCase):
    def test_shortcut_sized_burst_does_not_start_typing(self) -> None:
        detector = TypingBurstDetector()
        for timestamp in (1.00, 1.03, 1.06, 1.09):
            self.assertFalse(detector.record_activity(timestamp))
        self.assertFalse(detector.active)

    def test_ultrafast_chord_does_not_start_typing(self) -> None:
        detector = TypingBurstDetector()
        for timestamp in (1.00, 1.02, 1.04, 1.06, 1.08):
            self.assertFalse(detector.record_activity(timestamp))
        self.assertFalse(detector.active)

    def test_sustained_five_event_burst_starts_typing(self) -> None:
        detector = TypingBurstDetector()
        for timestamp in (1.00, 1.10, 1.20, 1.30):
            self.assertFalse(detector.record_activity(timestamp))
        self.assertTrue(detector.record_activity(1.40))
        self.assertTrue(detector.active)

    def test_old_events_roll_out_of_burst_window(self) -> None:
        detector = TypingBurstDetector()
        for timestamp in (1.0, 1.1, 1.2, 2.5, 2.6, 2.7, 2.8):
            self.assertFalse(detector.record_activity(timestamp))
        self.assertTrue(detector.record_activity(2.9))

    def test_end_session_allows_fresh_burst(self) -> None:
        detector = TypingBurstDetector()
        for timestamp in (1.0, 1.1, 1.2, 1.3):
            self.assertFalse(detector.record_activity(timestamp))
        self.assertTrue(detector.record_activity(1.4))
        self.assertTrue(detector.end_session())
        self.assertFalse(detector.end_session())
        for timestamp in (2.0, 2.1, 2.2, 2.3):
            self.assertFalse(detector.record_activity(timestamp))
        self.assertTrue(detector.record_activity(2.4))

    def test_reset_discards_stale_activity(self) -> None:
        detector = TypingBurstDetector()
        for timestamp in (1.0, 1.1, 1.2, 1.3):
            self.assertFalse(detector.record_activity(timestamp))
        detector.reset()
        for timestamp in (1.4, 1.5, 1.6, 1.7):
            self.assertFalse(detector.record_activity(timestamp))
        self.assertTrue(detector.record_activity(1.8))


class _FakeGLib:
    SOURCE_REMOVE = False

    def __init__(self) -> None:
        self._callbacks: dict[int, object] = {}
        self._next_source_id = 1
        self.removed: list[int] = []
        self.last_timeout_ms: int | None = None

    def timeout_add(self, milliseconds: int, callback: object) -> int:
        self.last_timeout_ms = milliseconds
        source_id = self._next_source_id
        self._next_source_id += 1
        self._callbacks[source_id] = callback
        return source_id

    def source_remove(self, source_id: int) -> None:
        self.removed.append(source_id)
        self._callbacks.pop(source_id, None)

    def fire_latest_timer(self) -> None:
        source_id = max(self._callbacks)
        callback = self._callbacks.pop(source_id)
        callback()

    @property
    def timer_count(self) -> int:
        return len(self._callbacks)


class _FakeBackend:
    def __init__(self, name: str, available: bool = True, error: str | None = None):
        self.name = name
        self.available = available
        self.last_error = error
        self.start_calls = 0
        self.stop_calls = 0
        self.callback = None

    def start(self, callback) -> bool:
        self.start_calls += 1
        if not self.available:
            return False
        self.callback = callback
        return True

    def stop(self) -> None:
        self.stop_calls += 1
        self.callback = None

    def emit(self, now: float | None = None) -> None:
        if self.callback is None:
            raise AssertionError("backend is not started")
        self.callback(now)


class _ListLogger(logging.Logger):
    def __init__(self) -> None:
        super().__init__("typing-test")
        self.messages: list[str] = []

    def info(self, msg, *args, **kwargs) -> None:
        self.messages.append(msg % args if args else str(msg))

    def debug(self, msg, *args, **kwargs) -> None:
        self.messages.append(msg % args if args else str(msg))


class TypingActivityMonitorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.activity_calls = 0
        self.stop_calls = 0
        self.glib = _FakeGLib()
        self.backend = _FakeBackend("broad")
        self.monitor = TypingActivityMonitor(
            on_typing_activity=self._record_activity,
            on_typing_stopped=self._record_stop,
            backends=[self.backend],
        )
        self.monitor._glib = self.glib
        self.assertTrue(self.monitor.start())

    def _record_activity(self) -> None:
        self.activity_calls += 1

    def _record_stop(self) -> None:
        self.stop_calls += 1

    def _emit_sustained_typing_burst(self, start: float = 1.0) -> None:
        for offset in (0.0, 0.1, 0.2, 0.3, 0.4):
            self.backend.emit(start + offset)

    def test_shortcut_sized_burst_does_not_trigger_typing(self) -> None:
        for timestamp in (1.00, 1.03, 1.06, 1.09):
            self.backend.emit(timestamp)
        self.assertFalse(self.monitor.active)
        self.assertEqual(self.activity_calls, 0)

    def test_sustained_burst_triggers_typing(self) -> None:
        self._emit_sustained_typing_burst()
        self.assertTrue(self.monitor.active)
        self.assertEqual(self.activity_calls, 1)
        self.assertEqual(self.glib.timer_count, 1)
        self.assertEqual(self.glib.last_timeout_ms, 2250)

    def test_continued_activity_refreshes_same_session(self) -> None:
        self._emit_sustained_typing_burst()
        self.backend.emit(1.5)
        self.assertEqual(self.activity_calls, 2)
        self.assertEqual(self.glib.timer_count, 1)

    def test_inactivity_stops_typing_once(self) -> None:
        self._emit_sustained_typing_burst()
        self.glib.fire_latest_timer()
        self.assertFalse(self.monitor.active)
        self.assertEqual(self.stop_calls, 1)

    def test_reset_requires_fresh_sustained_burst(self) -> None:
        self._emit_sustained_typing_burst()
        self.monitor.reset()
        for timestamp in (2.0, 2.1, 2.2, 2.3):
            self.backend.emit(timestamp)
        self.assertFalse(self.monitor.active)
        self.backend.emit(2.4)
        self.assertTrue(self.monitor.active)

    def test_preferred_backend_prevents_fallback(self) -> None:
        preferred = _FakeBackend("device", available=True)
        fallback = _FakeBackend("text", available=True)
        monitor = TypingActivityMonitor(
            on_typing_activity=lambda: None,
            on_typing_stopped=lambda: None,
            backends=[preferred, fallback],
        )
        monitor._glib = _FakeGLib()
        self.assertTrue(monitor.start())
        self.assertEqual(monitor.backend_name, "device")
        self.assertEqual(preferred.start_calls, 1)
        self.assertEqual(fallback.start_calls, 0)

    def test_default_runtime_prefers_cosmic_then_shell_pulse_then_text_fallback(self) -> None:
        monitor = TypingActivityMonitor(
            on_typing_activity=lambda: None,
            on_typing_stopped=lambda: None,
        )
        self.assertEqual(len(monitor._backends), 3)
        self.assertIsInstance(monitor._backends[0], CosmicCompKeyboardBackend)
        self.assertIsInstance(monitor._backends[1], GnomeShellTypingPulseBackend)
        self.assertIsInstance(monitor._backends[2], AtspiTextActivityBackend)

    def test_failed_preferred_backend_falls_back(self) -> None:
        preferred = _FakeBackend("device", available=False, error="unavailable")
        fallback = _FakeBackend("text", available=True)
        monitor = TypingActivityMonitor(
            on_typing_activity=lambda: None,
            on_typing_stopped=lambda: None,
            backends=[preferred, fallback],
        )
        monitor._glib = _FakeGLib()
        self.assertTrue(monitor.start())
        self.assertEqual(monitor.backend_name, "text")
        self.assertEqual(preferred.start_calls, 1)
        self.assertEqual(fallback.start_calls, 1)

    def test_stop_disconnects_backend_once(self) -> None:
        self.monitor.stop()
        self.monitor.stop()
        self.assertEqual(self.backend.stop_calls, 1)
        self.assertFalse(self.monitor.available)


class GnomeShellTypingPulseBackendTests(unittest.TestCase):
    class _Variant:
        def __init__(self, _signature, value):
            self.value = value

        def unpack(self):
            return self.value

    class _GLib:
        Variant = None

    class _Gio:
        class BusType:
            SESSION = object()

        class DBusCallFlags:
            NONE = object()

        class DBusSignalFlags:
            NONE = object()

        class BusNameWatcherFlags:
            NONE = 0

        @classmethod
        def bus_watch_name_on_connection(cls, connection, name, flags, appeared, vanished):
            if connection.has_owner:
                appeared(connection, name, ":1.42")
            else:
                vanished(connection, name)
            return 1

        @staticmethod
        def bus_unwatch_name(ident):
            pass

        connection = None

        @classmethod
        def bus_get_sync(cls, _bus_type, _cancellable):
            return cls.connection

    class _Connection:
        def __init__(self, *, has_owner=True):
            self.has_owner = has_owner
            self.callback = None
            self.subscribe_args = None
            self.unsubscribed = []

        def call_sync(self, *args):
            return GnomeShellTypingPulseBackendTests._Variant(
                "(b)", (self.has_owner,)
            )

        def signal_subscribe(self, *args):
            self.subscribe_args = args
            self.callback = args[-1]
            return 17

        def signal_unsubscribe(self, subscription_id):
            self.unsubscribed.append(subscription_id)
            self.callback = None

    def _backend_with_connection(self, connection):
        backend = GnomeShellTypingPulseBackend()
        gio = self._Gio
        glib = self._GLib
        glib.Variant = self._Variant
        gio.connection = connection
        backend._load_gio = lambda: (gio, glib)
        return backend

    def test_absent_extension_keeps_watching(self) -> None:
        backend = self._backend_with_connection(self._Connection(has_owner=False))

        self.assertTrue(backend.start(lambda: None))
        self.assertIsNone(backend.last_error)
        self.assertFalse(backend.active)

    def test_subscribes_to_zero_payload_pulse(self) -> None:
        connection = self._Connection()
        backend = self._backend_with_connection(connection)
        calls = 0

        def activity():
            nonlocal calls
            calls += 1

        self.assertTrue(backend.start(activity))
        self.assertTrue(backend.active)
        self.assertEqual(connection.subscribe_args[0], ":1.42")
        self.assertEqual(connection.subscribe_args[1], backend.INTERFACE_NAME)
        self.assertEqual(connection.subscribe_args[2], backend.SIGNAL_NAME)
        self.assertEqual(connection.subscribe_args[3], backend.OBJECT_PATH)

        connection.callback(object(), object(), object(), object(), object(), object())
        self.assertEqual(calls, 1)

    def test_stop_unsubscribes_once(self) -> None:
        connection = self._Connection()
        backend = self._backend_with_connection(connection)
        self.assertTrue(backend.start(lambda: None))

        backend.stop()
        backend.stop()

        self.assertEqual(connection.unsubscribed, [17])
        self.assertFalse(backend.active)

    def test_pulse_callback_never_inspects_payload(self) -> None:
        class Explosive:
            def __repr__(self):
                raise AssertionError("D-Bus callback payload must not be formatted")

            def __str__(self):
                raise AssertionError("D-Bus callback payload must not be inspected")

        backend = GnomeShellTypingPulseBackend()
        calls = 0

        def activity():
            nonlocal calls
            calls += 1

        backend._on_activity = activity
        secret = Explosive()
        backend._on_pulse(secret, secret, secret, secret, secret, secret)

        self.assertEqual(calls, 1)
        self.assertNotIn(secret, vars(backend).values())


class DeviceCapabilityTests(unittest.TestCase):
    class _Capability:
        KEYBOARD_MONITOR = 1

    class _Atspi:
        DeviceCapability = None

    class _Device:
        def __init__(self, *, existing=0, enabled=1):
            self.existing = existing
            self.enabled = enabled
            self.requested = None

        def get_capabilities(self):
            return self.existing

        def set_capabilities(self, requested):
            self.requested = requested
            return self.enabled

    def test_keyboard_monitor_capability_is_requested_and_verified(self) -> None:
        backend = AtspiDeviceActivityBackend()
        atspi = type("Atspi", (), {"DeviceCapability": self._Capability})
        device = self._Device(existing=2, enabled=3)

        self.assertTrue(backend._enable_keyboard_monitor(device, atspi))
        self.assertEqual(device.requested, 3)
        self.assertIsNone(backend.last_error)

    def test_refused_keyboard_monitor_capability_fails_backend(self) -> None:
        backend = AtspiDeviceActivityBackend()
        atspi = type("Atspi", (), {"DeviceCapability": self._Capability})
        device = self._Device(enabled=0)

        self.assertFalse(backend._enable_keyboard_monitor(device, atspi))
        self.assertEqual(
            backend.last_error, "keyboard-monitor capability was not enabled"
        )

    def test_missing_capability_api_fails_cleanly(self) -> None:
        backend = AtspiDeviceActivityBackend()
        atspi = type("Atspi", (), {"DeviceCapability": None})
        device = self._Device()

        self.assertFalse(backend._enable_keyboard_monitor(device, atspi))
        self.assertEqual(
            backend.last_error, "keyboard-monitor capability API is unavailable"
        )


class CosmicCompKeyboardBackendTests(unittest.TestCase):
    class _Variant:
        def __init__(self, _sig, value):
            self.value = value

        def unpack(self):
            return self.value

    class _GLib:
        @classmethod
        def Variant(cls, sig, value):
            return CosmicCompKeyboardBackendTests._Variant(sig, value)

        class VariantType:
            @classmethod
            def new(cls, sig):
                return sig

    class _Gio:
        class BusType:
            SESSION = object()

        class DBusCallFlags:
            NONE = object()

        class DBusSignalFlags:
            NONE = object()

        class BusNameOwnerFlags:
            NONE = object()

        connection = None
        owned_names = []
        unowned_ids = []

        @classmethod
        def bus_get_sync(cls, _bus_type, _cancellable):
            return cls.connection

        @classmethod
        def bus_own_name_on_connection(cls, connection, name, flags, on_acquired, on_lost):
            cls.owned_names.append(name)
            if on_acquired:
                on_acquired(connection, name)
            return 99

        @classmethod
        def bus_unown_name(cls, owner_id):
            cls.unowned_ids.append(owner_id)

    class _Connection:
        def __init__(self, *, has_owner=True, watch_fails=False):
            self.has_owner = has_owner
            self.watch_fails = watch_fails
            self.calls = []
            self.unsubscribed = []
            self.callback = None

        def call_sync(self, dest, path, iface, method, *args):
            self.calls.append((dest, path, iface, method))
            if method == "NameHasOwner":
                return CosmicCompKeyboardBackendTests._Variant("(b)", (self.has_owner,))
            if method == "WatchKeyboard" and self.watch_fails:
                raise RuntimeError("permission denied")
            return None

        def signal_subscribe(self, *args):
            self.callback = args[-1]
            return 42

        def signal_unsubscribe(self, sub_id):
            self.unsubscribed.append(sub_id)
            self.callback = None

    def _setup_backend(self, connection):
        backend = CosmicCompKeyboardBackend()
        gio = self._Gio
        gio.connection = connection
        gio.owned_names = []
        gio.unowned_ids = []
        glib = self._GLib
        backend._load_gio = lambda: (gio, glib)
        return backend

    def test_fails_if_dbus_connection_unavailable(self) -> None:
        backend = self._setup_backend(None)
        self.assertFalse(backend.start(lambda: None))
        self.assertIn("connection unavailable", backend.last_error)

    def test_fails_if_cosmic_comp_not_present(self) -> None:
        conn = self._Connection(has_owner=False)
        backend = self._setup_backend(conn)
        self.assertFalse(backend.start(lambda: None))
        self.assertIn("not present", backend.last_error)

    def test_successful_start_and_stop(self) -> None:
        conn = self._Connection(has_owner=True)
        backend = self._setup_backend(conn)
        calls = 0

        def on_activity():
            nonlocal calls
            calls += 1

        self.assertTrue(backend.start(on_activity))
        self.assertTrue(backend.active)
        self.assertIn("org.gnome.Orca.KeyboardMonitor", self._Gio.owned_names)

        # Simulate key press
        conn.callback(None, None, None, None, None, self._Variant("(b)", (True,)))
        self.assertEqual(calls, 1)

        # Simulate key release
        conn.callback(None, None, None, None, None, self._Variant("(b)", (False,)))
        self.assertEqual(calls, 1)

        backend.stop()
        self.assertFalse(backend.active)
        self.assertIn(42, conn.unsubscribed)
        self.assertIn(99, self._Gio.unowned_ids)


class BackendPrivacyTests(unittest.TestCase):
    class _ExplosivePayload:
        def __repr__(self) -> str:
            raise AssertionError("keyboard payload must never be formatted")

        def __str__(self) -> str:
            raise AssertionError("keyboard payload must never be inspected")

    def test_device_backend_discards_signal_payload(self) -> None:
        backend = AtspiDeviceActivityBackend()
        calls = 0

        def activity() -> None:
            nonlocal calls
            calls += 1

        backend._on_activity = activity
        secret = self._ExplosivePayload()
        backend._on_key_pressed(object(), secret, secret, secret, secret)

        self.assertEqual(calls, 1)
        self.assertNotIn(secret, vars(backend).values())

    def test_cosmic_backend_discards_signal_payload(self) -> None:
        backend = CosmicCompKeyboardBackend()
        calls = 0

        def activity() -> None:
            nonlocal calls
            calls += 1

        backend._on_activity = activity
        secret = self._ExplosivePayload()

        class MockParams:
            def unpack(self):
                # pressed=True, keysym, keycode, state, unichar
                return (True, secret, secret, secret, secret)

        backend._on_key_event(None, None, None, None, None, MockParams())

        self.assertEqual(calls, 1)
        self.assertNotIn(secret, vars(backend).values())

    def test_text_fallback_reads_only_event_type(self) -> None:
        backend = AtspiTextActivityBackend()
        calls = 0

        def activity() -> None:
            nonlocal calls
            calls += 1

        backend._on_activity = activity
        secret = self._ExplosivePayload()
        event = type(
            "Event",
            (),
            {
                "type": "object:text-changed:insert",
                "source": secret,
                "any_data": secret,
            },
        )()
        backend._on_accessibility_event(event, secret)

        self.assertEqual(calls, 1)
        self.assertNotIn(secret, vars(backend).values())


if __name__ == "__main__":
    unittest.main()

