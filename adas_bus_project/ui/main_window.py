"""Main application window and user workflows."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import cv2

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QImage
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from analytics.reports import generate_pdf
from core.demo_engine import DemoEngine
from logging_system.database_manager import DatabaseManager
from api_server import PassengerApiServer
from passenger_state import PassengerState
from ui.styles import COLORS
from ui.widgets import EventRow, MetricTile, MiniBarChart, RiskGauge, VideoCanvas
from detection.detector import YOLODetector
from detection.tracker import ByteTracker
from detection.lane_detector import LaneDetector
from core.risk_engine import RiskEngine


class MainWindow(QMainWindow):
    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.project_root = project_root
        self.output_dir = project_root / "outputs"
        self.output_dir.mkdir(exist_ok=True)
        self.config_path = project_root / "config" / "config.json"
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.database = DatabaseManager(project_root / "database" / "events.db")
        self.passenger_state = PassengerState(self.config)
        passenger_config = self.config.get("passenger_monitor", {})
        self.passenger_tracker: ByteTracker | None = None
        self.api_server = PassengerApiServer(
            self.passenger_state,
            passenger_config.get("api_host", "127.0.0.1"),
            int(passenger_config.get("api_port", 8765)),
        )
        self.api_server.start()
        self.engine = DemoEngine(self)
        self.engine.frame_ready.connect(self._on_frame)
        self.engine.event_ready.connect(self._on_event)
        # Lazy-loaded real detector for video playback analysis
        self.detector: YOLODetector | None = None
        self.lane_detector = LaneDetector()
        self.current_stats = {"risk": 0, "fps": 0, "total": 0, "counts": {}, "event_counts": {}}
        self.running = False
        self.video_capture = None
        self.video_path = self._resolve_video_path(self.config.get("video_path"))
        self.video_timer = QTimer(self)
        self.video_timer.timeout.connect(self._read_video_frame)

        self.setWindowTitle("Crowd Track AI | Urban Bus Crowd Monitor")
        self.resize(1600, 900)
        self.setMinimumSize(1180, 720)
        self._build_ui()
        self._load_existing_events()
        self._update_passenger_panels(self.passenger_state.snapshot())
        self._set_status(f"API :{self.api_server.port} | System ready", COLORS["green"])

    def _build_ui(self) -> None:
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 12, 14, 8)
        outer.setSpacing(10)
        outer.addWidget(self._build_top_bar())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_live_tab(), "Live Monitor")
        self.tabs.addTab(self._build_analytics_tab(), "Analytics")
        self.tabs.addTab(self._build_events_tab(), "Event History")
        outer.addWidget(self.tabs, 1)
        outer.addWidget(self._build_control_bar())
        self.setCentralWidget(root)
        self.statusBar().showMessage("Ready")

        escape = QAction(self)
        escape.setShortcut("Esc")
        escape.triggered.connect(self.showNormal)
        self.addAction(escape)

    def _build_top_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("topBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 12, 10)
        layout.setSpacing(12)

        logo = QLabel("CT")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedSize(34, 34)
        logo.setStyleSheet(
            f"background: {COLORS['cyan']}; color: #FFFFFF; border-radius: 5px; font-weight: 900;"
        )
        brand_box = QVBoxLayout()
        brand_box.setSpacing(0)
        brand = QLabel("Crowd Track AI")
        brand.setObjectName("brand")
        descriptor = QLabel("REAL-TIME PASSENGER INTELLIGENCE")
        descriptor.setObjectName("muted")
        descriptor.setStyleSheet("font-size: 9px; font-weight: 700;")
        brand_box.addWidget(brand)
        brand_box.addWidget(descriptor)

        disclaimer = QLabel("BUS-042  |  ROUTE: CENTRAL -> CAMPUS  |  CAPACITY: 40")
        disclaimer.setObjectName("disclaimer")

        self.health_dot = QLabel()
        self.health_dot.setFixedSize(8, 8)
        self.health_dot.setStyleSheet(f"background: {COLORS['green']};")
        self.health_label = QLabel("SYSTEM READY")
        self.health_label.setStyleSheet("font-size: 10px; font-weight: 700;")

        settings = QToolButton()
        settings.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        settings.setToolTip("Settings")
        settings.clicked.connect(self._open_settings)
        fullscreen = QToolButton()
        fullscreen.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMaxButton))
        fullscreen.setToolTip("Toggle full screen")
        fullscreen.clicked.connect(self._toggle_fullscreen)

        layout.addWidget(logo)
        layout.addLayout(brand_box)
        layout.addSpacing(16)
        layout.addWidget(disclaimer)
        layout.addStretch()
        layout.addWidget(self.health_dot)
        layout.addWidget(self.health_label)
        layout.addSpacing(8)
        layout.addWidget(settings)
        layout.addWidget(fullscreen)
        return bar

    def _build_live_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(9)
        self.video = VideoCanvas(self.config["zones"])
        self.video.set_zone_draw_callback(self._zone_drawn)
        self.video.set_zone_edit_callback(self._on_zone_edited)
        video_frame = QFrame()
        video_frame.setObjectName("card")
        video_layout = QVBoxLayout(video_frame)
        video_layout.setContentsMargins(1, 1, 1, 1)
        video_layout.addWidget(self.video)
        left.addWidget(video_frame, 1)
        left.addLayout(self._build_bottom_metrics())

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setFixedWidth(354)
        right_container = QWidget()
        right = QVBoxLayout(right_container)
        right.setContentsMargins(0, 0, 2, 0)
        right.setSpacing(9)
        right.addWidget(self._build_crowd_status_card())
        right.addWidget(self._build_passenger_monitor_card())
        right.addWidget(self._build_bus_info_card())
        right.addWidget(self._build_control_center_card())
        right.addWidget(self._build_feed_card(), 1)
        right_scroll.setWidget(right_container)

        layout.addLayout(left, 1)
        layout.addWidget(right_scroll)
        return page

    def _build_bottom_metrics(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(8)
        self.total_tile = MetricTile("Tracked passengers", "0", COLORS["cyan"])
        self.fps_tile = MetricTile("YOLO FPS", "0 FPS", COLORS["green"])
        self.source_tile = MetricTile("Current occupancy", "0 / 40", COLORS["amber"])
        self.alert_tile = MetricTile("Crowd level", "LOW", COLORS["red"])
        for widget in (self.total_tile, self.fps_tile, self.source_tile, self.alert_tile):
            layout.addWidget(widget)
        return layout

    def _build_crowd_status_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        title = QLabel("CURRENT CROWD STATUS")
        title.setObjectName("cardTitle")
        self.crowd_percent_label = QLabel("0.0%")
        self.crowd_percent_label.setStyleSheet(f"color: {COLORS['red']}; font-size: 30px; font-weight: 800;")
        self.crowd_level_label = QLabel("LOW")
        self.crowd_level_label.setStyleSheet(f"color: {COLORS['green']}; font-size: 16px; font-weight: 800;")
        self.crowd_capacity_label = QLabel("Capacity: 40  |  Current: 0  |  Available: 40")
        self.crowd_capacity_label.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(self.crowd_percent_label)
        layout.addWidget(self.crowd_level_label)
        layout.addWidget(self.crowd_capacity_label)
        return card

    def _build_passenger_monitor_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        title = QLabel("PASSENGER MONITOR")
        title.setObjectName("cardTitle")
        layout.addWidget(title)
        self.passenger_labels = {}
        for key, caption in (
            ("passengers", "Passengers detected"),
            ("current_passengers", "Current passengers"),
            ("capacity", "Bus capacity"),
            ("occupancy_percent", "Occupancy"),
            ("crowd_level", "Crowd level"),
            ("available_capacity", "Available capacity"),
        ):
            row = QHBoxLayout()
            name = QLabel(caption)
            name.setObjectName("muted")
            value = QLabel("0")
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            value.setStyleSheet("font-weight: 700;")
            row.addWidget(name)
            row.addWidget(value)
            layout.addLayout(row)
            self.passenger_labels[key] = value
        return card

    def _build_bus_info_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        title = QLabel("BUS INFORMATION")
        title.setObjectName("cardTitle")
        self.bus_info_label = QLabel()
        self.bus_info_label.setObjectName("muted")
        self.bus_info_label.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(self.bus_info_label)
        self._refresh_bus_info()
        return card

    def _build_control_center_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        title_row = QHBoxLayout()
        title = QLabel("TRANSPORT CONTROL CENTER")
        title.setObjectName("cardTitle")
        self.stream_status = QLabel("● DATA STREAM ACTIVE")
        self.stream_status.setStyleSheet(f"color: {COLORS['green']}; font-size: 8px; font-weight: 700;")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.stream_status)
        self.control_center_label = QLabel("Waiting for passenger data")
        self.control_center_label.setObjectName("muted")
        self.control_center_label.setWordWrap(True)
        layout.addLayout(title_row)
        layout.addWidget(self.control_center_label)
        return card

    def _build_risk_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(2)
        title = QLabel("CURRENT RISK ASSESSMENT")
        title.setObjectName("cardTitle")
        self.risk_gauge = RiskGauge()
        self.risk_message = QLabel("No active hazards detected")
        self.risk_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.risk_message.setObjectName("muted")
        self.risk_message.setStyleSheet("font-size: 9px;")
        layout.addWidget(title)
        layout.addWidget(self.risk_gauge)
        layout.addWidget(self.risk_message)
        return card

    def _build_stats_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        title_row = QHBoxLayout()
        title = QLabel("SYSTEM STATISTICS")
        title.setObjectName("cardTitle")
        self.object_total = QLabel("0 ACTIVE")
        self.object_total.setStyleSheet(f"color: {COLORS['cyan']}; font-size: 9px; font-weight: 700;")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.object_total)
        layout.addLayout(title_row)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(7)
        self.count_labels = {}
        entries = [
            ("person", "Pedestrians", "P"),
            ("motorcycle", "Motorcycles", "M"),
            ("car", "Cars", "C"),
            ("bus", "Buses", "B"),
            ("truck", "Trucks", "T"),
            ("bicycle", "Bicycles", "Y"),
        ]
        for index, (key, label, glyph) in enumerate(entries):
            item = QFrame()
            item.setStyleSheet("background: #1C1C1C; border-radius: 4px;")
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(8, 7, 8, 7)
            icon = QLabel(glyph)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setFixedSize(22, 22)
            icon.setStyleSheet(f"color: {COLORS['cyan']}; background: #4A1D22; border-radius: 3px; font-weight: 800; font-size: 9px;")
            name = QLabel(label)
            name.setObjectName("muted")
            name.setStyleSheet("font-size: 9px;")
            value = QLabel("0")
            value.setStyleSheet("font-weight: 700;")
            item_layout.addWidget(icon)
            item_layout.addWidget(name, 1)
            item_layout.addWidget(value)
            self.count_labels[key] = value
            grid.addWidget(item, index // 2, index % 2)
        layout.addLayout(grid)
        return card

    def _build_event_counter_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        title = QLabel("EVENT COUNTERS")
        title.setObjectName("cardTitle")
        layout.addWidget(title)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.event_counter_labels = {}
        for key, caption, color in [
            ("blind_spot", "Blind spot", COLORS["red"]),
            ("pedestrian", "Pedestrian", COLORS["amber"]),
            ("turning", "Turning", "#A58BFA"),
        ]:
            box = QFrame()
            box.setStyleSheet("background: #1C1C1C; border-radius: 4px;")
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(6, 7, 6, 7)
            box_layout.setSpacing(1)
            value = QLabel("0")
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: 700;")
            label = QLabel(caption.upper())
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setObjectName("muted")
            label.setStyleSheet("font-size: 7px; font-weight: 700;")
            box_layout.addWidget(value)
            box_layout.addWidget(label)
            self.event_counter_labels[key] = value
            row.addWidget(box)
        layout.addLayout(row)
        return card

    def _build_feed_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 10)
        title_row = QHBoxLayout()
        title = QLabel("LIVE EVENT FEED")
        title.setObjectName("cardTitle")
        self.feed_status = QLabel("MONITORING")
        self.feed_status.setStyleSheet(f"color: {COLORS['green']}; font-size: 8px; font-weight: 700;")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.feed_status)
        self.feed_layout = QVBoxLayout()
        self.feed_layout.setSpacing(0)
        self.feed_layout.addStretch()
        layout.addLayout(title_row)
        layout.addLayout(self.feed_layout, 1)
        return card

    def _build_analytics_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Operational Analytics")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Live safety performance and detection distribution")
        subtitle.setObjectName("muted")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        range_box = QComboBox()
        range_box.addItems(["Current session", "Last 24 hours", "Last 7 days", "Last 30 days"])
        range_box.setFixedWidth(160)
        header.addLayout(title_box)
        header.addStretch()
        header.addWidget(range_box)
        layout.addLayout(header)

        summary = QHBoxLayout()
        self.analytics_alerts = MetricTile("Total alerts", "0", COLORS["red"])
        self.analytics_risk = MetricTile("Peak risk score", "0", COLORS["amber"])
        self.analytics_objects = MetricTile("Objects observed", "0", COLORS["cyan"])
        self.analytics_uptime = MetricTile("Monitor uptime", "00:00", COLORS["green"])
        for tile in (self.analytics_alerts, self.analytics_risk, self.analytics_objects, self.analytics_uptime):
            summary.addWidget(tile)
        layout.addLayout(summary)

        charts = QGridLayout()
        charts.setSpacing(10)
        self.object_chart = self._chart_card(MiniBarChart(
            "Object Count Distribution", ["PED", "MOTO", "CAR", "BUS", "TRUCK", "BIKE"], [4, 2, 7, 1, 2, 1]
        ))
        self.event_chart = self._chart_card(MiniBarChart(
            "Event Trend", ["08", "09", "10", "11", "12", "13", "14", "15"], [1, 3, 2, 5, 4, 7, 3, 6], COLORS["amber"]
        ))
        self.zone_chart = self._chart_card(MiniBarChart(
            "Zone Intrusions", ["LEFT", "RIGHT", "DOOR", "TURN"], [8, 4, 6, 3], COLORS["red"]
        ))
        self.risk_chart = self._chart_card(MiniBarChart(
            "Risk Distribution", ["LOW", "MED", "HIGH"], [62, 28, 10], COLORS["green"]
        ))
        charts.addWidget(self.object_chart, 0, 0)
        charts.addWidget(self.event_chart, 0, 1)
        charts.addWidget(self.zone_chart, 1, 0)
        charts.addWidget(self.risk_chart, 1, 1)
        layout.addLayout(charts, 1)
        return page

    @staticmethod
    def _chart_card(chart: QWidget) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.addWidget(chart)
        return card

    def _build_events_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)
        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Event History")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Searchable audit trail of safety-zone alerts")
        subtitle.setObjectName("muted")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        export_csv = QPushButton("Export CSV")
        export_csv.clicked.connect(lambda: self._export("csv"))
        export_xlsx = QPushButton("Export Excel")
        export_xlsx.clicked.connect(lambda: self._export("xlsx"))
        top.addLayout(title_box)
        top.addStretch()
        top.addWidget(export_csv)
        top.addWidget(export_xlsx)
        layout.addLayout(top)

        self.event_table = QTableWidget(0, 7)
        self.event_table.setHorizontalHeaderLabels(
            ["Time", "Track ID", "Object", "Zone", "Risk", "Event type", "Status"]
        )
        self.event_table.setAlternatingRowColors(True)
        self.event_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.event_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.event_table.verticalHeader().setVisible(False)
        header = self.event_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.event_table, 1)
        return page

    def _build_control_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("controlBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(8)
        load = QPushButton("Load Video")
        load.clicked.connect(self._load_video)
        self.start_button = QPushButton("Start Monitor")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self._start)
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self._pause)
        self.pause_button.setEnabled(False)
        self.draw_zone_button = QPushButton("Draw Zone")
        self.draw_zone_button.setCheckable(True)
        self.draw_zone_button.clicked.connect(self._toggle_zone_draw)
        stop = QPushButton("Stop")
        stop.setObjectName("danger")
        stop.clicked.connect(self._stop)
        report = QPushButton("Export Report")
        report.clicked.connect(lambda: self._export("pdf"))
        source_name = Path(self.video_path).name.upper() if self.video_path else "NO VIDEO SELECTED"
        self.source_label = QLabel(f"SOURCE  |  {source_name}")
        self.source_label.setObjectName("muted")
        self.source_label.setStyleSheet("font-size: 9px; font-weight: 700;")
        layout.addWidget(load)
        layout.addWidget(self.start_button)
        layout.addWidget(self.pause_button)
        layout.addWidget(self.draw_zone_button)
        layout.addWidget(stop)
        layout.addStretch()
        layout.addWidget(self.source_label)
        layout.addSpacing(10)
        layout.addWidget(report)
        return bar

    def _start(self) -> None:
        self.running = True
        if self.video_path:
            self._start_video_playback()
        else:
            self.engine.start()
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.feed_status.setText("LIVE")
        self._set_status("Monitoring active", COLORS["green"])

    def _start_video_playback(self) -> None:
        if not self.video_path:
            QMessageBox.critical(self, "Playback error", "No video file has been selected yet.")
            self.running = False
            return

        if self.video_capture is not None:
            self.video_capture.release()
        self.video_capture = cv2.VideoCapture(self.video_path)
        if not self.video_capture.isOpened():
            QMessageBox.critical(self, "Playback error", f"Unable to open video file:\n{self.video_path}")
            self.video_capture = None
            self.running = False
            return

        fps = self.video_capture.get(cv2.CAP_PROP_FPS) or 30
        interval = max(1, int(1000 / fps))
        self.video_timer.setInterval(interval)
        self.video_timer.start()
        self._read_video_frame()

    def _read_video_frame(self) -> None:
        if self.video_capture is None:
            return

        ret, frame = self.video_capture.read()
        if not ret:
            self._stop()
            return

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, _ = rgb.shape
        bytes_per_line = 3 * width
        image = QImage(rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).copy()

        # Run detection and build UI objects
        stats = {
            "fps": int(round(1000 / max(1, self.video_timer.interval()))),
            "risk": 0,
            "counts": {},
            "total": 0,
            "event_counts": {},
            "lane_info": None,
            "scene_reasons": [],
        }
        objects = []
        try:
            if self.detector is None:
                ycfg = self.config.get("yolo_settings", {})
                model_path = ycfg.get("model_path", ycfg.get("model_name", "models/yolov8n.pt"))
                conf = float(self.config.get("confidence_threshold", ycfg.get("confidence_threshold", 0.5)))
                device = ycfg.get("device", "cpu")
                self.detector = YOLODetector(model_path, conf, device)
            if self.passenger_tracker is None:
                tracking = self.config.get("tracking", {})
                self.passenger_tracker = ByteTracker(
                    track_thresh=float(tracking.get("track_thresh", 0.5)),
                    track_buffer=int(tracking.get("track_buffer", 30)),
                    match_thresh=float(tracking.get("match_thresh", 0.8)),
                    min_box_area=int(tracking.get("min_box_area", 10)),
                )

            detections = self.detector.detect(frame)
            detections = self.detector.filter_classes(detections, ["person"])
            tracks = self.passenger_tracker.update(detections, self.passenger_tracker.frame_id + 1)
            boxes = detections.get("boxes", [])
            class_names = detections.get("class_names", [])
            confidences = detections.get("confidences", [])

            lane_info = self.lane_detector.detect_lanes(frame)
            scene_eval = RiskEngine.evaluate_scene(
                [
                    {
                        "kind": name.lower(),
                        "x": float(box[0]) / float(width),
                        "y": float(box[1]) / float(height),
                        "width": float(box[2] - box[0]) / float(width),
                        "height": float(box[3] - box[1]) / float(height),
                        "confidence": float(conf),
                    }
                    for box, name, conf in zip(boxes, class_names, confidences)
                ],
                lane_info=lane_info,
            )

            counts = {"person": len(tracks)}
            fh, fw = height, width
            for track in tracks:
                x1, y1, x2, y2 = track.bbox
                nx = float(x1) / float(fw)
                ny = float(y1) / float(fh)
                nw = float(x2 - x1) / float(fw)
                nh = float(y2 - y1) / float(fh)
                obj = type("Obj", (), {})()
                obj.track_id = track.track_id
                obj.kind = "PERSON"
                obj.x = nx
                obj.y = ny
                obj.width = nw
                obj.height = nh
                obj.confidence = track.confidence
                obj.threat = "normal"
                objects.append(obj)

            stats["counts"] = counts
            stats["total"] = len(tracks)
            stats["tracked_passengers"] = len(tracks)
            stats["lane_info"] = lane_info
            stats["scene_reasons"] = scene_eval.get("reasons", [])
            stats["risk"] = scene_eval.get("score", 0)
            self.passenger_state.update(len(tracks), stats["fps"])

        except Exception as exc:
            # On detection error, fall back to empty objects
            objects = []
            self.statusBar().showMessage(f"Detection error: {exc}", 5000)

        # Send frame + objects to UI
        self._on_frame(objects, stats, frame=image)

    def _pause(self) -> None:
        if self.video_timer.isActive():
            self.video_timer.stop()
        else:
            self.engine.pause()
        self.running = False
        self.start_button.setEnabled(True)
        self.start_button.setText("Resume")
        self.pause_button.setEnabled(False)
        self.feed_status.setText("PAUSED")
        self._set_status("Monitoring paused", COLORS["amber"])

    def _stop(self) -> None:
        self.video_timer.stop()
        if self.video_capture is not None:
            self.video_capture.release()
            self.video_capture = None
        if not self.video_path:
            self.engine.stop()
        self.passenger_tracker = None
        self.running = False
        self.video.set_idle()
        self.start_button.setEnabled(True)
        self.start_button.setText("Start Monitor")
        self.pause_button.setEnabled(False)
        self.feed_status.setText("STANDBY")
        self._set_status("System ready", COLORS["green"])

    def _on_frame(self, objects: list, stats: dict, frame: QImage | None = None) -> None:
        self.current_stats = stats
        self.video.update_frame(objects, stats, frame)
        self.total_tile.set_value(stats["total"])
        self.fps_tile.set_value(f'{stats["fps"]} FPS')
        self.analytics_risk.set_value(stats["risk"])
        self.analytics_objects.set_value(stats["total"])
        snapshot = self.passenger_state.snapshot()
        values = [snapshot.passengers]
        self._update_passenger_panels(snapshot)
        chart = self.object_chart.findChild(MiniBarChart)
        if chart:
            chart.set_values(values)
        risk = stats["risk"]
        reasons = stats.get("scene_reasons", [])
        lane_change_reason = next((reason for reason in reasons if "lane change" in reason), None)
        if hasattr(self, "risk_message"):
            if lane_change_reason:
                self.risk_message.setText(f"Lane change alert: {lane_change_reason}")
            else:
                self.risk_message.setText(
                    "Immediate driver attention required" if risk > 60
                    else "Elevated activity near safety zones" if risk > 30
                    else "No active hazards detected"
                )

    def _on_event(self, event: dict) -> None:
        try:
            self.database.add_event(event)
        except OSError as exc:
            self.statusBar().showMessage(f"Database error: {exc}", 6000)
            return
        self._prepend_feed_event(event)
        self._insert_table_event(event)
        count = self.event_table.rowCount()
        self.alert_tile.set_value(count)
        self.analytics_alerts.set_value(count)

    def _prepend_feed_event(self, event: dict) -> None:
        stretch = self.feed_layout.takeAt(self.feed_layout.count() - 1)
        self.feed_layout.insertWidget(0, EventRow(event))
        while self.feed_layout.count() > 6:
            item = self.feed_layout.takeAt(self.feed_layout.count() - 1)
            if item.widget():
                item.widget().deleteLater()
        self.feed_layout.addStretch()
        del stretch

    def _insert_table_event(self, event: dict) -> None:
        self.event_table.insertRow(0)
        values = [
            event["timestamp"].replace("T", " "),
            str(event["track_id"]),
            event["object_type"],
            event["zone"],
            event["risk_level"],
            event["event_type"],
            "Logged",
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column == 4:
                item.setForeground(QColor(COLORS["red"] if value == "HIGH" else COLORS["amber"]))
            if column == 6:
                item.setForeground(QColor(COLORS["green"]))
            self.event_table.setItem(0, column, item)

    def _load_existing_events(self) -> None:
        events = self.database.recent_events(30)
        for event in reversed(events):
            self._insert_table_event(event)
        for event in events[:4]:
            self._prepend_feed_event(event)
        self.alert_tile.set_value(len(events))
        self.analytics_alerts.set_value(len(events))

    def _load_video(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select bus camera footage", "", "Video files (*.mp4 *.avi *.mov *.mkv);;All files (*)"
        )
        if not filename:
            return

        resolved_path = self._resolve_video_path(filename)
        if not resolved_path:
            QMessageBox.critical(self, "Playback error", "The selected file could not be resolved.")
            return

        name = Path(resolved_path).name
        self.video.source_name = name.upper()
        self.source_label.setText(f"SOURCE  |  {name.upper()}")
        self.source_tile.set_value("Video")
        self.config["video_path"] = resolved_path
        self.video_path = resolved_path
        self.config_path.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        self.statusBar().showMessage(f"Loaded {name}. YOLO passenger tracking is ready.", 7000)
        self._start_video_playback()

    def _update_passenger_panels(self, snapshot) -> None:
        available = max(0, snapshot.capacity - snapshot.current_occupancy)
        values = {
            "passengers": snapshot.passengers,
            "current_passengers": snapshot.passengers,
            "capacity": snapshot.capacity,
            "occupancy_percent": f"{snapshot.occupancy_percent:.1f}%",
            "crowd_level": snapshot.crowd_level,
            "available_capacity": available,
        }
        for key, value in values.items():
            self.passenger_labels[key].setText(str(value))
        self.crowd_percent_label.setText(f"{snapshot.occupancy_percent:.1f}%")
        self.crowd_level_label.setText(snapshot.crowd_level)
        self.crowd_capacity_label.setText(
            f"Capacity: {snapshot.capacity}  |  Current: {snapshot.current_occupancy}  |  Available: {available}"
        )
        self.control_center_label.setText(
            f"Last update: {snapshot.timestamp[11:19]} UTC\n"
            f"Passengers: {snapshot.passengers}\n"
            f"Occupancy: {snapshot.occupancy_percent:.1f}%  |  Crowd level: {snapshot.crowd_level}"
        )
        self.total_tile.set_value(snapshot.passengers)
        self.source_tile.set_value(f"{snapshot.current_occupancy} / {snapshot.capacity}")
        self.alert_tile.set_value(snapshot.crowd_level)
        self._refresh_bus_info()

    def _refresh_bus_info(self) -> None:
        snapshot = self.passenger_state.snapshot()
        self.bus_info_label.setText(
            f"Bus ID: {snapshot.bus_id}\n"
            f"Route: {snapshot.route.replace('-', ' -> ')}\n"
            f"Capacity: {snapshot.capacity}\n"
            "Camera: FRONT DOOR\n"
            f"Monitoring: {'ACTIVE' if self.running else 'STANDBY'}\n"
            f"API: /api/bus/{snapshot.bus_id}/status"
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        self.api_server.stop()
        if self.video_capture is not None:
            self.video_capture.release()
        super().closeEvent(event)

    def _export(self, export_type: str) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            if export_type == "csv":
                destination = self.output_dir / f"events_{stamp}.csv"
                self.database.export_csv(destination)
            elif export_type == "xlsx":
                destination = self.output_dir / f"events_{stamp}.xlsx"
                self.database.export_xlsx(destination)
            else:
                destination = self.output_dir / f"ADAS_Report_{stamp}.pdf"
                generate_pdf(destination, self.current_stats, self.database.recent_events(100))
        except (OSError, RuntimeError) as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Export complete", f"Saved report to:\n{destination}")

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.config.update(dialog.values())
        self.config_path.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        self.passenger_state.update_config(self.config.get("passenger_monitor", {}))
        self.video.zones = self.config.get("zones", {})
        self.video.update()
        self._refresh_bus_info()
        self.statusBar().showMessage("Settings saved", 4000)

    def _toggle_zone_draw(self) -> None:
        enabled = self.draw_zone_button.isChecked()
        self.video.enable_zone_drawing(enabled)
        if enabled:
            self._set_status("Draw a new zone by dragging on the video frame", COLORS["cyan"])
        else:
            self._set_status("Zone drawing cancelled", COLORS["green"])

    def _zone_drawn(self, normalized_polygon: list[tuple[float, float]]):
        self.draw_zone_button.setChecked(False)
        self.video.enable_zone_drawing(False)

        zone_id = self._make_unique_zone_id()
        dialog = ZoneDrawDialog(zone_id, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_zone_id, zone_values = dialog.values()
        zone_values["points"] = normalized_polygon
        self.config.setdefault("zones", {})[new_zone_id] = zone_values
        self.config_path.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        self.video.zones = self.config.get("zones", {})
        self.video.update()
        self.statusBar().showMessage(f"Zone '{new_zone_id}' created", 4000)

    def _on_zone_edited(self, zone_id: str, new_points: list[list[float]]) -> None:
        # Persist translated zone points back to config
        try:
            zones = self.config.setdefault("zones", {})
            if zone_id in zones and isinstance(zones[zone_id], dict):
                zones[zone_id]["points"] = new_points
            else:
                zones[zone_id] = {"name": zone_id, "points": new_points, "color": [0,165,255], "alert_message": "Zone edited", "zone_type": "generic"}
            self.config_path.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
            self.statusBar().showMessage(f"Zone '{zone_id}' updated", 3000)
        except Exception as exc:
            self.statusBar().showMessage(f"Failed to save zone: {exc}", 5000)

    def _make_unique_zone_id(self) -> str:
        base = "custom_zone"
        index = 1
        while True:
            candidate = f"{base}_{index}"
            if candidate not in self.config.get("zones", {}):
                return candidate
            index += 1

    def _toggle_fullscreen(self) -> None:
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def _resolve_video_path(self, video_path: str | Path | None) -> str | None:
        if not video_path:
            return None

        raw_path = str(video_path).strip()
        if not raw_path:
            return None

        candidate = Path(raw_path)
        if candidate.is_absolute():
            return str(candidate)

        for base in (self.project_root, self.project_root / "videos", self.project_root / "assets" / "sample_videos"):
            resolved = (base / candidate).resolve()
            if resolved.exists():
                return str(resolved)

        return str((self.project_root / candidate).resolve())

    def _set_status(self, text: str, color: str) -> None:
        self.health_label.setText(text.upper())
        self.health_dot.setStyleSheet(f"background: {color};")
        self.statusBar().showMessage(text)


class SettingsDialog(QDialog):
    def __init__(self, config: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Monitoring Settings")
        self.setMinimumWidth(520)
        self.config = config
        self.zones = {zone_id: dict(zone_data) for zone_id, zone_data in config.get("zones", {}).items()}
        self.selected_zone_id = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        title = QLabel("Monitoring Settings")
        title.setObjectName("pageTitle")
        description = QLabel(
            "Configure detection sensitivity, input source, and safety zones for the live monitor."
        )
        description.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(description)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(), "General")
        self.tabs.addTab(self._build_zone_tab(), "Zones")
        layout.addWidget(self.tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load_zone_list()

    def _build_general_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        confidence_label = QLabel("Detection confidence")
        confidence_label.setStyleSheet("font-weight: 600;")
        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(0.1, 0.95)
        self.confidence.setSingleStep(0.05)
        self.confidence.setDecimals(2)
        self.confidence.setValue(float(self.config.get("confidence_threshold", 0.5)))

        source_label = QLabel("Default source")
        source_label.setStyleSheet("font-weight: 600;")
        self.source = QComboBox()
        self.source.addItems(["Demo simulation", "Video file", "Camera 0", "Camera 1"])
        if not self.config.get("demo_mode", True):
            self.source.setCurrentIndex(1)

        passenger = self.config.get("passenger_monitor", {})
        bus_label = QLabel("Bus ID")
        self.bus_id = QLineEdit(str(passenger.get("bus_id", "BUS-042")))
        route_label = QLabel("Route")
        self.route = QLineEdit(str(passenger.get("route", "CENTRAL -> CAMPUS")))
        capacity_label = QLabel("Capacity")
        self.capacity = QSpinBox()
        self.capacity.setRange(1, 1000)
        self.capacity.setValue(int(passenger.get("capacity", 40)))

        notice = QLabel(
            "Zone coordinates are stored as normalized polygons in config/config.json. "
            "Use the Zones tab to edit or add custom detection areas."
        )
        notice.setWordWrap(True)
        notice.setObjectName("disclaimer")
        notice.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        layout.addWidget(confidence_label)
        layout.addWidget(self.confidence)
        layout.addWidget(source_label)
        layout.addWidget(self.source)
        layout.addWidget(bus_label)
        layout.addWidget(self.bus_id)
        layout.addWidget(route_label)
        layout.addWidget(self.route)
        layout.addWidget(capacity_label)
        layout.addWidget(self.capacity)
        layout.addWidget(notice)
        layout.addStretch(1)
        return page

    def _build_zone_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(8)
        self.zone_list = QListWidget()
        self.zone_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.zone_list.currentItemChanged.connect(self._on_zone_selected)
        left.addWidget(self.zone_list)

        row_buttons = QHBoxLayout()
        add_button = QPushButton("Add zone")
        add_button.clicked.connect(self._add_zone)
        remove_button = QPushButton("Remove zone")
        remove_button.clicked.connect(self._remove_zone)
        row_buttons.addWidget(add_button)
        row_buttons.addWidget(remove_button)
        left.addLayout(row_buttons)
        left.setStretch(0, 1)

        right = QWidget()
        right_layout = QFormLayout(right)
        right_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        right_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        right_layout.setSpacing(10)

        self.zone_id = QLineEdit()
        self.zone_id.setReadOnly(True)
        self.zone_name = QLineEdit()
        self.zone_type = QComboBox()
        self.zone_type.addItems(["generic", "blind_spot", "safety", "risk"])
        self.alert_message = QLineEdit()
        self.color = QLineEdit()
        self.color.setPlaceholderText("B,G,R")
        color_button = QPushButton("Pick color")
        color_button.clicked.connect(self._choose_color)
        color_row = QHBoxLayout()
        color_row.addWidget(self.color)
        color_row.addWidget(color_button)

        self.points_edit = QPlainTextEdit()
        self.points_edit.setPlaceholderText("Enter one normalized point per line, e.g. 0.05,0.42")
        self.points_edit.setMinimumHeight(140)

        right_layout.addRow("Zone ID:", self.zone_id)
        right_layout.addRow("Name:", self.zone_name)
        right_layout.addRow("Zone type:", self.zone_type)
        right_layout.addRow("Alert message:", self.alert_message)
        right_layout.addRow("Color:", color_row)
        right_layout.addRow("Polygon points:", self.points_edit)

        layout.addLayout(left, 1)
        layout.addWidget(right, 2)
        return page

    def _load_zone_list(self) -> None:
        self.zone_list.clear()
        for zone_id in list(self.zones.keys()):
            self.zone_list.addItem(zone_id)
        if self.zone_list.count() > 0:
            self.zone_list.setCurrentRow(0)

    def _on_zone_selected(self, current, previous) -> None:
        if previous is not None:
            self._save_selected_zone(previous.text())
        if current is None:
            self.selected_zone_id = None
            self._clear_zone_editor()
            return
        self.selected_zone_id = current.text()
        self._load_selected_zone(self.selected_zone_id)

    def _load_selected_zone(self, zone_id: str) -> None:
        zone = self.zones.get(zone_id, {})
        self.zone_id.setText(zone_id)
        self.zone_name.setText(zone.get("name", ""))
        self.zone_type.setCurrentText(zone.get("zone_type", "generic"))
        self.alert_message.setText(zone.get("alert_message", ""))
        self.color.setText(",".join(str(int(c)) for c in zone.get("color", [0, 165, 255])))

        points = zone.get("points", [])
        points_lines = [f"{float(x):.4f},{float(y):.4f}" for x, y in points]
        self.points_edit.setPlainText("\n".join(points_lines))

    def _clear_zone_editor(self) -> None:
        self.zone_id.clear()
        self.zone_name.clear()
        self.zone_type.setCurrentText("generic")
        self.alert_message.clear()
        self.color.clear()
        self.points_edit.clear()

    def _save_selected_zone(self, zone_id: str) -> None:
        if zone_id not in self.zones:
            return
        try:
            points = []
            for line in self.points_edit.toPlainText().splitlines():
                line = line.strip()
                if not line:
                    continue
                x_str, y_str = [part.strip() for part in line.split(",", maxsplit=1)]
                x = float(x_str)
                y = float(y_str)
                points.append([x, y])
        except Exception:
            return

        try:
            color_values = [int(part.strip()) for part in self.color.text().split(",") if part.strip()]
            if len(color_values) != 3:
                raise ValueError
            color_values = [max(0, min(255, c)) for c in color_values]
        except Exception:
            color_values = [0, 165, 255]

        self.zones[zone_id] = {
            "name": self.zone_name.text().strip() or zone_id,
            "points": points,
            "color": color_values,
            "alert_message": self.alert_message.text().strip() or "Zone intrusion detected",
            "zone_type": self.zone_type.currentText(),
        }

    def _choose_color(self) -> None:
        current_color = self.color.text()
        rgb = (255, 165, 0)
        try:
            parts = [int(x.strip()) for x in current_color.split(",") if x.strip()]
            if len(parts) == 3:
                rgb = (parts[2], parts[1], parts[0])
        except Exception:
            pass
        color = QColorDialog.getColor(QColor(*rgb), self, "Select zone color")
        if color.isValid():
            self.color.setText(",".join(str(int(c)) for c in (color.blue(), color.green(), color.red())))

    def _make_unique_zone_id(self) -> str:
        base = "zone"
        index = 1
        while True:
            candidate = f"{base}_{index}"
            if candidate not in self.zones:
                return candidate
            index += 1

    def _add_zone(self) -> None:
        self._save_current_zone_if_any()
        zone_id = self._make_unique_zone_id()
        self.zones[zone_id] = {
            "name": "New Zone",
            "points": [[0.1, 0.1], [0.25, 0.1], [0.25, 0.25], [0.1, 0.25]],
            "color": [0, 165, 255],
            "alert_message": "New zone defined",
            "zone_type": "generic",
        }
        self._load_zone_list()
        self.zone_list.setCurrentRow(self.zone_list.count() - 1)

    def _remove_zone(self) -> None:
        current_item = self.zone_list.currentItem()
        if current_item is None:
            return
        zone_id = current_item.text()
        self.zones.pop(zone_id, None)
        self._load_zone_list()

    def _save_current_zone_if_any(self) -> None:
        if self.selected_zone_id:
            self._save_selected_zone(self.selected_zone_id)

    def _validate_zone_points(self) -> bool:
        for zone_id, zone in self.zones.items():
            points = zone.get("points", [])
            if len(points) < 3:
                return False
            for x, y in points:
                if not (0.0 <= float(x) <= 1.0 and 0.0 <= float(y) <= 1.0):
                    return False
        return True

    def accept(self) -> None:
        self._save_current_zone_if_any()
        if not self._validate_zone_points():
            QMessageBox.warning(
                self,
                "Invalid zone data",
                "Each zone must have at least 3 normalized points in the range 0.0 to 1.0.",
            )
            return
        super().accept()

    def values(self) -> dict:
        self._save_current_zone_if_any()
        return {
            "confidence_threshold": self.confidence.value(),
            "demo_mode": self.source.currentIndex() == 0,
            "camera_source": max(0, self.source.currentIndex() - 2),
            "passenger_monitor": {
                **self.config.get("passenger_monitor", {}),
                "bus_id": self.bus_id.text().strip() or "BUS-042",
                "route": self.route.text().strip() or "CENTRAL -> CAMPUS",
                "capacity": self.capacity.value(),
            },
            "zones": self.zones,
        }


class ZoneDrawDialog(QDialog):
    def __init__(self, default_zone_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Zone Details")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("New Zone Properties")
        title.setObjectName("pageTitle")
        description = QLabel(
            "Enter an identifier and optional metadata for the zone created from the selected frame area."
        )
        description.setWordWrap(True)
        description.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(description)

        form = QFormLayout()
        self.zone_id = QLineEdit(default_zone_id)
        self.zone_name = QLineEdit("Custom Zone")
        self.zone_type = QComboBox()
        self.zone_type.addItems(["generic", "blind_spot", "safety", "risk"])
        self.alert_message = QLineEdit("Zone intrusion detected")
        self.color = QLineEdit("0,165,255")
        pick_color = QPushButton("Pick color")
        pick_color.clicked.connect(self._pick_color)
        color_row = QHBoxLayout()
        color_row.addWidget(self.color)
        color_row.addWidget(pick_color)

        form.addRow("Zone ID:", self.zone_id)
        form.addRow("Name:", self.zone_name)
        form.addRow("Type:", self.zone_type)
        form.addRow("Alert message:", self.alert_message)
        form.addRow("Color (B,G,R):", color_row)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _pick_color(self) -> None:
        try:
            values = [int(v.strip()) for v in self.color.text().split(",") if v.strip()]
            if len(values) == 3:
                current = QColor(values[2], values[1], values[0])
            else:
                current = QColor(255, 165, 255)
        except Exception:
            current = QColor(255, 165, 255)

        selected = QColorDialog.getColor(current, self, "Select zone color")
        if selected.isValid():
            self.color.setText(",".join(str(int(c)) for c in (selected.blue(), selected.green(), selected.red())))

    def accept(self) -> None:
        if not self.zone_id.text().strip():
            QMessageBox.warning(self, "Missing zone id", "Please enter a unique zone identifier.")
            return
        if not self.zone_name.text().strip():
            QMessageBox.warning(self, "Missing name", "Please enter a zone name.")
            return
        try:
            parts = [int(part.strip()) for part in self.color.text().split(",") if part.strip()]
            if len(parts) != 3:
                raise ValueError
            for c in parts:
                if c < 0 or c > 255:
                    raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Invalid color", "Enter a valid B,G,R color triplet.")
            return
        super().accept()

    def values(self) -> tuple[str, dict]:
        return self.zone_id.text().strip(), {
            "name": self.zone_name.text().strip(),
            "points": [],
            "color": [int(part.strip()) for part in self.color.text().split(",") if part.strip()],
            "alert_message": self.alert_message.text().strip(),
            "zone_type": self.zone_type.currentText(),
        }
