"""
Risk scoring engine for ADAS events.
"""

from __future__ import annotations

from typing import Dict, Optional


class RiskEngine:
    """Calculate risk scores and risk levels for detected objects."""

    DEFAULT_ZONE_SEVERITY = {
        "left_blind_spot": "yellow",
        "right_blind_spot": "yellow",
        "door_safety_zone": "red",
        "left_turn_risk_zone": "red"
    }

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.pedestrian_scores = self.config.get("pedestrian_risk_scores", {
            "green_zone": 10,
            "yellow_zone": 25,
            "red_zone": 50,
        })
        self.motorcycle_scores = self.config.get("motorcycle_risk_scores", {
            "green_zone": 5,
            "yellow_zone": 20,
            "red_zone": 40,
        })
        self.vehicle_scores = self.config.get("vehicle_risk_scores", {
            "green_zone": 5,
            "yellow_zone": 10,
            "red_zone": 20,
        })
        self.zone_severity = self.config.get("zone_severity", self.DEFAULT_ZONE_SEVERITY)

    def score(self, object_type: str, zone_id: str) -> int:
        """Return risk score for a given object type and zone."""
        severity = self._zone_severity(zone_id)
        if object_type == "person":
            return self._get_risk_value(self.pedestrian_scores, severity)
        if object_type == "motorcycle":
            return self._get_risk_value(self.motorcycle_scores, severity)
        if object_type in {"car", "bus", "truck"}:
            return self._get_risk_value(self.vehicle_scores, severity)
        if object_type == "bicycle":
            return self._get_risk_value(self.pedestrian_scores, severity)
        return 0

    def _get_risk_value(self, score_map: Dict[str, int], severity: str) -> int:
        if severity == "red":
            return score_map.get("red_zone", 0)
        if severity == "yellow":
            return score_map.get("yellow_zone", 0)
        return score_map.get("green_zone", 0)

    def _zone_severity(self, zone_id: str) -> str:
        return self.zone_severity.get(zone_id, "green")

    def compute_total_risk(self, events: list[Dict]) -> int:
        """Compute the total risk score for a list of events."""
        total = sum(event.get("risk_score", 0) for event in events)
        return min(100, total)

    def get_risk_level(self, score: int) -> str:
        """Map numeric score to risk level label."""
        if score <= 30:
            return "LOW"
        if score <= 60:
            return "MEDIUM"
        return "HIGH"
