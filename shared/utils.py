import yaml
import cv2
import numpy as np
import os
import logging
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)

def load_yaml(path: str) -> Dict[str, Any]:
    """Loads a YAML file from a given path."""
    if not os.path.exists(path):
        logger.error(f"YAML file not found at: {path}")
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load YAML from {path}: {e}")
        return {}

def get_zone_centroid(pts: List[List[float]], width: int = 640, height: int = 480) -> Tuple[float, float]:
    """Calculates the normalized centroid [cx, cy] of a polygon zone."""
    pixel_pts = np.array([[int(p[0] * width), int(p[1] * height)] for p in pts], dtype=np.int32)
    M = cv2.moments(pixel_pts)
    if M["m00"] > 0:
        cx = (M["m10"] / M["m00"]) / width
        cy = (M["m01"] / M["m00"]) / height
        return cx, cy
    # Fallback to mean coordinates
    mean_coords = np.mean(pts, axis=0)
    return float(mean_coords[0]), float(mean_coords[1])

def is_point_in_zone(point: Tuple[float, float], zone_pts: List[List[float]]) -> bool:
    """Checks if a normalized point [x, y] is inside a normalized polygon zone."""
    poly = np.array(zone_pts, np.float32)
    # cv2.pointPolygonTest requires coords to be in the same space, normalized is fine
    res = cv2.pointPolygonTest(poly, (point[0], point[1]), False)
    return res >= 0

def draw_zones(frame: np.ndarray, zones: Dict[str, List[List[float]]], active_zones: Dict[str, bool]) -> np.ndarray:
    """
    Draws polygon zones on a frame.
    Green if active, Yellow/Red if idle.
    """
    h, w = frame.shape[:2]
    overlay = frame.copy()
    
    for zone_name, pts in zones.items():
        pixel_pts = np.array([[int(p[0] * w), int(p[1] * h)] for p in pts], dtype=np.int32)
        is_active = active_zones.get(zone_name, False)
        
        color = (0, 255, 0) if is_active else (0, 165, 255) # Green if active, Orange/Yellow if idle
        # Fill polygon with transparency
        cv2.fillPoly(overlay, [pixel_pts], color)
        # Draw outline
        cv2.polylines(frame, [pixel_pts], True, color, 2)
        
        # Calculate centroid to put text
        cx_norm, cy_norm = get_zone_centroid(pts, w, h)
        cx, cy = int(cx_norm * w), int(cy_norm * h)
        cv2.putText(frame, zone_name, (cx - 30, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        
    # Alpha blending for transparency
    cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)
    return frame
