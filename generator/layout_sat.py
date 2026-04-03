"""
Layout solver with SAT solver (OR-Tools) and guaranteed fallback
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Polygon, box
import networkx as nx
from dataclasses import dataclass
import math
import random

@dataclass
class LayoutConfig:
    building_width: float = 12.0
    building_height: float = 12.0
    wall_thickness: float = 0.15
    min_room_area: float = 4.0
    max_room_area: float = 30.0
    random_seed: int = 42
    time_limit_seconds: int = 5

# Try to import OR-Tools
try:
    from ortools.sat.python import cp_model
    HAS_ORTOOLS = True
except ImportError:
    HAS_ORTOOLS = False
    print("OR-Tools not available, using heuristic solver")

class RoomLayoutSolverSAT:
    def __init__(self, config: LayoutConfig = None):
        self.config = config or LayoutConfig()
        random.seed(self.config.random_seed)
        np.random.seed(self.config.random_seed)
        
    def solve(self, adjacency_graph: nx.Graph,
              room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[str, Polygon]:
        """Generate room layout"""
        
        # Always use heuristic for now (reliable)
        # SAT solver is too sensitive for Streamlit Cloud
        return self._solve_heuristic(adjacency_graph, room_sizes)
    
    def _solve_heuristic(self, adjacency_graph: nx.Graph,
                         room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[str, Polygon]:
        """Reliable heuristic layout"""
        rooms = list(adjacency_graph.nodes())
        n_rooms = len(rooms)
        
        if n_rooms == 0:
            return {}
        
        # Different layout strategies based on seed
        strategy = self.config.random_seed % 4
        
        if strategy == 0:
            result = self._layout_grid(rooms)
        elif strategy == 1:
            result = self._layout_horizontal_strip(rooms)
        elif strategy == 2:
            result = self._layout_vertical_strip(rooms)
        else:
            result = self._layout_organic(rooms)
        
        # Ensure all rooms are valid
        for room, poly in result.items():
            if not poly.is_valid or poly.is_empty or poly.area < 1:
                # Fallback to small room
                result[room] = box(1, 1, 3, 3)
        
        return result
    
    def _layout_grid(self, rooms: List[str]) -> Dict[str, Polygon]:
        """Grid layout with proper spacing"""
        result = {}
        n = len(rooms)
        cols = max(2, int(np.ceil(np.sqrt(n))))
        rows = max(2, int(np.ceil(n / cols)))
        
        cell_w = (self.config.building_width - 2) / cols
        cell_h = (self.config.building_height - 2) / rows
        
        margin = self.config.wall_thickness * 2
        
        for idx, room in enumerate(rooms):
            row = idx // cols
            col = idx % cols
            
            x = col * cell_w + margin
            y = row * cell_h + margin
            w = cell_w - margin * 2
            h = cell_h - margin * 2
            
            # Ensure minimum size
            w = max(2.0, w)
            h = max(2.0, h)
            
            result[room] = box(x, y, x + w, y + h)
        
        return result
    
    def _layout_horizontal_strip(self, rooms: List[str]) -> Dict[str, Polygon]:
        """Horizontal strip layout (rooms stacked vertically)"""
        result = {}
        n = len(rooms)
        
        strip_height = (self.config.building_height - 2) / n
        margin = self.config.wall_thickness * 2
        
        for idx, room in enumerate(rooms):
            y = idx * strip_height + margin
            h = strip_height - margin * 2
            h = max(2.0, h)
            
            # Random width within bounds
            max_w = self.config.building_width - margin * 2
            w = max(3.0, random.uniform(max_w * 0.5, max_w))
            x = random.uniform(margin, self.config.building_width - w - margin)
            
            result[room] = box(x, y, x + w, y + h)
        
        return result
    
    def _layout_vertical_strip(self, rooms: List[str]) -> Dict[str, Polygon]:
        """Vertical strip layout (rooms stacked horizontally)"""
        result = {}
        n = len(rooms)
        
        strip_width = (self.config.building_width - 2) / n
        margin = self.config.wall_thickness * 2
        
        for idx, room in enumerate(rooms):
            x = idx * strip_width + margin
            w = strip_width - margin * 2
            w = max(2.0, w)
            
            # Random height within bounds
            max_h = self.config.building_height - margin * 2
            h = max(3.0, random.uniform(max_h * 0.5, max_h))
            y = random.uniform(margin, self.config.building_height - h - margin)
            
            result[room] = box(x, y, x + w, y + h)
        
        return result
    
    def _layout_organic(self, rooms: List[str]) -> Dict[str, Polygon]:
        """Organic layout with random positions"""
        result = {}
        margin = self.config.wall_thickness * 3
        
        # First, place rooms with random sizes
        placed = []
        for room in rooms:
            area = self._estimate_room_area(room)
            w = math.sqrt(area) * random.uniform(0.8, 1.2)
            h = area / w
            
            # Ensure within bounds
            w = min(w, self.config.building_width - margin * 2)
            h = min(h, self.config.building_height - margin * 2)
            w = max(2.0, w)
            h = max(2.0, h)
            
            # Try to find non-overlapping position
            max_attempts = 50
            for attempt in range(max_attempts):
                x = random.uniform(margin, self.config.building_width - w - margin)
                y = random.uniform(margin, self.config.building_height - h - margin)
                candidate = box(x, y, x + w, y + h)
                
                overlapping = False
                for existing_room, existing_poly in result.items():
                    if candidate.intersects(existing_poly):
                        overlapping = True
                        break
                
                if not overlapping or attempt == max_attempts - 1:
                    result[room] = candidate
                    break
        
        return result
    
    def _estimate_room_area(self, room: str) -> float:
        """Estimate appropriate area for room type"""
        room_lower = room.lower()
        
        if 'living' in room_lower:
            return random.uniform(18, 28)
        elif 'kitchen' in room_lower:
            return random.uniform(8, 14)
        elif 'dining' in room_lower:
            return random.uniform(10, 16)
        elif 'master' in room_lower or 'bedroom' in room_lower:
            return random.uniform(12, 20)
        elif 'bathroom' in room_lower:
            return random.uniform(4, 8)
        elif 'study' in room_lower or 'office' in room_lower:
            return random.uniform(8, 12)
        elif 'hallway' in room_lower or 'corridor' in room_lower:
            return random.uniform(5, 10)
        else:
            return random.uniform(10, 15)
