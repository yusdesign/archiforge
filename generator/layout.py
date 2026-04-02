"""
Enhanced procedural layout generation with realistic room shapes
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Polygon, box, Point, LineString
from shapely.ops import unary_union, polygonize
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
    hallway_width: float = 1.2
    random_seed: int = 42

class ProceduralLayoutSolver:
    def __init__(self, config: LayoutConfig = None):
        self.config = config or LayoutConfig()
        random.seed(self.config.random_seed)
        np.random.seed(self.config.random_seed)
        
    def solve(self, adjacency_graph: nx.Graph,
              room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[str, Polygon]:
        """Generate realistic room polygons using recursive partitioning"""
        
        # Create initial bounding box
        outer_box = box(0, 0, self.config.building_width, self.config.building_height)
        
        # Sort rooms by importance (living room first, then bedrooms, etc.)
        room_list = list(adjacency_graph.nodes())
        room_priority = self._prioritize_rooms(room_list)
        
        # Recursively partition space
        rooms = {}
        remaining_spaces = [outer_box]
        
        for room in room_priority:
            if not remaining_spaces:
                break
                
            # Get target area
            target_area = self._get_target_area(room, room_sizes)
            
            # Find best space for this room
            best_space = None
            best_fit = float('inf')
            
            for space in remaining_spaces:
                if space.area >= target_area * 0.7:
                    fit = abs(space.area - target_area)
                    if fit < best_fit:
                        best_fit = fit
                        best_space = space
            
            if best_space:
                # Extract room polygon
                room_poly = self._extract_room(best_space, target_area, room)
                rooms[room] = room_poly
                
                # Update remaining spaces
                remaining_spaces.remove(best_space)
                new_spaces = self._split_remaining_space(best_space, room_poly)
                remaining_spaces.extend(new_spaces)
        
        # Add hallway connections
        rooms = self._add_hallways(rooms, adjacency_graph)
        
        # Ensure all rooms are valid
        for room, poly in rooms.items():
            if not poly.is_valid or poly.is_empty:
                # Fallback to simple box
                rooms[room] = self._create_fallback_room(room, len(rooms))
        
        return rooms
    
    def _prioritize_rooms(self, room_list: List[str]) -> List[str]:
        """Prioritize rooms by importance"""
        priority_order = ['living', 'kitchen', 'dining', 'master_bedroom', 'bedroom', 'bathroom', 'hallway', 'closet']
        
        def get_priority(room):
            for i, p in enumerate(priority_order):
                if p in room.lower():
                    return i
            return len(priority_order)
        
        return sorted(room_list, key=get_priority)
    
    def _get_target_area(self, room: str, room_sizes: Dict) -> float:
        """Get target area for room type"""
        area_map = {
            'living': 25.0,
            'kitchen': 12.0,
            'dining': 12.0,
            'bedroom': 14.0,
            'bathroom': 6.0,
            'hallway': 8.0,
            'closet': 3.0
        }
        
        for key in area_map:
            if key in room.lower():
                base_area = area_map[key]
                # Add some randomness (±20%)
                variation = random.uniform(0.8, 1.2)
                return base_area * variation
        
        return 12.0  # default
    
    def _extract_room(self, space: Polygon, target_area: float, room_name: str) -> Polygon:
        """Extract a room polygon from available space"""
        # Try different shapes
        attempts = []
        
        # Square/rectangle
        side = np.sqrt(target_area)
        width = side * random.uniform(0.8, 1.2)
        height = target_area / width
        
        # Try to fit rectangle in space
        bounds = space.bounds
        space_width = bounds[2] - bounds[0]
        space_height = bounds[3] - bounds[1]
        
        if width <= space_width and height <= space_height:
            # Place rectangle
            x = bounds[0] + random.uniform(0, space_width - width)
            y = bounds[1] + random.uniform(0, space_height - height)
            room = box(x, y, x + width, y + height)
        else:
            # Scale down
            scale = min(space_width / width, space_height / height) * 0.9
            width *= scale
            height *= scale
            x = bounds[0] + (space_width - width) / 2
            y = bounds[1] + (space_height - height) / 2
            room = box(x, y, x + width, y + height)
        
        # Add slight irregularity for realistic look
        if 'living' in room_name.lower() or 'bedroom' in room_name.lower():
            room = self._add_irregularity(room)
        
        return room
    
    def _add_irregularity(self, polygon: Polygon) -> Polygon:
        """Add slight irregularity to room shape"""
        if random.random() > 0.6:
            # Add a small notch or bump
            coords = list(polygon.exterior.coords)
            if len(coords) > 4:
                idx = random.randint(1, len(coords) - 2)
                x, y = coords[idx]
                offset = 0.3 * random.uniform(-1, 1)
                if idx % 2 == 0:
                    coords[idx] = (x + offset, y)
                else:
                    coords[idx] = (x, y + offset)
                return Polygon(coords)
        return polygon
    
    def _split_remaining_space(self, original_space: Polygon, room: Polygon) -> List[Polygon]:
        """Split remaining space after room extraction"""
        remaining = original_space.difference(room)
        
        if remaining.is_empty:
            return []
        
        # Split into separate polygons
        if remaining.geom_type == 'Polygon':
            return [remaining]
        elif remaining.geom_type == 'MultiPolygon':
            return list(remaining.geoms)
        return []
    
    def _add_hallways(self, rooms: Dict[str, Polygon], graph: nx.Graph) -> Dict[str, Polygon]:
        """Add hallway connections between adjacent rooms"""
        # Find rooms that need connections
        connections = []
        
        for u, v in graph.edges():
            if u in rooms and v in rooms:
                # Create corridor between rooms
                centroid_u = rooms[u].centroid
                centroid_v = rooms[v].centroid
                
                # Create hallway polygon
                hallway = self._create_hallway(centroid_u, centroid_v)
                if hallway and hallway.is_valid:
                    hallway_name = f"hallway_{u}_{v}"
                    rooms[hallway_name] = hallway
                    connections.append((u, hallway_name))
                    connections.append((v, hallway_name))
        
        return rooms
    
    def _create_hallway(self, point_a: Point, point_b: Point) -> Optional[Polygon]:
        """Create a hallway polygon between two points"""
        dx = point_b.x - point_a.x
        dy = point_b.y - point_a.y
        length = np.sqrt(dx*dx + dy*dy)
        
        if length < 0.1:
            return None
        
        # Create hallway as a rectangle
        width = self.config.hallway_width
        angle = np.arctan2(dy, dx)
        
        # Calculate corner points
        perp_x = -np.sin(angle) * width / 2
        perp_y = np.cos(angle) * width / 2
        
        p1 = (point_a.x + perp_x, point_a.y + perp_y)
        p2 = (point_a.x - perp_x, point_a.y - perp_y)
        p3 = (point_b.x - perp_x, point_b.y - perp_y)
        p4 = (point_b.x + perp_x, point_b.y + perp_y)
        
        return Polygon([p1, p2, p3, p4])
    
    def _create_fallback_room(self, room: str, index: int) -> Polygon:
        """Create a simple fallback room"""
        cols = max(2, int(np.ceil(np.sqrt(index + 1))))
        row = index // cols
        col = index % cols
        
        cell_w = self.config.building_width / cols
        cell_h = self.config.building_height / cols
        
        x = col * cell_w + self.config.wall_thickness
        y = row * cell_h + self.config.wall_thickness
        w = cell_w - self.config.wall_thickness * 2
        h = cell_h - self.config.wall_thickness * 2
        
        return box(x, y, x + w, y + h)
