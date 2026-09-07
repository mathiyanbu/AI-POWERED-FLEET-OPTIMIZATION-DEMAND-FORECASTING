"""
Export manager for ADAS event data.
"""

from __future__ import annotations

from pathlib import Path

from .db_manager import DatabaseManager


class ExportManager:
    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    def export_csv(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.db_manager.export_csv(destination)

    def export_excel(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.db_manager.export_xlsx(destination)
