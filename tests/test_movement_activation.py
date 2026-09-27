"""Unit tests for movement activation, persistence, and direction resolution."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mochi.buddy import Buddy
from mochi.config import Position
from mochi.presence.edge_roam_controls import EdgeRoamMixin
from mochi.presence.integration import PresenceBuddyMixin
from mochi.state import MochiState


class MovementActivationTests(unittest.TestCase):
    def test_stay_put_loaded_at_startup_and_toggle_triggers_walk(self) -> None:
        class BaseDummy:
            def __init__(self, **kwargs):
                self.state = SimpleNamespace(current=MochiState.IDLE)
                self._context_menu_open = False
                self._logger = Mock()
                self._placement = SimpleNamespace(
                    sync_from_window=Mock(return_value=Position(100, 100)),
                    clamp_position=lambda x, y: Position(x, y),
                    _monitor_for_position=Mock(return_value=None),
                    _x11_coordinate_scale=lambda: 1.0,
                )
                self._sound = Mock()
                self._config = SimpleNamespace(
                    load_stay_put=Mock(return_value=True),
                    save_stay_put=Mock(),
                )
                for k, v in kwargs.items():
                    setattr(self, k, v)

            def _start_walk(self):
                self.state.current = MochiState.WALKING

        class TestBuddy(PresenceBuddyMixin, BaseDummy):
            def __init__(self):
                super().__init__(_preview_mode=True)

        buddy = TestBuddy()
        # Verifying stay_put is loaded on startup from config
        self.assertTrue(buddy._stay_put)

        # Toggling stay_put to False should trigger walk when in IDLE
        buddy._toggle_stay_put(Mock())
        self.assertFalse(buddy._stay_put)
        self.assertEqual(buddy.state.current, MochiState.WALKING)

    def test_edge_roam_loaded_at_startup_sets_pending(self) -> None:
        class BaseDummy:
            def __init__(self, **kwargs):
                self.state = SimpleNamespace(current=MochiState.IDLE)
                self._context_menu_open = False
                self._logger = Mock()
                self._config = SimpleNamespace(
                    load_edge_roam=Mock(return_value=True),
                    save_edge_roam=Mock(),
                )
                for k, v in kwargs.items():
                    setattr(self, k, v)

        class TestBuddy(EdgeRoamMixin, BaseDummy):
            def __init__(self):
                super().__init__()

        buddy = TestBuddy()
        self.assertTrue(buddy._edge_roam)
        self.assertTrue(buddy._edge_roam_start_pending)

    def test_start_walk_fallback_towards_center(self) -> None:
        # Placement where all positions clamp to (0, 0)
        # except when moving toward center
        geometry = SimpleNamespace(x=0, y=0, width=1000, height=800)
        monitor = SimpleNamespace(get_geometry=lambda: geometry)

        class ClampingPlacement:
            def sync_from_window(self):
                return Position(0, 0)

            def clamp_position(self, x, y):
                # Clamp coordinates to [0, 1000] and [0, 800]
                return Position(max(0, min(1000, x)), max(0, min(800, y)))

            def _monitor_for_position(self, x, y):
                return monitor

            def _x11_coordinate_scale(self):
                return 1.0

        buddy = SimpleNamespace(
            _placement=ClampingPlacement(),
            _animation_for=Mock(return_value=SimpleNamespace(frames=(), frame_duration_ms=100)),
            _walk_speed_multiplier=lambda: 1.0,
            WALK_SPEED_PX_PER_SECOND=72.0,
            _transition_to=Mock(return_value=True),
            _play_animation=Mock(),
            _walk_motion=None,
            _walk_elapsed_ms=0,
        )

        with patch("mochi.buddy.random.uniform", return_value=-1.0):
            # All 8 random angles point to (-1, -1) which clamps to (0, 0), dist = 0
            Buddy._start_walk(buddy)

        # Fallback towards center (500, 400) should have successfully created a walk motion
        self.assertIsNotNone(buddy._walk_motion)
        self.assertGreater(buddy._walk_motion.distance, 24.0)


if __name__ == "__main__":
    unittest.main()
