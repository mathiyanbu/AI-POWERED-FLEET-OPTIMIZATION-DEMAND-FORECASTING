"""
Object Filter Module
Filters and categorizes detected objects
"""

import numpy as np
from typing import List, Dict, Set
import logging

logger = logging.getLogger(__name__)


class ObjectFilter:
    """Filters detected objects by class, confidence, and area."""
    
    # Define which classes are of interest
    VULNERABLE_ROAD_USERS = {'person', 'bicycle', 'motorcycle'}
    VEHICLES = {'car', 'bus', 'truck'}
    ALL_CLASSES = VULNERABLE_ROAD_USERS | VEHICLES
    
    def __init__(self):
        """Initialize object filter."""
        self.class_categories = {
            'pedestrian': ['person'],
            'cyclist': ['bicycle'],
            'motorcycle_driver': ['motorcycle'],
            'car': ['car'],
            'bus': ['bus'],
            'truck': ['truck'],
            'vehicle': ['car', 'bus', 'truck'],
            'vulnerable': ['person', 'bicycle', 'motorcycle']
        }
    
    def filter_by_class(self, detections: Dict, target_classes: List[str]) -> Dict:
        """
        Filter detections to only include specific classes.
        
        Args:
            detections: Detection dict with 'class_names'
            target_classes: List of class names to keep
            
        Returns:
            Filtered detections dictionary
        """
        if not detections['class_names']:
            return detections
        
        mask = np.array([name in target_classes for name in detections['class_names']])
        
        filtered = {
            'boxes': detections['boxes'][mask] if len(detections['boxes']) > 0 else np.array([]),
            'confidences': detections['confidences'][mask] if len(detections['confidences']) > 0 else np.array([]),
            'class_ids': detections['class_ids'][mask] if len(detections['class_ids']) > 0 else np.array([]),
            'class_names': [name for i, name in enumerate(detections['class_names']) if mask[i]],
            'raw_results': detections['raw_results']
        }
        
        return filtered
    
    def filter_by_category(self, detections: Dict, category: str) -> Dict:
        """
        Filter detections by predefined category.
        
        Categories:
        - 'pedestrian': Only persons
        - 'cyclist': Bicycles and motorcycles
        - 'vehicle': Cars, buses, trucks
        - 'vulnerable': Pedestrians, cyclists, motorcycles
        - 'all': All detected classes
        
        Args:
            detections: Detection dict
            category: Category name
            
        Returns:
            Filtered detections
        """
        if category not in self.class_categories:
            logger.warning(f"Unknown category: {category}")
            return detections
        
        target_classes = self.class_categories[category]
        return self.filter_by_class(detections, target_classes)
    
    def filter_by_confidence(self, detections: Dict, min_confidence: float) -> Dict:
        """
        Filter detections by confidence threshold.
        
        Args:
            detections: Detection dict
            min_confidence: Minimum confidence score (0.0 - 1.0)
            
        Returns:
            Filtered detections
        """
        if len(detections['confidences']) == 0:
            return detections
        
        mask = detections['confidences'] >= min_confidence
        
        filtered = {
            'boxes': detections['boxes'][mask] if len(detections['boxes']) > 0 else np.array([]),
            'confidences': detections['confidences'][mask] if len(detections['confidences']) > 0 else np.array([]),
            'class_ids': detections['class_ids'][mask] if len(detections['class_ids']) > 0 else np.array([]),
            'class_names': [name for i, name in enumerate(detections['class_names']) if mask[i]],
            'raw_results': detections['raw_results']
        }
        
        return filtered
    
    def filter_by_area(self, detections: Dict, min_area: float = 0, max_area: float = float('inf')) -> Dict:
        """
        Filter detections by bounding box area.
        
        Args:
            detections: Detection dict
            min_area: Minimum box area in pixels
            max_area: Maximum box area in pixels
            
        Returns:
            Filtered detections
        """
        if len(detections['boxes']) == 0:
            return detections
        
        areas = []
        for box in detections['boxes']:
            x1, y1, x2, y2 = box
            area = (x2 - x1) * (y2 - y1)
            areas.append(area)
        
        mask = (np.array(areas) >= min_area) & (np.array(areas) <= max_area)
        
        filtered = {
            'boxes': detections['boxes'][mask] if len(detections['boxes']) > 0 else np.array([]),
            'confidences': detections['confidences'][mask] if len(detections['confidences']) > 0 else np.array([]),
            'class_ids': detections['class_ids'][mask] if len(detections['class_ids']) > 0 else np.array([]),
            'class_names': [name for i, name in enumerate(detections['class_names']) if mask[i]],
            'raw_results': detections['raw_results']
        }
        
        return filtered
    
    def categorize_detections(self, detections: Dict) -> Dict:
        """
        Categorize all detections into groups.
        
        Returns dictionary with counts of each type:
        {
            'pedestrians': int,
            'cyclists': int,
            'motorcycles': int,
            'cars': int,
            'buses': int,
            'trucks': int,
            'total': int
        }
        """
        counts = {
            'pedestrians': 0,
            'cyclists': 0,
            'motorcycles': 0,
            'cars': 0,
            'buses': 0,
            'trucks': 0,
            'total': len(detections['class_names'])
        }
        
        for class_name in detections['class_names']:
            if class_name == 'person':
                counts['pedestrians'] += 1
            elif class_name == 'bicycle':
                counts['cyclists'] += 1
            elif class_name == 'motorcycle':
                counts['motorcycles'] += 1
            elif class_name == 'car':
                counts['cars'] += 1
            elif class_name == 'bus':
                counts['buses'] += 1
            elif class_name == 'truck':
                counts['trucks'] += 1
        
        return counts
    
    def get_vulnerable_objects(self, detections: Dict) -> Dict:
        """Get only vulnerable road users (pedestrians, cyclists, motorcycles)."""
        return self.filter_by_category(detections, 'vulnerable')
    
    def get_vehicles(self, detections: Dict) -> Dict:
        """Get only vehicles (cars, buses, trucks)."""
        return self.filter_by_category(detections, 'vehicle')
    
    def has_high_risk_objects(self, detections: Dict, risk_threshold: float = 0.7) -> bool:
        """
        Check if detections contain any high-confidence vulnerable objects.
        
        Args:
            detections: Detection dict
            risk_threshold: Confidence threshold for high risk
            
        Returns:
            True if any high-confidence vulnerable object found
        """
        vulnerable = self.get_vulnerable_objects(detections)
        if len(vulnerable['confidences']) > 0:
            return np.max(vulnerable['confidences']) >= risk_threshold
        return False
