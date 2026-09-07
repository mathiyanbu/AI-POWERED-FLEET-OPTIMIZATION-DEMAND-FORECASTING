import unittest
from passenger_state import PassengerState


class PassengerStateTests(unittest.TestCase):
    def test_snapshot_uses_current_passengers_not_accumulated_frames(self):
        state = PassengerState({"passenger_monitor": {"capacity": 40}})
        state.update(6, fps=62)
        self.assertEqual(state.snapshot().passengers, 6)
        state.update(7, fps=62)
        self.assertEqual(state.snapshot().passengers, 7)

    def test_snapshot_calculates_occupancy_and_crowd_level(self):
        state = PassengerState({"passenger_monitor": {"capacity": 40}})
        state.update(21, fps=62)
        snapshot = state.snapshot()
        self.assertEqual(snapshot.current_occupancy, 21)
        self.assertEqual(snapshot.occupancy_percent, 52.5)
        self.assertEqual(snapshot.crowd_level, "MODERATE")
        self.assertEqual(snapshot.fps, 62)


if __name__ == "__main__":
    unittest.main()