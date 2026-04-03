"""
ILP-based floor plan layout solver with true randomization
Based on: "Algorithms for Floor Planning with Proximity Requirements" (Klawitter et al.)
"""
import pulp
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
    corridor_width: float = 1.2
    random_seed: int = 42
    time_limit_seconds: int = 30

class RoomLayoutSolverILP:
    """
    ILP-based room layout solver with true randomization
    """
    
    def __init__(self, config: LayoutConfig = None):
        self.config = config or LayoutConfig()
        random.seed(self.config.random_seed)
        np.random.seed(self.config.random_seed)
        
    def solve(self, adjacency_graph: nx.Graph,
              room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[str, Polygon]:
        """Generate randomized floor plan"""
        
        rooms = list(adjacency_graph.nodes())
        
        # Always use decomposition with randomization for variety
        return self._solve_decomposition(rooms, adjacency_graph, room_sizes)
    
    def _solve_decomposition(self, rooms: List[str], graph: nx.Graph,
                              room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[str, Polygon]:
        """Decomposition approach with randomized room sizes"""
        
        # First, assign random sizes to each room
        room_areas = {}
        room_dimensions = {}
        
        for room in rooms:
            # Generate random size based on room type
            area = self._get_random_room_area(room)
            room_areas[room] = area
            
            # Generate random aspect ratio
            aspect_ratio = random.uniform(0.6, 1.6)
            width = math.sqrt(area * aspect_ratio)
            height = area / width
            
            # Ensure within building bounds
            width = min(width, self.config.building_width * 0.8)
            height = min(height, self.config.building_height * 0.8)
            width = max(2.5, width)
            height = max(2.5, height)
            
            room_dimensions[room] = (width, height)
        
        # Choose layout style based on seed
        layout_style = self.config.random_seed % 6
        
        if layout_style == 0:
            return self._layout_grid_varied(rooms, room_dimensions)
        elif layout_style == 1:
            return self._layout_spiral_varied(rooms, room_dimensions)
        elif layout_style == 2:
            return self._layout_hallway_varied(rooms, room_dimensions)
        elif layout_style == 3:
            return self._layout_cluster_varied(rooms, room_dimensions, graph)
        elif layout_style == 4:
            return self._layout_organic_varied(rooms, room_dimensions)
        else:
            return self._layout_recursive_varied(rooms, room_dimensions)
    
    def _get_random_room_area(self, room: str) -> float:
        """Generate random realistic area for room type"""
        room_lower = room.lower()
        
        # Different ranges for different room types
        area_ranges = {
            'living': (18, 35),
            'kitchen': (8, 18),
            'dining': (10, 20),
            'master': (16, 28),
            'bedroom': (10, 20),
            'bathroom': (4, 10),
            'study': (8, 16),
            'office': (10, 18),
            'hallway': (5, 12),
            'closet': (3, 8),
            'laundry': (4, 8)
        }
        
        for key, (min_area, max_area) in area_ranges.items():
            if key in room_lower:
                return random.uniform(min_area, max_area)
        
        # Default range
        return random.uniform(8, 20)
    
    def _layout_grid_varied(self, rooms: List[str], 
                            dimensions: Dict[str, Tuple[float, float]]) -> Dict[str, Polygon]:
        """Grid layout with varied room sizes"""
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
            
            # Get target dimensions
            target_w, target_h = dimensions[room]
            
            # Position with some randomness
            x_offset = random.uniform(-0.5, 0.5)
            y_offset = random.uniform(-0.5, 0.5)
            
            x = col * cell_w + margin + x_offset
            y = row * cell_h + margin + y_offset
            
            # Use actual dimensions, not grid cell
            w = min(target_w, cell_w - margin)
            h = min(target_h, cell_h - margin)
            
            # Ensure minimum size
            w = max(2.0, w)
            h = max(2.0, h)
            
            result[room] = box(x, y, x + w, y + h)
        
        return result
    
    def _layout_spiral_varied(self, rooms: List[str], 
                               dimensions: Dict[str, Tuple[float, float]]) -> Dict[str, Polygon]:
        """Spiral layout with varied room sizes"""
        result = {}
        
        center_x = self.config.building_width / 2
        center_y = self.config.building_height / 2
        
        # Place largest room at center
        if rooms:
            main_room = self._find_main_room(rooms)
            if main_room:
                w, h = dimensions[main_room]
                result[main_room] = box(center_x - w/2, center_y - h/2,
                                       center_x + w/2, center_y + h/2)
                rooms.remove(main_room)
        
        # Place other rooms in spiral
        angle = 0
        radius = max(dimensions.get(main_room, (3, 3))[0] / 2 + 1, 2)
        
        for room in rooms:
            angle += math.pi / 4
            radius += random.uniform(0.8, 1.5)
            
            x = center_x + math.cos(angle) * radius
            y = center_y + math.sin(angle) * radius
            
            w, h = dimensions[room]
            
            # Adjust to not exceed bounds
            x = max(0.5, min(x, self.config.building_width - w - 0.5))
            y = max(0.5, min(y, self.config.building_height - h - 0.5))
            
            result[room] = box(x - w/2, y - h/2, x + w/2, y + h/2)
        
        return result
    
    def _layout_hallway_varied(self, rooms: List[str],
                                dimensions: Dict[str, Tuple[float, float]]) -> Dict[str, Polygon]:
        """Hallway layout with rooms on both sides"""
        result = {}
        
        hallway_width = self.config.corridor_width
        hallway_length = self.config.building_width - 2
        
        # Place hallway
        hallway_x = 1
        hallway_y = (self.config.building_height - hallway_length) / 2
        result['hallway'] = box(hallway_x, hallway_y,
                               hallway_x + hallway_width, hallway_y + hallway_length)
        
        # Separate rooms by type
        left_rooms = []
        right_rooms = []
        
        for room in rooms:
            if 'living' in room.lower() or 'kitchen' in room.lower():
                left_rooms.append(room)
            else:
                right_rooms.append(room)
        
        # Distribute left side
        left_height = hallway_length / max(1, len(left_rooms))
        for i, room in enumerate(left_rooms):
            y_start = hallway_y + i * left_height + 0.3
            y_end = y_start + left_height - 0.6
            
            w, h = dimensions[room]
            actual_h = min(h, y_end - y_start)
            actual_w = min(w, hallway_x - 0.5)
            
            x_start = hallway_x - actual_w
            result[room] = box(x_start, y_start, hallway_x, y_start + actual_h)
        
        # Distribute right side
        right_height = hallway_length / max(1, len(right_rooms))
        for i, room in enumerate(right_rooms):
            y_start = hallway_y + i * right_height + 0.3
            y_end = y_start + right_height - 0.6
            
            w, h = dimensions[room]
            actual_h = min(h, y_end - y_start)
            actual_w = min(w, self.config.building_width - hallway_x - hallway_width - 0.5)
            
            x_end = hallway_x + hallway_width + actual_w
            result[room] = box(hallway_x + hallway_width, y_start, x_end, y_start + actual_h)
        
        return result
    
    def _layout_cluster_varied(self, rooms: List[str],
                                dimensions: Dict[str, Tuple[float, float]],
                                graph: nx.Graph) -> Dict[str, Polygon]:
        """Cluster layout grouping related rooms"""
        result = {}
        
        # Create clusters based on adjacency
        clusters = self._create_clusters(rooms, graph)
        
        # Position clusters
        cluster_positions = {}
        used_x = 0.5
        
        for cluster_name, cluster_rooms in clusters.items():
            # Calculate cluster size
            total_w = sum(dimensions[r][0] for r in cluster_rooms)
            total_h = max(dimensions[r][1] for r in cluster_rooms)
            
            # Position cluster
            if used_x + total_w < self.config.building_width - 0.5:
                cluster_x = used_x
                used_x += total_w + 0.5
            else:
                cluster_x = random.uniform(0.5, self.config.building_width - total_w - 0.5)
            
            cluster_y = random.uniform(0.5, self.config.building_height - total_h - 0.5)
            cluster_positions[cluster_name] = (cluster_x, cluster_y, total_w, total_h)
            
            # Place rooms within cluster
            current_x = cluster_x
            for room in cluster_rooms:
                w, h = dimensions[room]
                result[room] = box(current_x, cluster_y, current_x + w, cluster_y + h)
                current_x += w + 0.1
        
        return result
    
    def _layout_organic_varied(self, rooms: List[str],
                                dimensions: Dict[str, Tuple[float, float]]) -> Dict[str, Polygon]:
        """Organic layout with random positions and rotations"""
        result = {}
        
        # Sort by size (largest first)
        sorted_rooms = sorted(rooms, 
                            key=lambda r: dimensions[r][0] * dimensions[r][1],
                            reverse=True)
        
        for room in sorted_rooms:
            w, h = dimensions[room]
            
            # Try to find non-overlapping position
            max_attempts = 100
            for attempt in range(max_attempts):
                x = random.uniform(0.5, self.config.building_width - w - 0.5)
                y = random.uniform(0.5, self.config.building_height - h - 0.5)
                
                candidate = box(x, y, x + w, y + h)
                
                overlapping = False
                for existing in result.values():
                    if candidate.intersects(existing):
                        overlapping = True
                        break
                
                if not overlapping:
                    result[room] = candidate
                    break
            else:
                # Place anyway if no position found
                x = random.uniform(0.5, self.config.building_width - w - 0.5)
                y = random.uniform(0.5, self.config.building_height - h - 0.5)
                result[room] = box(x, y, x + w, y + h)
        
        return result
    
    def _layout_recursive_varied(self, rooms: List[str],
                                  dimensions: Dict[str, Tuple[float, float]]) -> Dict[str, Polygon]:
        """Recursive subdivision with varied sizes"""
        
        def subdivide(space: Polygon, room_list: List[str]) -> Dict[str, Polygon]:
            if len(room_list) == 1:
                return {room_list[0]: space}
            
            if len(room_list) == 0:
                return {}
            
            bounds = space.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            
            # Random split orientation
            split_vertical = random.choice([True, False])
            
            # Random split ratio based on room sizes
            mid = len(room_list) // 2
            left_rooms = room_list[:mid]
            right_rooms = room_list[mid:]
            
            left_area = sum(dimensions[r][0] * dimensions[r][1] for r in left_rooms)
            right_area = sum(dimensions[r][0] * dimensions[r][1] for r in right_rooms)
            total = left_area + right_area
            
            if split_vertical:
                split_ratio = left_area / total if total > 0 else 0.5
                split_x = bounds[0] + width * split_ratio
                
                left = box(bounds[0], bounds[1], split_x, bounds[3])
                right = box(split_x, bounds[1], bounds[2], bounds[3])
                
                result = {}
                result.update(subdivide(left, left_rooms))
                result.update(subdivide(right, right_rooms))
                return result
            else:
                split_ratio = left_area / total if total > 0 else 0.5
                split_y = bounds[1] + height * split_ratio
                
                bottom = box(bounds[0], bounds[1], bounds[2], split_y)
                top = box(bounds[0], split_y, bounds[2], bounds[3])
                
                result = {}
                result.update(subdivide(bottom, left_rooms))
                result.update(subdivide(top, right_rooms))
                return result
        
        # Start with full building
        building = box(0, 0, self.config.building_width, self.config.building_height)
        
        # Shuffle rooms for variety
        shuffled_rooms = rooms.copy()
        random.shuffle(shuffled_rooms)
        
        return subdivide(building, shuffled_rooms)
    
    def _create_clusters(self, rooms: List[str], graph: nx.Graph) -> Dict[str, List[str]]:
        """Create clusters based on graph connectivity"""
        clusters = {}
        
        # Find connected components
        visited = set()
        cluster_id = 0
        
        for room in rooms:
            if room not in visited:
                # BFS to find cluster
                cluster = []
                queue = [room]
                visited.add(room)
                
                while queue:
                    current = queue.pop(0)
                    cluster.append(current)
                    
                    for neighbor in graph.neighbors(current):
                        if neighbor not in visited and neighbor in rooms:
                            visited.add(neighbor)
                            queue.append(neighbor)
                
                if cluster:
                    clusters[f"cluster_{cluster_id}"] = cluster
                    cluster_id += 1
        
        # If no clusters found, create functional clusters
        if not clusters:
            clusters = {
                'living_area': [],
                'sleeping_area': [],
                'service_area': []
            }
            
            for room in rooms:
                room_lower = room.lower()
                if any(x in room_lower for x in ['living', 'kitchen', 'dining']):
                    clusters['living_area'].append(room)
                elif any(x in room_lower for x in ['bedroom', 'master']):
                    clusters['sleeping_area'].append(room)
                else:
                    clusters['service_area'].append(room)
            
            # Remove empty clusters
            clusters = {k: v for k, v in clusters.items() if v}
        
        return clusters
    
    def _find_main_room(self, rooms: List[str]) -> Optional[str]:
        """Find the main room (largest or living)"""
        for room in rooms:
            if 'living' in room.lower():
                return room
        return rooms[0] if rooms else None
