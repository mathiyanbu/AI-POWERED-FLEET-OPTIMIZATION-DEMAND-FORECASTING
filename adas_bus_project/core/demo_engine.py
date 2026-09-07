"""Deterministic simulation used to demonstrate the complete interface."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime

from PyQt6.QtCore import QObject, QTimer, pyqtSignal


@dataclass
class TrackedObject:
    track_id: int
    kind: str
    x: float
    y: float
    width: float
    height: float
    confidence: float
    threat: str = "normal"


class DemoEngine(QObject):
    frame_ready = pyqtSignal(list, dict)
    event_ready = pyqtSignal(dict)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._tick)
        self.frame = 0
        self.random = random.Random(19)
        self.event_counts = {"blind_spot": 3, "pedestrian": 2, "turning": 1}
        self._emitted: set[tuple[int, str]] = set()

    def start(self) -> None:
        self.timer.start()

    def pause(self) -> None:
        self.timer.stop()

    def stop(self) -> None:
        self.timer.stop()
        self.frame = 0
        self._emitted.clear()
        self._tick()

    def _tick(self) -> None:
        self.frame += 1
        t = self.frame / 20.0
        objects = [
            TrackedObject(12, "Motorcycle", 0.10 + (t % 9) * 0.035, 0.72, 0.07, 0.16, 0.91),
            TrackedObject(5, "Pedestrian", 0.68 + math.sin(t * 0.45) * 0.05, 0.57, 0.045, 0.22, 0.88),
            TrackedObject(31, "Car", 0.46 + math.sin(t * 0.25) * 0.025, 0.49, 0.14, 0.16, 0.94),
            TrackedObject(8, "Bus", 0.28, 0.42 + math.sin(t * 0.18) * 0.02, 0.13, 0.18, 0.97),
            TrackedObject(19, "Bicycle", 0.82 - (t % 14) * 0.018, 0.67, 0.055, 0.14, 0.84),
        ]

        risk = 22
        for item in objects:
            if item.kind == "Motorcycle" and 0.12 < item.x < 0.34:
                item.threat = "high"
                risk += 32
                self._emit_once(item, "Left blind spot", "Blind spot intrusion")
            if item.kind == "Pedestrian" and item.x > 0.64:
                item.threat = "medium"
                risk += 24
                self._emit_once(item, "Door safety zone", "Pedestrian near door")
            if item.kind == "Bicycle" and item.x > 0.72:
                item.threat = "medium"
                risk += 12

        risk = min(risk, 100)
        counts = {"person": 4, "motorcycle": 2, "car": 7, "bus": 1, "truck": 2, "bicycle": 1}
        stats = {
            "fps": 20 + int(3 * math.sin(t)),
            "risk": risk,
            "counts": counts,
            "total": sum(counts.values()),
            "event_counts": dict(self.event_counts),
        }
        self.frame_ready.emit(objects, stats)

    def _emit_once(self, item: TrackedObject, zone: str, event_type: str) -> None:
        key = (item.track_id, event_type)
        cycle = self.frame // 260
        cycle_key = (item.track_id, f"{event_type}:{cycle}")
        if cycle_key in self._emitted:
            return
        self._emitted.add(cycle_key)
        if "Pedestrian" in event_type:
            self.event_counts["pedestrian"] += 1
        else:
            self.event_counts["blind_spot"] += 1
        self.event_ready.emit(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "track_id": item.track_id,
                "object_type": item.kind,
                "zone": zone,
                "risk_level": "HIGH" if item.threat == "high" else "MEDIUM",
                "event_type": event_type,
            }
        )
