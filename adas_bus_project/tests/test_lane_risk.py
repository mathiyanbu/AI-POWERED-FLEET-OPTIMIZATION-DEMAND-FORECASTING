import unittest

import cv2
import numpy as np
from PyQt6.QtWidgets import QApplication

from detection.lane_detector import LaneDetector
from core.risk_engine import RiskEngine
from ui.widgets import VideoCanvas


class LaneRiskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_lane_detector_finds_lane_boundaries(self) -> None:
        image = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.line(image, (40, 180), (120, 120), (255, 255, 255), 3)
        cv2.line(image, (200, 180), (280, 120), (255, 255, 255), 3)
        detector = LaneDetector()
        lanes = detector.detect_lanes(image)
        self.assertIn("left_line", lanes)
        self.assertIn("right_line", lanes)
        self.assertGreaterEqual(lanes["confidence"], 0.0)

    def test_risk_engine_flags_lane_change_risk(self) -> None:
        detection = {
            "kind": "car",
            "x": 0.36,
            "y": 0.56,
            "width": 0.18,
            "height": 0.14,
            "confidence": 0.9,
        }
        lane_info = {
            "left_line": (0.25, 0.42),
            "right_line": (0.75, 0.42),
            "lane_center": 0.5,
            "confidence": 0.8,
        }
        result = RiskEngine.evaluate_scene([detection], lane_info=lane_info)
        self.assertIn(result["risk_level"], {"warning", "critical"})

    def test_risk_engine_flags_indicator_based_lane_change(self) -> None:
        detection = {
            "kind": "car",
            "x": 0.5,
            "y": 0.55,
            "width": 0.12,
            "height": 0.1,
            "confidence": 0.92,
            "indicator": "left",
        }
        lane_info = {
            "left_line": (0.25, 0.42),
            "right_line": (0.75, 0.42),
            "lane_center": 0.5,
            "confidence": 0.8,
        }
        result = RiskEngine.evaluate_scene([detection], lane_info=lane_info)
        self.assertIn("front vehicle signaling left lane change", result["reasons"])
        self.assertIn(result["risk_level"], {"warning", "critical"})

    def test_video_canvas_shows_danger_overlay_only_when_needed(self) -> None:
        canvas = VideoCanvas({})
        self.assertTrue(VideoCanvas.should_show_lane_overlay({"lane_info": {"left_line": (80, 120)}}))
        self.assertFalse(VideoCanvas.should_show_danger_overlay({"scene_reasons": []}))
        self.assertTrue(VideoCanvas.should_show_danger_overlay({"scene_reasons": ["front vehicle signaling left lane change"]}))


if __name__ == "__main__":
    unittest.main()
