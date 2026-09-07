"""
ByteTrack Object Tracking Module
Tracks detected objects across frames with persistent IDs
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Track:
    """Represents a tracked object with persistent ID."""
    track_id: int
    class_name: str
    class_id: int
    bbox: np.ndarray  # [x1, y1, x2, y2]
    confidence: float
    frame_count: int = 1
    last_seen_frame: int = 0
    history: List[np.ndarray] = field(default_factory=list)
    feature_vector: Optional[np.ndarray] = None
    first_detected_frame: int = 0
    alerts: Dict = field(default_factory=dict)  # Store alert info
    
    def update(self, bbox: np.ndarray, confidence: float, frame_id: int):
        """Update track with new detection."""
        self.bbox = bbox
        self.confidence = confidence
        self.frame_count += 1
        self.last_seen_frame = frame_id
        self.history.append(bbox.copy())
        # Keep only last 30 frames of history
        if len(self.history) > 30:
            self.history.pop(0)
    
    def get_center(self) -> Tuple[float, float]:
        """Get center point of bounding box."""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)
    
    def get_width_height(self) -> Tuple[float, float]:
        """Get width and height of bounding box."""
        x1, y1, x2, y2 = self.bbox
        return (x2 - x1, y2 - y1)


class ByteTracker:
    """
    Simple ByteTrack implementation for multi-object tracking.
    
    Features:
    - Persistent object IDs
    - Track history
    - No duplicate alerts
    - Configurable track buffer
    """
    
    def __init__(self, track_thresh: float = 0.5, track_buffer: int = 30, 
                 match_thresh: float = 0.8, min_box_area: int = 10):
        """
        Initialize ByteTrack tracker.
        
        Args:
            track_thresh: Minimum confidence to start tracking
            track_buffer: Frames to keep track without detection
            match_thresh: IoU threshold for matching detections to tracks
            min_box_area: Minimum area for valid detections
        """
        self.track_thresh = track_thresh
        self.track_buffer = track_buffer
        self.match_thresh = match_thresh
        self.min_box_area = min_box_area
        
        self.tracks: List[Track] = []
        self.next_track_id = 1
        self.frame_id = 0
        
        logger.info(f"ByteTracker initialized: buffer={track_buffer}, thresh={match_thresh}")
    
    def update(self, detections: Dict, frame_id: int) -> List[Track]:
        """
        Update tracks with new detections.
        
        Args:
            detections: Dictionary with 'boxes', 'confidences', 'class_ids', 'class_names'
            frame_id: Current frame number
            
        Returns:
            List of active Track objects
        """
        self.frame_id = frame_id
        
        # Extract detections
        boxes = detections.get('boxes', np.array([]))
        confidences = detections.get('confidences', np.array([]))
        class_ids = detections.get('class_ids', np.array([]))
        class_names = detections.get('class_names', [])
        
        # Filter high confidence detections
        high_conf_dets = []
        for i, (box, conf, class_id, class_name) in enumerate(
            zip(boxes, confidences, class_ids, class_names)):
            
            # Check box area
            x1, y1, x2, y2 = box
            area = (x2 - x1) * (y2 - y1)
            if area >= self.min_box_area and conf >= self.track_thresh:
                high_conf_dets.append((box, conf, class_id, class_name, i))
        
        # Match detections to existing tracks
        matched_tracks, unmatched_dets, unmatched_tracks = self._match_detections(
            high_conf_dets)
        
        # Update matched tracks
        for track_idx, det_idx in matched_tracks:
            box, conf, class_id, class_name, _ = high_conf_dets[det_idx]
            self.tracks[track_idx].update(box, conf, frame_id)
        
        # Create new tracks for unmatched detections
        for det_idx in unmatched_dets:
            box, conf, class_id, class_name, _ = high_conf_dets[det_idx]
            self._create_new_track(box, conf, class_id, class_name, frame_id)
        
        # Remove dead tracks
        self._remove_dead_tracks()
        
        return self.tracks
    
    def _match_detections(self, detections: List) -> Tuple[List, List, List]:
        """
        Simple IoU-based matching between tracks and detections.
        
        Returns:
            matched_tracks: List of (track_idx, det_idx) tuples
            unmatched_dets: List of unmatched detection indices
            unmatched_tracks: List of unmatched track indices
        """
        matched_tracks = []
        unmatched_dets = list(range(len(detections)))
        unmatched_tracks = list(range(len(self.tracks)))
        
        if len(detections) == 0 or len(self.tracks) == 0:
            return matched_tracks, unmatched_dets, unmatched_tracks
        
        # Calculate IoU between all tracks and detections
        iou_matrix = np.zeros((len(self.tracks), len(detections)))
        
        for track_idx, track in enumerate(self.tracks):
            for det_idx, (det_box, _, _, _, _) in enumerate(detections):
                iou = self._compute_iou(track.bbox, det_box)
                iou_matrix[track_idx, det_idx] = iou
        
        # Hungarian-like greedy matching
        while True:
            max_iou = np.max(iou_matrix) if iou_matrix.size > 0 else -1
            if max_iou < self.match_thresh:
                break
            
            track_idx, det_idx = np.unravel_index(
                np.argmax(iou_matrix), iou_matrix.shape)
            
            matched_tracks.append((track_idx, det_idx))
            unmatched_dets.remove(det_idx)
            unmatched_tracks.remove(track_idx)
            
            # Mark row and column as used
            iou_matrix[track_idx, :] = -1
            iou_matrix[:, det_idx] = -1
        
        return matched_tracks, unmatched_dets, unmatched_tracks
    
    @staticmethod
    def _compute_iou(box1: np.ndarray, box2: np.ndarray) -> float:
        """Compute Intersection over Union of two boxes."""
        x1_min, y1_min, x1_max, y1_max = box1
        x2_min, y2_min, x2_max, y2_max = box2
        
        # Intersection
        inter_xmin = max(x1_min, x2_min)
        inter_ymin = max(y1_min, y2_min)
        inter_xmax = min(x1_max, x2_max)
        inter_ymax = min(y1_max, y2_max)
        
        if inter_xmax <= inter_xmin or inter_ymax <= inter_ymin:
            return 0.0
        
        inter_area = (inter_xmax - inter_xmin) * (inter_ymax - inter_ymin)
        
        # Union
        box1_area = (x1_max - x1_min) * (y1_max - y1_min)
        box2_area = (x2_max - x2_min) * (y2_max - y2_min)
        union_area = box1_area + box2_area - inter_area
        
        return inter_area / union_area if union_area > 0 else 0.0
    
    def _create_new_track(self, bbox: np.ndarray, confidence: float, 
                         class_id: int, class_name: str, frame_id: int):
        """Create a new track."""
        track = Track(
            track_id=self.next_track_id,
            class_name=class_name,
            class_id=class_id,
            bbox=bbox,
            confidence=confidence,
            first_detected_frame=frame_id,
            last_seen_frame=frame_id
        )
        track.history.append(bbox.copy())
        self.tracks.append(track)
        self.next_track_id += 1
    
    def _remove_dead_tracks(self):
        """Remove tracks not updated for too long."""
        alive_tracks = []
        for track in self.tracks:
            if self.frame_id - track.last_seen_frame <= self.track_buffer:
                alive_tracks.append(track)
        self.tracks = alive_tracks
    
    def get_track_by_id(self, track_id: int) -> Optional[Track]:
        """Get track by ID."""
        for track in self.tracks:
            if track.track_id == track_id:
                return track
        return None
    
    def get_tracks_by_class(self, class_name: str) -> List[Track]:
        """Get all tracks of a specific class."""
        return [t for t in self.tracks if t.class_name == class_name]
    
    def reset(self):
        """Reset tracker state."""
        self.tracks = []
        self.next_track_id = 1
        self.frame_id = 0
