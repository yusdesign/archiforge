"""
Procedural layout generation with shared walls between rooms
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Polygon, box, Point, LineString, MultiPolygon
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
    max_room_area: float = 30.0
    hallway_width: float = 1.2
    prefer_square_rooms: bool = True
    random_seed: int = 42

class ProceduralLayoutSolver:
    def __init__(self, config: LayoutConfig = None):
        self.config = config or LayoutConfig()
        random.seed(self.config.random_seed)
        np.random.seed(self.config.random_seed)
        
    def solve(self, adjacency_graph: nx.Graph,
              room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[str, Polygon]:
        """Generate rooms that share walls based on adjacency graph"""
                 
        # Add random offset to room positions
        random_offset_x = random.uniform(-1, 1) * self.config.building_width * 0.05
        random_offset_y = random.uniform(-1, 1) * self.config.building_height * 0.05 
        
        # Sort rooms by importance
        room_list = self._prioritize_rooms(list(adjacency_graph.nodes()))
        
        # Create initial building envelope
        building = box(0, 0, self.config.building_width, self.config.building_height)
        
        # Simple grid-based placement that ensures shared walls
        rooms = self._grid_placement(room_list, adjacency_graph, building)
        
        # Ensure all rooms touch their neighbors
        rooms = self._enforce_shared_walls(rooms, adjacency_graph)
        
        # Clean up any gaps
        rooms = self._fill_gaps(rooms)
        
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
    
    def _grid_placement(self, rooms: List[str], graph: nx.Graph, building: Polygon) -> Dict[str, Polygon]:
        """Place rooms in a grid ensuring they touch"""
        
        result = {}
        bounds = building.bounds
        total_width = bounds[2] - bounds[0]
        total_height = bounds[3] - bounds[1]
        
        # Calculate grid dimensions
        n_rooms = len(rooms)
        cols = max(2, int(np.ceil(np.sqrt(n_rooms))))
        rows = max(2, int(np.ceil(n_rooms / cols)))
        
        cell_width = total_width / cols
        cell_height = total_height / rows
        
        for idx, room in enumerate(rooms):
            row = idx // cols
            col = idx % cols
            
            # Calculate cell boundaries
            x1 = col * cell_width + self.config.wall_thickness
            y1 = row * cell_height + self.config.wall_thickness
            x2 = x1 + cell_width - self.config.wall_thickness * 2
            y2 = y1 + cell_height - self.config.wall_thickness * 2
            
            # Ensure minimum size
            min_size = 2.0
            if x2 - x1 < min_size:
                x2 = x1 + min_size
            if y2 - y1 < min_size:
                y2 = y1 + min_size
            
            # Create room polygon
            room_poly = box(x1, y1, x2, y2)
            
            # Adjust shape based on preference
            if self.config.prefer_square_rooms:
                # Make more square
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                size = min(x2 - x1, y2 - y1)
                room_poly = box(center_x - size/2, center_y - size/2, 
                               center_x + size/2, center_y + size/2)
            
            result[room] = room_poly
        
        return result
    
    def _enforce_shared_walls(self, rooms: Dict[str, Polygon], 
                               graph: nx.Graph) -> Dict[str, Polygon]:
        """Ensure adjacent rooms share walls"""
        
        for u, v in graph.edges():
            if u in rooms and v in rooms:
                poly_u = rooms[u]
                poly_v = rooms[v]
                
                # Check if they already share a wall
                intersection = poly_u.intersection(poly_v)
                
                if intersection.is_empty:
                    # They don't touch - move them together
                    rooms = self._merge_rooms(rooms, u, v)
                elif intersection.geom_type == 'Polygon' and intersection.area > 0:
                    # They overlap - trim them
                    rooms = self._trim_overlap(rooms, u, v)
        
        return rooms
    
    def _merge_rooms(self, rooms: Dict[str, Polygon], room_a: str, room_b: str) -> Dict[str, Polygon]:
        """Move rooms to share a wall"""
        
        poly_a = rooms[room_a]
        poly_b = rooms[room_b]
        
        # Get centroids
        ca = poly_a.centroid
        cb = poly_b.centroid
        
        # Calculate direction to move
        dx = cb.x - ca.x
        dy = cb.y - ca.y
        distance = np.sqrt(dx*dx + dy*dy)
        
        if distance > 0:
            dx /= distance
            dy /= distance
            
            # Move towards each other by half the distance
            move_dist = distance / 2
            
            # Shift rooms
            new_a = self._shift_polygon(poly_a, dx * move_dist, dy * move_dist)
            new_b = self._shift_polygon(poly_b, -dx * move_dist, -dy * move_dist)
            
            rooms[room_a] = new_a
            rooms[room_b] = new_b
            
            # Create shared wall by making them exactly touch
            rooms = self._create_shared_wall(rooms, room_a, room_b)
        
        return rooms
    
    def _shift_polygon(self, polygon: Polygon, dx: float, dy: float) -> Polygon:
        """Shift polygon by dx, dy"""
        coords = [(x + dx, y + dy) for x, y in polygon.exterior.coords]
        return Polygon(coords)
    
    def _create_shared_wall(self, rooms: Dict[str, Polygon], room_a: str, room_b: str) -> Dict[str, Polygon]:
        """Create a shared wall between two rooms"""
        
        poly_a = rooms[room_a]
        poly_b = rooms[room_b]
        
        # Find the closest points between the two polygons
        closest_points = self._find_closest_points(poly_a, poly_b)
        
        if closest_points:
            p1, p2 = closest_points
            
            # Create a shared wall by adjusting both polygons
            # Extend both to meet at the midpoint
            mid_x = (p1[0] + p2[0]) / 2
            mid_y = (p1[1] + p2[1]) / 2
            
            # Adjust room_a to include up to the wall
            rooms[room_a] = self._extend_to_point(poly_a, (mid_x, mid_y))
            
            # Adjust room_b to include up to the wall
            rooms[room_b] = self._extend_to_point(poly_b, (mid_x, mid_y))
        
        return rooms
    
    def _find_closest_points(self, poly_a: Polygon, poly_b: Polygon) -> Optional[Tuple[Tuple, Tuple]]:
        """Find closest points between two polygons"""
        min_dist = float('inf')
        closest_pair = None
        
        coords_a = list(poly_a.exterior.coords)
        coords_b = list(poly_b.exterior.coords)
        
        for p1 in coords_a:
            for p2 in coords_b:
                dist = np.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)
                if dist < min_dist:
                    min_dist = dist
                    closest_pair = (p1, p2)
        
        return closest_pair
    
    def _extend_to_point(self, polygon: Polygon, point: Tuple[float, float]) -> Polygon:
        """Extend polygon to include a point"""
        coords = list(polygon.exterior.coords)
        
        # Add the point to coordinates
        all_coords = coords + [point]
        
        # Create convex hull to include the point
        from scipy.spatial import ConvexHull
        
        points_array = np.array(all_coords)
        if len(points_array) >= 3:
            try:
                hull = ConvexHull(points_array)
                hull_coords = [tuple(points_array[i]) for i in hull.vertices]
                return Polygon(hull_coords)
            except:
                pass
        
        return polygon
    
    def _trim_overlap(self, rooms: Dict[str, Polygon], room_a: str, room_b: str) -> Dict[str, Polygon]:
        """Trim overlapping areas between rooms"""
        
        poly_a = rooms[room_a]
        poly_b = rooms[room_b]
        
        # Remove overlap from both
        overlap = poly_a.intersection(poly_b)
        
        if not overlap.is_empty:
            # Simple fix: difference operation
            rooms[room_a] = poly_a.difference(overlap)
            rooms[room_b] = poly_b.difference(overlap)
        
        return rooms
    
    def _fill_gaps(self, rooms: Dict[str, Polygon]) -> Dict[str, Polygon]:
        """Fill gaps between rooms"""
        
        all_rooms = unary_union(list(rooms.values()))
        building = box(0, 0, self.config.building_width, self.config.building_height)
        
        # Find gaps
        gaps = building.difference(all_rooms)
        
        if not gaps.is_empty:
            # Distribute gaps to adjacent rooms
            if gaps.geom_type == 'Polygon':
                gaps = [gaps]
            elif gaps.geom_type == 'MultiPolygon':
                gaps = list(gaps.geoms)
            
            for gap in gaps:
                # Find room that should get this gap
                best_room = self._find_room_for_gap(gap, rooms)
                if best_room:
                    rooms[best_room] = rooms[best_room].union(gap)
        
        return rooms
    
    def _find_room_for_gap(self, gap: Polygon, rooms: Dict[str, Polygon]) -> Optional[str]:
        """Find which room a gap should belong to"""
        max_overlap = 0
        best_room = None
        
        for name, room in rooms.items():
            # Check if gap touches this room
            if room.distance(gap) < 0.1:
                # Measure shared boundary
                shared = room.intersection(gap.buffer(0.1))
                if hasattr(shared, 'length') and shared.length > max_overlap:
                    max_overlap = shared.length
                    best_room = name
        
        return best_room
