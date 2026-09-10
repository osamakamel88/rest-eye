import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import cv2
from .config import ZONES_FILE

class ZoneManager:
    """
    Manages custom restricted polygon zones (e.g. Storage Shelf, Freezer, Prep Table).
    Coordinates are stored as normalized floats [[x, y], ...] where 0.0 <= x, y <= 1.0
    """
    def __init__(self, filepath: Path = ZONES_FILE):
        self.filepath = filepath
        self.zones: List[Dict[str, Any]] = []
        self.load_zones()

    def load_zones(self) -> None:
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.zones = data.get("zones", [])
                    return
            except Exception as e:
                print(f"[ZoneManager] Error loading zones from {self.filepath}: {e}")
        
        # Default starter zones if none exist
        self.zones = [
            {
                "id": "zone-storage-01",
                "name": "Restricted Inventory / Storage",
                "type": "restricted_eating",  # "restricted_eating", "restricted_access", "warning"
                "color": "#ef4444",  # Red
                "polygon": [
                    [0.05, 0.20],
                    [0.45, 0.20],
                    [0.45, 0.85],
                    [0.05, 0.85]
                ],
                "alert_on_eating": True,
                "alert_on_loiter": True,
                "loiter_threshold_sec": 90.0
            }
        ]
        self.save_zones()

    def save_zones(self) -> None:
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({"zones": self.zones}, f, indent=2)
        except Exception as e:
            print(f"[ZoneManager] Error saving zones: {e}")

    def get_zones(self) -> List[Dict[str, Any]]:
        return self.zones

    def update_zones(self, zones: List[Dict[str, Any]]) -> None:
        self.zones = zones
        self.save_zones()

    def add_zone(self, name: str, polygon: List[List[float]], zone_type: str = "restricted_eating", color: str = "#ef4444") -> Dict[str, Any]:
        new_zone = {
            "id": f"zone-{len(self.zones)+1:02d}",
            "name": name,
            "type": zone_type,
            "color": color,
            "polygon": polygon,
            "alert_on_eating": True,
            "alert_on_loiter": True,
            "loiter_threshold_sec": 90.0
        }
        self.zones.append(new_zone)
        self.save_zones()
        return new_zone

    def remove_zone(self, zone_id: str) -> bool:
        initial_len = len(self.zones)
        self.zones = [z for z in self.zones if z.get("id") != zone_id]
        if len(self.zones) != initial_len:
            self.save_zones()
            return True
        return False

    def is_point_in_polygon(self, point: Tuple[float, float], polygon_norm: List[List[float]]) -> bool:
        """
        Point-in-polygon test with ray casting.
        point: (x, y) normalized [0, 1]
        polygon_norm: [[x1, y1], [x2, y2], ...] normalized [0, 1]
        """
        if len(polygon_norm) < 3:
            return False
        
        x, y = point
        n = len(polygon_norm)
        inside = False
        p1x, p1y = polygon_norm[0]
        for i in range(n + 1):
            p2x, p2y = polygon_norm[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def check_person_in_zones(self, bbox: List[float], img_w: int, img_h: int) -> List[Dict[str, Any]]:
        """
        bbox: [x1, y1, x2, y2] in pixels
        Checks if person center or bottom-center (feet) is within any active zone.
        """
        if img_w <= 0 or img_h <= 0:
            return []
        
        x1, y1, x2, y2 = bbox
        center_x = ((x1 + x2) / 2.0) / img_w
        feet_y = y2 / img_h
        center_y = ((y1 + y2) / 2.0) / img_h
        
        active_zones = []
        for zone in self.zones:
            poly = zone.get("polygon", [])
            # Check feet position (ground location) or center of body
            if self.is_point_in_polygon((center_x, feet_y), poly) or self.is_point_in_polygon((center_x, center_y), poly):
                active_zones.append(zone)
                
        return active_zones
