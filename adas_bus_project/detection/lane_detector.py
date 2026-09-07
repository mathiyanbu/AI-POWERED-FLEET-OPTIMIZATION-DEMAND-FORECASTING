from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import cv2
import numpy as np


@dataclass
class LaneInfo:
    left_line: Tuple[float, float] | None = None
    right_line: Tuple[float, float] | None = None
    lane_center: float | None = None
    confidence: float = 0.0


class LaneDetector:
    """Very lightweight lane detector for prototype front-view warnings."""

    def __init__(self, canny_low: int = 50, canny_high: int = 150) -> None:
        self.canny_low = canny_low
        self.canny_high = canny_high

    def detect_lanes(self, frame: np.ndarray) -> Dict[str, object]:
        if frame is None:
            return {"left_line": None, "right_line": None, "lane_center": None, "confidence": 0.0}

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, self.canny_low, self.canny_high)

        height, width = gray.shape
        roi = edges[int(height * 0.45):int(height * 0.95), :]
        lines = cv2.HoughLinesP(
            roi,
            1,
            np.pi / 180,
            threshold=20,
            minLineLength=max(20, width // 12),
            maxLineGap=20,
        )

        if lines is None:
            return {"left_line": None, "right_line": None, "lane_center": None, "confidence": 0.0}

        left_candidates = []
        right_candidates = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if x2 == x1:
                continue
            slope = (y2 - y1) / (x2 - x1)
            if abs(slope) > 0.2:
                continue
            mid_x = (x1 + x2) / 2.0
            if mid_x < width / 2:
                left_candidates.append((mid_x, y1 + (y2 - y1) / 2.0))
            else:
                right_candidates.append((mid_x, y1 + (y2 - y1) / 2.0))

        left_line = None
        right_line = None
        if left_candidates:
            left_line = (float(np.mean([x for x, _ in left_candidates])), float(np.mean([y for _, y in left_candidates])))
        if right_candidates:
            right_line = (float(np.mean([x for x, _ in right_candidates])), float(np.mean([y for _, y in right_candidates])))

        lane_center = None
        if left_line and right_line:
            lane_center = (left_line[0] + right_line[0]) / 2.0 / width
        confidence = 0.6 if left_line and right_line else 0.3 if left_line or right_line else 0.0

        return {
            "left_line": left_line,
            "right_line": right_line,
            "lane_center": lane_center,
            "confidence": confidence,
        }
