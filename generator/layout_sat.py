"""
Real floor plan generator with shared walls, void spaces, and livable layouts
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Polygon, box, MultiPolygon
from shapely.ops import unary_union
import networkx as nx
from dataclasses import dataclass
import math
import random

@dataclass
class LayoutConfig:
    building_width: float = 12.0
    building_height: float = 12.0
    wall_thickness: float = 0.15
    hallway_width: float = 1.2
    random_seed: int = 42

class RoomLayoutSolverSAT:
    def __init__(self, config: LayoutConfig = None):
        self.config = config or LayoutConfig()
        random.seed(self.config.random_seed)
        np.random.seed(self.config.random_seed)
        
    def solve(self, adjacency_graph: nx.Graph,
              room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[str, Polygon]:
        """Generate real floor plan with shared walls"""
        
        rooms = list(adjacency_graph.nodes())
        
        # Choose layout strategy based on room count and seed
        strategy = self.config.random_seed % 5
        
        if strategy == 0:
            return self._layout_central_hallway(rooms, adjacency_graph)
        elif strategy == 1:
            return self._layout_l_shaped(rooms, adjacency_graph)
        elif strategy == 2:
            return self._layout_courtyard(rooms, adjacency_graph)
        elif strategy == 3:
            return self._layout_split_level(rooms, adjacency_graph)
        else:
            return self._layout_organic_clusters(rooms, adjacency_graph)
    
    def _layout_central_hallway(self, rooms: List[str], graph: nx.Graph) -> Dict[str, Polygon]:
        """Central hallway with rooms on both sides (real apartment layout)"""
        result = {}
        
        hallway_width = self.config.hallway_width
        hallway_length = self.config.building_width - 2
        
        # Place hallway in center
        hallway_x = 1
        hallway_y = (self.config.building_height - hallway_length) / 2
        hallway = box(hallway_x, hallway_y, 
                     hallway_x + hallway_width, hallway_y + hallway_length)
        
        # Sort rooms: living/kitchen on one side, bedrooms on other
        left_rooms = []
        right_rooms = []
        
        for room in rooms:
            if 'living' in room.lower() or 'kitchen' in room.lower() or 'dining' in room.lower():
                left_rooms.append(room)
            else:
                right_rooms.append(room)
        
        # Distribute rooms along hallway
        left_height = hallway_length / max(1, len(left_rooms))
        right_height = hallway_length / max(1, len(right_rooms))
        
        # Left side rooms
        for i, room in enumerate(left_rooms):
            y_start = hallway_y + i * left_height + 0.5
            y_end = y_start + left_height - 1
            
            room_width = random.uniform(3.0, 5.0)
            room_x = hallway_x - room_width
            room_poly = box(room_x, y_start, hallway_x, y_end)
            result[room] = room_poly
        
        # Right side rooms
        for i, room in enumerate(right_rooms):
            y_start = hallway_y + i * right_height + 0.5
            y_end = y_start + right_height - 1
            
            room_width = random.uniform(3.0, 5.0)
            room_x = hallway_x + hallway_width
            room_poly = box(room_x, y_start, room_x + room_width, y_end)
            result[room] = room_poly
        
        # Add hallway as a room
        result['hallway'] = hallway
        
        return result
    
    def _layout_l_shaped(self, rooms: List[str], graph: nx.Graph) -> Dict[str, Polygon]:
        """L-shaped building with corner common area"""
        result = {}
        
        # Create L-shaped footprint
        wing1_width = self.config.building_width * 0.6
        wing1_height = self.config.building_height * 0.7
        wing2_width = self.config.building_width * 0.5
        wing2_height = self.config.building_height * 0.5
        
        # Wing 1 (vertical)
        wing1 = box(0, 0, wing1_width, wing1_height)
        
        # Wing 2 (horizontal)
        wing2 = box(wing1_width - wing2_width, wing1_height - wing2_height,
                   self.config.building_width, self.config.building_height)
        
        # Corner common area (living room)
        corner = wing1.intersection(wing2)
        
        # Place main living room in corner
        main_room = self._find_main_room(rooms)
        if main_room:
            result[main_room] = corner
        
        # Distribute other rooms
        other_rooms = [r for r in rooms if r != main_room]
        
        # Wing 1 rooms (along vertical)
        wing1_rooms = other_rooms[:len(other_rooms)//2]
        wing1_height_available = wing1_height - corner.bounds[3] + corner.bounds[1]
        room_height = wing1_height_available / max(1, len(wing1_rooms))
        
        for i, room in enumerate(wing1_rooms):
            y_start = corner.bounds[3] + i * room_height
            y_end = y_start + room_height
            room_poly = box(0, y_start, wing1_width, y_end)
            result[room] = room_poly
        
        # Wing 2 rooms (along horizontal)
        wing2_rooms = other_rooms[len(other_rooms)//2:]
        wing2_width_available = wing2_width - corner.bounds[2] + corner.bounds[0]
        room_width = wing2_width_available / max(1, len(wing2_rooms))
        
        for i, room in enumerate(wing2_rooms):
            x_start = corner.bounds[2] + i * room_width
            x_end = x_start + room_width
            room_poly = box(x_start, wing2.bounds[1], x_end, wing2.bounds[3])
            result[room] = room_poly
        
        return result
    
    def _layout_courtyard(self, rooms: List[str], graph: nx.Graph) -> Dict[str, Polygon]:
        """Courtyard style with rooms around central void"""
        result = {}
        
        # Create outer building
        outer = box(0, 0, self.config.building_width, self.config.building_height)
        
        # Create central courtyard (void)
        courtyard_size = min(self.config.building_width, self.config.building_height) * 0.4
        courtyard_x = (self.config.building_width - courtyard_size) / 2
        courtyard_y = (self.config.building_height - courtyard_size) / 2
        courtyard = box(courtyard_x, courtyard_y, 
                       courtyard_x + courtyard_size, courtyard_y + courtyard_size)
        
        # Building ring
        building_ring = outer.difference(courtyard)
        
        # Divide ring into rooms
        n_rooms = len(rooms)
        
        # Calculate ring perimeter
        perimeter = 2 * (self.config.building_width + self.config.building_height)
        courtyard_perimeter = 4 * courtyard_size
        total_wall_length = perimeter + courtyard_perimeter
        
        # Distribute rooms along ring
        room_length = total_wall_length / n_rooms
        
        current_pos = 0
        for room in rooms:
            # Determine which wall this room goes on
            if current_pos < self.config.building_width:
                # Bottom wall
                x1 = current_pos
                x2 = min(current_pos + room_length, self.config.building_width)
                room_poly = box(x1, 0, x2, self.config.building_height * 0.4)
            elif current_pos < self.config.building_width + self.config.building_height:
                # Right wall
                pos = current_pos - self.config.building_width
                y1 = pos
                y2 = min(pos + room_length, self.config.building_height)
                room_poly = box(self.config.building_width * 0.6, y1, 
                               self.config.building_width, y2)
            elif current_pos < self.config.building_width * 2 + self.config.building_height:
                # Top wall
                pos = current_pos - self.config.building_width - self.config.building_height
                x2 = self.config.building_width - pos
                x1 = max(0, x2 - room_length)
                room_poly = box(x1, self.config.building_height * 0.6, 
                               x2, self.config.building_height)
            else:
                # Left wall
                pos = current_pos - self.config.building_width * 2 - self.config.building_height
                y2 = self.config.building_height - pos
                y1 = max(0, y2 - room_length)
                room_poly = box(0, y1, self.config.building_width * 0.4, y2)
            
            result[room] = room_poly
            current_pos += room_length
        
        # Add courtyard as void (represented as a room)
        result['courtyard'] = courtyard
        
        return result
    
    def _layout_split_level(self, rooms: List[str], graph: nx.Graph) -> Dict[str, Polygon]:
        """Split level with public/private separation"""
        result = {}
        
        # Split building into public and private zones
        split_ratio = 0.4 + random.uniform(0, 0.2)
        split_x = self.config.building_width * split_ratio
        
        # Public zone (living, kitchen, dining)
        public_zone = box(0, 0, split_x, self.config.building_height)
        # Private zone (bedrooms, bathrooms)
        private_zone = box(split_x, 0, self.config.building_width, self.config.building_height)
        
        # Separate rooms
        public_rooms = [r for r in rooms if 'living' in r.lower() or 
                       'kitchen' in r.lower() or 'dining' in r.lower()]
        private_rooms = [r for r in rooms if r not in public_rooms]
        
        # Arrange public rooms in open plan
        if public_rooms:
            main_public = public_rooms[0]
            result[main_public] = public_zone
            
            # Additional public rooms as smaller spaces
            for i, room in enumerate(public_rooms[1:]):
                x = split_x - (i + 1) * 2
                room_poly = box(x, 1, split_x - 0.5, self.config.building_height - 1)
                result[room] = room_poly
        
        # Arrange private rooms with hallway
        hallway_width = self.config.hallway_width
        hallway = box(private_zone.bounds[0] + 1, private_zone.bounds[1] + 1,
                     private_zone.bounds[2] - 1, private_zone.bounds[3] - 1)
        
        # Split private zone into rooms
        n_private = len(private_rooms)
        if n_private > 0:
            room_height = (self.config.building_height - 2) / n_private
            
            for i, room in enumerate(private_rooms):
                y1 = 1 + i * room_height
                y2 = y1 + room_height - 0.5
                room_poly = box(private_zone.bounds[0] + 1.5, y1,
                               private_zone.bounds[2] - 1.5, y2)
                result[room] = room_poly
        
        return result
    
    def _layout_organic_clusters(self, rooms: List[str], graph: nx.Graph) -> Dict[str, Polygon]:
        """Organic clusters with shared walls"""
        result = {}
        
        # Create clusters of related rooms
        clusters = self._cluster_rooms(rooms, graph)
        
        # Place clusters in building
        cluster_positions = []
        used_x = 0
        
        for cluster_name, cluster_rooms in clusters.items():
            # Calculate cluster size
            total_area = sum(self._estimate_room_area(r) for r in cluster_rooms)
            cluster_width = math.sqrt(total_area) * 1.2
            cluster_height = total_area / cluster_width
            
            # Position cluster
            if used_x + cluster_width < self.config.building_width:
                x1 = used_x + 0.5
                used_x += cluster_width
            else:
                x1 = random.uniform(0.5, self.config.building_width - cluster_width - 0.5)
            
            y1 = random.uniform(0.5, self.config.building_height - cluster_height - 0.5)
            cluster_bounds = box(x1, y1, x1 + cluster_width, y1 + cluster_height)
            
            # Subdivide cluster into rooms
            cluster_rooms_layout = self._subdivide_cluster(cluster_bounds, cluster_rooms)
            result.update(cluster_rooms_layout)
        
        return result
    
    def _cluster_rooms(self, rooms: List[str], graph: nx.Graph) -> Dict[str, List[str]]:
        """Group rooms into functional clusters"""
        clusters = {}
        
        # Living cluster (living, dining, kitchen)
        living_cluster = []
        for room in rooms:
            if any(x in room.lower() for x in ['living', 'dining', 'kitchen']):
                living_cluster.append(room)
        if living_cluster:
            clusters['living'] = living_cluster
        
        # Bedroom cluster
        bedroom_cluster = []
        for room in rooms:
            if any(x in room.lower() for x in ['bedroom', 'master']):
                bedroom_cluster.append(room)
        if bedroom_cluster:
            clusters['bedroom'] = bedroom_cluster
        
        # Service cluster (bathroom, laundry, storage)
        service_cluster = []
        for room in rooms:
            if any(x in room.lower() for x in ['bath', 'laundry', 'storage', 'closet']):
                service_cluster.append(room)
        if service_cluster:
            clusters['service'] = service_cluster
        
        # Remaining rooms
        all_assigned = set()
        for c in clusters.values():
            all_assigned.update(c)
        remaining = [r for r in rooms if r not in all_assigned]
        if remaining:
            clusters['other'] = remaining
        
        return clusters
    
    def _subdivide_cluster(self, bounds: Polygon, rooms: List[str]) -> Dict[str, Polygon]:
        """Subdivide a cluster into individual rooms"""
        result = {}
        n_rooms = len(rooms)
        
        if n_rooms == 1:
            result[rooms[0]] = bounds
            return result
        
        # Recursive subdivision
        bounds_coords = bounds.bounds
        width = bounds_coords[2] - bounds_coords[0]
        height = bounds_coords[3] - bounds_coords[1]
        
        # Split horizontally or vertically
        split_vertical = width > height
        
        if split_vertical:
            split_ratio = random.uniform(0.3, 0.7)
            split_x = bounds_coords[0] + width * split_ratio
            
            left = box(bounds_coords[0], bounds_coords[1], split_x, bounds_coords[3])
            right = box(split_x, bounds_coords[1], bounds_coords[2], bounds_coords[3])
            
            split_point = max(1, min(n_rooms - 1, int(n_rooms * split_ratio)))
            result.update(self._subdivide_cluster(left, rooms[:split_point]))
            result.update(self._subdivide_cluster(right, rooms[split_point:]))
        else:
            split_ratio = random.uniform(0.3, 0.7)
            split_y = bounds_coords[1] + height * split_ratio
            
            bottom = box(bounds_coords[0], bounds_coords[1], bounds_coords[2], split_y)
            top = box(bounds_coords[0], split_y, bounds_coords[2], bounds_coords[3])
            
            split_point = max(1, min(n_rooms - 1, int(n_rooms * split_ratio)))
            result.update(self._subdivide_cluster(bottom, rooms[:split_point]))
            result.update(self._subdivide_cluster(top, rooms[split_point:]))
        
        return result
    
    def _find_main_room(self, rooms: List[str]) -> Optional[str]:
        """Find the main living room"""
        for room in rooms:
            if 'living' in room.lower():
                return room
        return rooms[0] if rooms else None
    
    def _estimate_room_area(self, room: str) -> float:
        """Estimate appropriate area for room type"""
        room_lower = room.lower()
        
        if 'living' in room_lower:
            return random.uniform(18, 28)
        elif 'kitchen' in room_lower:
            return random.uniform(8, 14)
        elif 'dining' in room_lower:
            return random.uniform(10, 16)
        elif 'master' in room_lower:
            return random.uniform(16, 24)
        elif 'bedroom' in room_lower:
            return random.uniform(10, 16)
        elif 'bathroom' in room_lower:
            return random.uniform(4, 8)
        elif 'study' in room_lower or 'office' in room_lower:
            return random.uniform(8, 12)
        else:
            return random.uniform(10, 15)
