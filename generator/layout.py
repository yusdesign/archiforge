"""
Procedural layout generation from adjacency graphs
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
import networkx as nx
from dataclasses import dataclass
import random

@dataclass
class LayoutConfig:
    building_width: float = 12.0
    building_height: float = 12.0
    wall_thickness: float = 0.15
    min_room_area: float = 4.0
    prefer_square_rooms: bool = True

class ProceduralLayoutSolver:
    def __init__(self, config: LayoutConfig = None):
        self.config = config or LayoutConfig()
        random.seed(42)
        np.random.seed(42)
        
    def solve(self, adjacency_graph: nx.Graph,
              room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[str, Polygon]:
        """Generate room polygons from adjacency graph"""
        
        rooms = {}
        
        # Simple grid-based layout
        n_rooms = len(adjacency_graph.nodes)
        cols = max(2, int(np.ceil(np.sqrt(n_rooms))))
        rows = max(2, int(np.ceil(n_rooms / cols)))
        
        cell_w = self.config.building_width / cols
        cell_h = self.config.building_height / rows
        
        for idx, room in enumerate(adjacency_graph.nodes):
            row = idx // cols
            col = idx % cols
            
            x1 = col * cell_w + self.config.wall_thickness
            y1 = row * cell_h + self.config.wall_thickness
            x2 = x1 + cell_w - self.config.wall_thickness * 2
            y2 = y1 + cell_h - self.config.wall_thickness * 2
            
            # Ensure minimum size
            if x2 - x1 < 2:
                x2 = x1 + 2
            if y2 - y1 < 2:
                y2 = y1 + 2
            
            # Create room polygon
            room_poly = box(x1, y1, x2, y2)
            
            if room_poly.is_valid and room_poly.area > 0:
                rooms[room] = room_poly
        
        # Merge adjacent rooms if they should be connected
        for u, v in adjacency_graph.edges():
            if u in rooms and v in rooms:
                # Create doorway by making rooms touch
                rooms = self._create_doorway(rooms, u, v)
        
        # Ensure all rooms are within bounds
        for room in rooms:
            rooms[room] = self._clip_to_bounds(rooms[room])
        
        return rooms
    
    def _create_doorway(self, rooms: Dict[str, Polygon], room_a: str, room_b: str) -> Dict[str, Polygon]:
        """Make two rooms adjacent by extending towards each other"""
        poly_a = rooms[room_a]
        poly_b = rooms[room_b]
        
        # If already touching, return
        if poly_a.distance(poly_b) < 0.1:
            return rooms
        
        # Get centroids
        ca = poly_a.centroid
        cb = poly_b.centroid
        
        # Direction vector
        dx = cb.x - ca.x
        dy = cb.y - ca.y
        dist = max(0.1, np.sqrt(dx*dx + dy*dy))
        
        if dist > 0:
            dx /= dist
            dy /= dist
            
            # Extend both rooms towards each other
            extension = min(dist / 2, 1.0)
            new_a = box(
                min(poly_a.bounds[0], ca.x + dx * extension),
                min(poly_a.bounds[1], ca.y + dy * extension),
                max(poly_a.bounds[2], ca.x + dx * extension),
                max(poly_a.bounds[3], ca.y + dy * extension)
            )
            rooms[room_a] = new_a
            
            new_b = box(
                min(poly_b.bounds[0], cb.x - dx * extension),
                min(poly_b.bounds[1], cb.y - dy * extension),
                max(poly_b.bounds[2], cb.x - dx * extension),
                max(poly_b.bounds[3], cb.y - dy * extension)
            )
            rooms[room_b] = new_b
        
        return rooms
    
    def _clip_to_bounds(self, polygon: Polygon) -> Polygon:
        """Ensure polygon stays within building bounds"""
        bounds = box(0, 0, self.config.building_width, self.config.building_height)
        clipped = polygon.intersection(bounds)
        
        if clipped.is_empty:
            return polygon
        if clipped.geom_type == 'Polygon':
            return clipped
        if clipped.geom_type == 'MultiPolygon':
            return max(clipped.geoms, key=lambda p: p.area)
        return polygon
