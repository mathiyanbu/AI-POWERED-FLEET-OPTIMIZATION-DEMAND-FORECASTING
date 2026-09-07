class RiskEngine:
    """Simple risk scoring based on detections, zones, and lane awareness."""

    @staticmethod
    def _normalize_indicator(detection):
        indicator = detection.get("indicator")
        if indicator is None:
            indicator = detection.get("signal")
        if indicator is None:
            indicator = detection.get("turn_signal")
        if indicator is None:
            indicator = detection.get("indicator_state")

        if isinstance(indicator, str):
            return indicator.lower()
        return None

    @staticmethod
    def evaluate_detection(detection, zones):
        confidence = detection.get("confidence", 0)
        if confidence >= zones["critical"]:
            return "Critical", 90 + int(confidence * 10)
        if confidence >= zones["warning"]:
            return "Warning", 60 + int(confidence * 10)
        return "Safe", 20 + int(confidence * 10)

    @staticmethod
    def evaluate_scene(detections, zones=None, lane_info=None):
        current_level = "safe"
        total_score = 0
        total_alerts = 0
        reasons = []

        for det in detections:
            level, score = RiskEngine.evaluate_detection(det, zones or {"critical": 0.8, "warning": 0.6})
            total_score += score
            if level != "Safe":
                total_alerts += 1
            if level == "Critical":
                current_level = "critical"
            elif level == "Warning" and current_level != "critical":
                current_level = "warning"

            px = det.get("x", 0.5)
            kind = det.get("kind", "object")
            if kind in {"car", "truck", "bus", "motorcycle"}:
                if px < 0.3:
                    reasons.append("vehicle in left blind spot")
                    total_score += 12
                elif px > 0.7:
                    reasons.append("vehicle near right side")
                    total_score += 10
                if lane_info and lane_info.get("lane_center") is not None:
                    lane_center = float(lane_info.get("lane_center", 0.5))
                    if abs(px - lane_center) > 0.2:
                        reasons.append("lane-change risk")
                        total_score += 15

        if lane_info and lane_info.get("confidence", 0.0) >= 0.5:
            for det in detections:
                px = det.get("x", 0.5)
                if px < 0.35 and det.get("kind") in {"car", "truck", "bus"}:
                    reasons.append("front vehicle drifting left")
                    total_score += 8
                elif px > 0.65 and det.get("kind") in {"car", "truck", "bus"}:
                    reasons.append("front vehicle drifting right")
                    total_score += 8

                indicator = RiskEngine._normalize_indicator(det)
                lane_center = float(lane_info.get("lane_center", 0.5))
                is_front_vehicle = float(det.get("y", 0.5)) <= 0.6
                is_vehicle = det.get("kind") in {"car", "truck", "bus", "motorcycle"}
                if is_vehicle and is_front_vehicle and abs(px - lane_center) <= 0.15:
                    if indicator == "left":
                        reasons.append("front vehicle signaling left lane change")
                        total_score += 18
                    elif indicator == "right":
                        reasons.append("front vehicle signaling right lane change")
                        total_score += 18

        if reasons:
            if current_level != "critical" and total_score >= 80:
                current_level = "critical"
            elif current_level != "critical" and total_score >= 55:
                current_level = "warning"

        if total_score < 30:
            current_level = "safe"

        return {
            "risk_level": current_level,
            "score": int(total_score / len(detections)) if detections else 0,
            "alerts": total_alerts,
            "reasons": reasons,
        }

    @staticmethod
    def aggregate(detections, zones):
        result = RiskEngine.evaluate_scene(detections, zones=zones)
        return result["risk_level"], result["score"], result["alerts"]
