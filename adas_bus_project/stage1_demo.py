#!/usr/bin/env python3
"""
ADAS Prototype - Stage 1 Demo
YOLOv8 Object Detection + ByteTrack Tracking + Zone Detection

This demonstrates the core detection and tracking functionality.
Run with: python stage1_demo.py
"""

import cv2
import json
import logging
import numpy as np
import argparse
from pathlib import Path
from typing import Dict, Optional
import sys
from datetime import datetime

# Import our modules
from detection.detector import YOLODetector
from detection.tracker import ByteTracker
from detection.object_filter import ObjectFilter
from zones.zone_manager import ZoneManager
from zones.zone_utils import ZoneVisualizer
from risk.risk_engine import RiskEngine
from logging_system.db_manager import DatabaseManager
from logging_system.export_manager import ExportManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ADASStage1:
    """
    Stage 1 ADAS Prototype
    - YOLOv8 detection
    - ByteTrack tracking
    - Zone-based intrusion detection
    """
    
    def __init__(self, config_path: str = "config/config.json", use_webcam: bool = False):
        """
        Initialize ADAS Stage 1.
        
        Args:
            config_path: Path to configuration file
            use_webcam: Use webcam instead of video file
        """
        self.config_path = Path(config_path)
        self.use_webcam = use_webcam
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize components
        logger.info("Initializing ADAS Stage 1 components...")
        
        # Detector
        model_path = self.config['yolo_settings']['model_path']
        confidence = self.config['yolo_settings']['confidence_threshold']
        device = self.config['yolo_settings']['device']
        
        self.detector = YOLODetector(model_path, confidence, device)
        logger.info(f"✓ YOLOv8 Detector loaded")
        
        # Tracker
        self.tracker = ByteTracker(
            track_thresh=self.config['tracking']['track_thresh'],
            track_buffer=self.config['tracking']['track_buffer'],
            match_thresh=self.config['tracking']['match_thresh'],
            min_box_area=self.config['tracking']['min_box_area']
        )
        logger.info(f"✓ ByteTracker initialized")
        
        # Object Filter
        self.filter = ObjectFilter()
        logger.info(f"✓ ObjectFilter initialized")
        
        # Zone Manager
        self.zone_manager = ZoneManager(frame_width=1600, frame_height=900)
        logger.info(f"✓ ZoneManager initialized")
        
        # Video capture
        self.cap = None
        self.fps = 30
        self.frame_count = 0
        self.frame_width = 1600
        self.frame_height = 900
        
        # Alert tracking and event logging
        self.active_alerts = {}  # {track_id: {zone_id: frame_id}}
        self.alert_cooldown = 30  # Frames before re-alerting
        self.logged_events = []

        database_path = Path(self.config['database']['path'])
        self.db_manager = DatabaseManager(database_path)
        self.export_manager = ExportManager(self.db_manager)
        self.risk_engine = RiskEngine(self.config.get('risk_engine', {}))
        
        logger.info("✓ ADAS Stage 1 initialized successfully")
    
    def _load_config(self) -> Dict:
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            logger.info(f"Configuration loaded from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    def _initialize_video_source(self):
        """Initialize video source (file or webcam)."""
        if self.use_webcam:
            camera_index = self.config['video_settings'].get('webcam_index', 0)
            self.cap = cv2.VideoCapture(camera_index)
            logger.info(f"✓ Webcam {camera_index} opened")
        else:
            video_path = self.config['video_settings'].get('video_source', '')
            if not video_path or not Path(video_path).exists():
                logger.warning(f"Video file not found: {video_path}")
                logger.info("Using webcam instead...")
                self.cap = cv2.VideoCapture(0)
                self.use_webcam = True
            else:
                self.cap = cv2.VideoCapture(video_path)
                logger.info(f"✓ Video file opened: {video_path}")
        
        # Get video properties
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS)) or 30
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1600
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 900
        
        # Reinitialize zone manager with correct dimensions
        self.zone_manager = ZoneManager(self.frame_width, self.frame_height)
        self.zone_manager.load_zones_from_config(self.config)
        
        logger.info(f"Video properties: {self.frame_width}x{self.frame_height} @ {self.fps} FPS")
    
    def process_frame(self, frame: np.ndarray) -> Dict:
        """
        Process a single frame with all Stage 1 components.
        
        Args:
            frame: Input frame (BGR)
            
        Returns:
            Dictionary with detection and tracking results
        """
        # Resize frame to standard size
        frame = cv2.resize(frame, (self.frame_width, self.frame_height))
        
        # Run detection
        detections = self.detector.detect(frame)
        
        # Update tracker
        tracks = self.tracker.update(detections, self.frame_count)
        
        # Check for zone intrusions
        zone_intrusions = self._check_zone_intrusions(tracks)
        
        # Categorize objects
        object_counts = self.filter.categorize_detections(detections)
        
        events = self._log_zone_events(tracks, zone_intrusions)
        risk_score = self.risk_engine.compute_total_risk(events)
        risk_level = self.risk_engine.get_risk_level(risk_score)
        
        return {
            'frame': frame,
            'detections': detections,
            'tracks': tracks,
            'zone_intrusions': zone_intrusions,
            'object_counts': object_counts,
            'events': events,
            'risk_score': risk_score,
            'risk_level': risk_level
        }
    
    def _check_zone_intrusions(self, tracks) -> Dict:
        """
        Check if any tracked objects are in safety zones.
        
        Returns:
            Dictionary of {zone_id: [track_ids]}
        """
        intrusions = {}
        
        for zone_id in self.zone_manager.zones:
            intrusions[zone_id] = []
        
        for track in tracks:
            zones = self.zone_manager.get_zones_containing_object(track.bbox)
            for zone_id in zones:
                intrusions[zone_id].append(track.track_id)

        return intrusions

    def _log_zone_events(self, tracks, zone_intrusions):
        """Generate and persist zone events for the current frame."""
        events = []
        timestamp = datetime.now().isoformat(timespec='seconds')
        track_map = {track.track_id: track for track in tracks}

        for zone_id, track_ids in zone_intrusions.items():
            for track_id in track_ids:
                track = track_map.get(track_id)
                if track is None:
                    continue
                if not self._should_log_event(track_id, zone_id):
                    continue

                risk_score = self.risk_engine.score(track.class_name, zone_id)
                risk_level = self.risk_engine.get_risk_level(risk_score)
                event_type = self._get_event_type(zone_id)
                event = {
                    'timestamp': timestamp,
                    'track_id': track_id,
                    'object_type': track.class_name,
                    'zone': zone_id,
                    'risk_level': risk_level,
                    'event_type': event_type,
                    'risk_score': risk_score
                }
                self.db_manager.add_event(event)
                events.append(event)
                self.logged_events.append(event)
                self.active_alerts.setdefault(track_id, {})[zone_id] = self.frame_count

        return events

    def _should_log_event(self, track_id: int, zone_id: str) -> bool:
        """Decide whether to log an event based on alert cooldown."""
        last_frame = self.active_alerts.get(track_id, {}).get(zone_id)
        if last_frame is None:
            return True
        return (self.frame_count - last_frame) >= self.alert_cooldown

    @staticmethod
    def _get_event_type(zone_id: str) -> str:
        if zone_id in {"left_blind_spot", "right_blind_spot"}:
            return "Blind Spot Alert"
        if zone_id == "door_safety_zone":
            return "Door Safety Alert"
        if zone_id == "left_turn_risk_zone":
            return "Left Turn Collision Warning"
        return "Zone Alert"

    def visualize_results(self, result: Dict) -> np.ndarray:
        """
        Visualize detection and tracking results.
        
        Args:
            result: Dictionary from process_frame()
            
        Returns:
            Visualized frame
        """
        frame = result['frame'].copy()
        tracks = result['tracks']
        zone_intrusions = result['zone_intrusions']
        object_counts = result['object_counts']
        
        # Draw all zones
        frame = ZoneVisualizer.draw_all_zones(frame, self.zone_manager)
        
        # Draw tracks and detections
        for track in tracks:
            x1, y1, x2, y2 = track.bbox
            
            # Determine if object is in any alert zone
            is_alert = any(track.track_id in zone_ids for zone_ids in zone_intrusions.values())
            
            # Draw bounding box
            color = (0, 0, 255) if is_alert else (0, 255, 0)  # Red if alert, green otherwise
            frame = ZoneVisualizer.draw_bounding_box(
                frame, track.bbox,
                label=track.class_name,
                confidence=track.confidence,
                color=color
            )
            
            # Draw track ID
            frame = ZoneVisualizer.draw_track_id(frame, track.bbox, track.track_id, color)
            
            # Draw track history
            if len(track.history) > 2:
                frame = ZoneVisualizer.draw_track_history(frame, track.history, color=color, thickness=1)
        
        # Draw information panel
        info_dict = {
            'Frame': str(self.frame_count),
            'FPS': f"{self.fps:.1f}",
            'Objects': str(object_counts['total']),
            'Pedestrians': str(object_counts['pedestrians']),
            'Motorcycles': str(object_counts['motorcycles']),
            'Vehicles': str(object_counts['vehicles']),
            'Tracks': str(len(tracks)),
            'Risk': str(result.get('risk_score', 0)),
            'Risk Level': result.get('risk_level', 'LOW')
        }
        frame = ZoneVisualizer.draw_info_panel(frame, info_dict, position=(10, 30))
        
        # Draw alerts
        alert_messages = []
        for zone_id, track_ids in zone_intrusions.items():
            if track_ids:
                zone_info = self.zone_manager.get_zone_info(zone_id)
                alert_messages.append(zone_info['alert_message'])
        
        if alert_messages:
            for i, msg in enumerate(alert_messages[:3]):  # Show max 3 alerts
                frame = ZoneVisualizer.draw_alert(frame, msg, position='top', color=(0, 0, 255))
        
        # Add disclaimer at bottom
        cv2.putText(frame, "PROTOTYPE FOR RESEARCH AND EDUCATIONAL USE ONLY",
                   (10, self.frame_height - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
        
        return frame
    
    def run(self, output_path: Optional[str] = None):
        """
        Run the ADAS system on video/webcam.
        
        Args:
            output_path: Optional path to save output video
        """
        self._initialize_video_source()
        
        # Setup video writer if output is needed
        writer = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(
                output_path,
                fourcc,
                self.fps,
                (self.frame_width, self.frame_height)
            )
            logger.info(f"Output video will be saved to: {output_path}")
        
        logger.info("Starting ADAS Stage 1 demo. Press 'q' to quit, 'p' to pause...")
        
        paused = False
        
        try:
            while True:
                if not paused:
                    ret, frame = self.cap.read()
                    if not ret:
                        logger.info("End of video reached")
                        break
                    
                    # Process frame
                    result = self.process_frame(frame)
                    
                    # Visualize
                    vis_frame = self.visualize_results(result)
                    
                    # Write to output video if specified
                    if writer:
                        writer.write(vis_frame)
                    
                    # Display
                    cv2.imshow('ADAS Stage 1 - Detection & Tracking', vis_frame)
                    
                    self.frame_count += 1
                    
                    # Log every 100 frames
                    if self.frame_count % 100 == 0:
                        logger.info(f"Processed {self.frame_count} frames | "
                                  f"Active tracks: {len(result['tracks'])} | "
                                  f"Objects: {result['object_counts']['total']}")
                
                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    logger.info("User quit")
                    break
                elif key == ord('p'):
                    paused = not paused
                    status = "PAUSED" if paused else "PLAYING"
                    logger.info(f"Video {status}")
                elif key == ord('s'):
                    # Save screenshot
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"screenshot_{timestamp}.png"
                    cv2.imwrite(filename, vis_frame)
                    logger.info(f"Screenshot saved: {filename}")
                elif key == ord('c'):
                    destination = Path(f"events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
                    self.export_manager.export_csv(destination)
                    logger.info(f"Exported events CSV: {destination}")
                elif key == ord('x'):
                    destination = Path(f"events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
                    self.export_manager.export_excel(destination)
                    logger.info(f"Exported events Excel: {destination}")
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        
        finally:
            # Cleanup
            if self.cap:
                self.cap.release()
            if writer:
                writer.release()
            cv2.destroyAllWindows()
            
            # Final summary
            logger.info(f"\n{'='*50}")
            logger.info("ADAS Stage 1 Summary:")
            logger.info(f"Total frames processed: {self.frame_count}")
            logger.info(f"Average FPS: {self.frame_count / (self.frame_count / self.fps) if self.frame_count > 0 else 0:.2f}")
            logger.info("="*50)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="ADAS Prototype Stage 1 - Detection & Tracking Demo"
    )
    parser.add_argument(
        '--video',
        type=str,
        default=None,
        help='Path to video file (if not specified, uses webcam)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Path to save output video'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/config.json',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--webcam',
        action='store_true',
        help='Force use of webcam instead of video file'
    )
    
    args = parser.parse_args()
    
    # Create ADAS system
    adas = ADASStage1(config_path=args.config, use_webcam=args.webcam)
    
    # Override video path if specified
    if args.video:
        adas.config['video_settings']['video_source'] = args.video
        adas.use_webcam = False
    
    # Run system
    adas.run(output_path=args.output)


if __name__ == '__main__':
    main()
