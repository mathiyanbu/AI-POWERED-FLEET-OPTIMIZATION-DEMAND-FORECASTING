"""
YOLOv8 Object Detection Module
Loads and manages YOLOv8 model for vehicle and pedestrian detection
"""

import cv2
import numpy as np
from ultralytics import YOLO
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class YOLODetector:
    """
    Wrapper class for YOLOv8 object detection.
    
    Handles:
    - Model loading
    - Inference
    - Class filtering
    - Confidence thresholding
    """
    
    def __init__(self, model_path: str, confidence_threshold: float = 0.5, device: str = "cpu"):
        """
        Initialize YOLOv8 detector.
        
        Args:
            model_path: Path to YOLOv8 model file (e.g., 'yolov8n.pt')
            confidence_threshold: Minimum confidence for detections (0.0 - 1.0)
            device: Device to use ('cpu', 'cuda', 'mps')
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.device = device
        
        try:
            self.model = YOLO(model_path)
            self.model.to(device)
            logger.info(f"YOLOv8 model loaded from {model_path} on device: {device}")
        except Exception as e:
            logger.error(f"Failed to load YOLOv8 model: {e}")
            raise
        
        # Class mapping from COCO dataset
        self.class_names = self.model.names
        
        # Filter to only these classes
        self.target_classes = {
            'person': 0,
            'bicycle': 1,
            'motorcycle': 3,
            'car': 2,
            'bus': 5,
            'truck': 7
        }
    
    def detect(self, frame: np.ndarray) -> Dict:
        """
        Run YOLOv8 inference on a frame.
        
        Args:
            frame: Input image/frame (BGR format)
            
        Returns:
            Dictionary containing:
            - 'boxes': List of [x1, y1, x2, y2] coordinates
            - 'confidences': List of confidence scores
            - 'class_ids': List of class IDs
            - 'class_names': List of class names
            - 'raw_results': Raw YOLO results object
        """
        try:
            # Run inference
            results = self.model(frame, conf=self.confidence_threshold, verbose=False)
            result = results[0]
            
            detections = {
                'boxes': [],
                'confidences': [],
                'class_ids': [],
                'class_names': [],
                'raw_results': result
            }
            
            # Extract detections
            if result.boxes is not None:
                boxes = result.boxes.xyxy.cpu().numpy()  # [x1, y1, x2, y2]
                confidences = result.boxes.conf.cpu().numpy()
                class_ids = result.boxes.cls.cpu().numpy().astype(int)
                
                for box, conf, class_id in zip(boxes, confidences, class_ids):
                    # Filter by target classes only
                    if class_id in self.target_classes.values():
                        detections['boxes'].append(box)
                        detections['confidences'].append(float(conf))
                        detections['class_ids'].append(int(class_id))
                        detections['class_names'].append(self.class_names[class_id])
            
            # Convert lists to numpy arrays for easier processing
            if detections['boxes']:
                detections['boxes'] = np.array(detections['boxes'])
                detections['confidences'] = np.array(detections['confidences'])
                detections['class_ids'] = np.array(detections['class_ids'])
            else:
                detections['boxes'] = np.array([])
                detections['confidences'] = np.array([])
                detections['class_ids'] = np.array([])
            
            return detections
            
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return {
                'boxes': np.array([]),
                'confidences': np.array([]),
                'class_ids': np.array([]),
                'class_names': [],
                'raw_results': None
            }
    
    def get_class_id_by_name(self, class_name: str) -> Optional[int]:
        """Get class ID from class name."""
        for coco_class_id, coco_name in self.class_names.items():
            if coco_name == class_name:
                return coco_class_id
        return None
    
    def filter_classes(self, detections: Dict, target_classes: List[str]) -> Dict:
        """
        Filter detections to only include specific classes.
        
        Args:
            detections: Detection results from detect()
            target_classes: List of class names to keep (e.g., ['person', 'car'])
            
        Returns:
            Filtered detections dictionary
        """
        if len(detections['class_names']) == 0:
            return detections
        
        target_class_ids = set()
        for class_name in target_classes:
            if class_name in self.target_classes:
                target_class_ids.add(self.target_classes[class_name])
        
        mask = np.array([cid in target_class_ids for cid in detections['class_ids']])
        
        filtered = {
            'boxes': detections['boxes'][mask] if len(detections['boxes']) > 0 else np.array([]),
            'confidences': detections['confidences'][mask] if len(detections['confidences']) > 0 else np.array([]),
            'class_ids': detections['class_ids'][mask] if len(detections['class_ids']) > 0 else np.array([]),
            'class_names': [name for i, name in enumerate(detections['class_names']) if mask[i]],
            'raw_results': detections['raw_results']
        }
        
        return filtered
