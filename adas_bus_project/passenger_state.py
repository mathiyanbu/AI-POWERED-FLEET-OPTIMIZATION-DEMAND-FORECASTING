"""Shared passenger occupancy state for the monitor and control-center API."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from threading import Lock


@dataclass
class PassengerSnapshot:
    bus_id: str
    route: str
    capacity: int
    current_occupancy: int
    occupancy_percent: float
    passengers: int
    crowd_level: str
    fps: int
    timestamp: str

    def as_dict(self) -> dict:
        data = asdict(self)
        data["occupancy"] = data["occupancy_percent"]
        return data


class PassengerState:
    """Thread-safe aggregate state; updates are intentionally frame-independent."""

    def __init__(self, config: dict) -> None:
        passenger = config.get("passenger_monitor", {})
        self._lock = Lock()
        self.bus_id = str(passenger.get("bus_id", "BUS-042"))
        self.route = str(passenger.get("route", "CENTRAL -> CAMPUS"))
        self.capacity = max(1, int(passenger.get("capacity", 40)))
        self.passengers = 0
        self.fps = 0
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def update(self, passengers: int, fps: int = 0) -> None:
        with self._lock:
            self.passengers = max(0, int(passengers))
            self.fps = max(0, int(fps))
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def reset(self) -> None:
        with self._lock:
            self.passengers = 0
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def update_config(self, values: dict) -> None:
        with self._lock:
            self.bus_id = str(values.get("bus_id", self.bus_id)).strip() or self.bus_id
            self.route = str(values.get("route", self.route)).strip() or self.route
            self.capacity = max(1, int(values.get("capacity", self.capacity)))

    def snapshot(self) -> PassengerSnapshot:
        with self._lock:
            occupancy = self.passengers
            percentage = round((occupancy / self.capacity) * 100, 1)
            route_parts = self.route.replace("→", "->").split("->")
            api_route = "-".join(part.strip() for part in route_parts)
            return PassengerSnapshot(
                bus_id=self.bus_id,
                route=api_route,
                capacity=self.capacity,
                current_occupancy=occupancy,
                occupancy_percent=percentage,
                passengers=self.passengers,
                crowd_level=self._crowd_level(percentage),
                fps=self.fps,
                timestamp=self.timestamp,
            )

    @staticmethod
    def _crowd_level(percentage: float) -> str:
        if percentage <= 50:
            return "LOW"
        if percentage <= 75:
            return "MODERATE"
        if percentage <= 90:
            return "HIGH"
        return "CRITICAL"