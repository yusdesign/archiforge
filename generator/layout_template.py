"""
Template-based floor plan generator - Guarantees readable layouts
"""
import random
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Polygon, box
import networkx as nx
from dataclasses import dataclass

@dataclass
class LayoutConfig:
    building_width: float = 12.0
    building_height: float = 12.0
    wall_thickness: float = 0.15
    corridor_width: float = 1.2
    random_seed: int = 42

class RoomLayoutSolverTemplate:
    """
    Template-based layout generator - produces readable floor plans
    """
    
    def __init__(self, config: LayoutConfig = None):
        self.config = config or LayoutConfig()
        random.seed(self.config.random_seed)
        
    def solve(self, adjacency_graph: nx.Graph,
              room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[str, Polygon]:
        
        rooms = list(adjacency_graph.nodes())
        n_rooms = len(rooms)
        
        # Choose template based on room count and seed
        template = self.config.random_seed % 5
        
        if template == 0 and n_rooms <= 6:
            return self._template_central_hallway(rooms, adjacency_graph, room_sizes)
        elif template == 1 and n_rooms <= 5:
            return self._template_l_shaped(rooms, adjacency_graph, room_sizes)
        elif template == 2 and n_rooms <= 4:
            return self._template_split_level(rooms, adjacency_graph, room_sizes)
        elif template == 3 and n_rooms <= 8:
            return self._template_double_corridor(rooms, adjacency_graph, room_sizes)
        else:
            return self._template_shotgun(rooms, adjacency_graph, room_sizes)
    
    def _template_central_hallway(self, rooms: List[str], graph: nx.Graph,
                                   room_sizes: Dict) -> Dict[str, Polygon]:
        """
        Central hallway with rooms on both sides
        Most common apartment layout - very readable
        """
        result = {}
        wall = self.config.wall_thickness
        
        # Hallway dimensions
        hallway_width = self.config.corridor_width
        hallway_height = self.config.building_height - 2 * wall
        hallway_x = (self.config.building_width - hallway_width) / 2
        
        # Add hallway
        result['hallway'] = box(hallway_x, wall, 
                               hallway_x + hallway_width, wall + hallway_height)
        
        # Separate rooms by type
        living_rooms = []
        bedroom_rooms = []
        other_rooms = []
        
        for room in rooms:
            r = room.lower()
            if 'living' in r or 'kitchen' in r or 'dining' in r:
                living_rooms.append(room)
            elif 'bedroom' in r or 'master' in r:
                bedroom_rooms.append(room)
            else:
                other_rooms.append(room)
        
        # Calculate available wall space
        left_wall_start = wall
        left_wall_end = hallway_x - wall
        right_wall_start = hallway_x + hallway_width + wall
        right_wall_end = self.config.building_width - wall
        
        left_depth = left_wall_end - left_wall_start
        right_depth = right_wall_end - right_wall_start
        
        # Place living rooms on left (deeper side typically)
        n_left = len(living_rooms) + len(other_rooms) // 2
        n_right = len(bedroom_rooms) + len(other_rooms) - len(other_rooms) // 2
        
        left_height = hallway_height / max(1, n_left)
        right_height = hallway_height / max(1, n_right)
        
        # Left side rooms
        y = wall
        for room in living_rooms + other_rooms[:n_left]:
            area = self._get_room_area(room, room_sizes)
            # Adjust depth based on area
            depth = min(left_depth, max(2.5, area / left_height))
            result[room] = box(left_wall_end - depth, y, left_wall_end, y + left_height - wall)
            y += left_height
        
        # Right side rooms
        y = wall
        for room in bedroom_rooms + other_rooms[n_left:]:
            area = self._get_room_area(room, room_sizes)
            depth = min(right_depth, max(2.5, area / right_height))
            result[room] = box(right_wall_start, y, right_wall_start + depth, y + right_height - wall)
            y += right_height
        
        return result
    
    def _template_shotgun(self, rooms: List[str], graph: nx.Graph,
                          room_sizes: Dict) -> Dict[str, Polygon]:
        """
        Shotgun layout - rooms in a line (typical for row houses)
        Very readable, no gaps
        """
        result = {}
        wall = self.config.wall_thickness
        
        n = len(rooms)
        room_height = (self.config.building_height - 2 * wall) / n
        
        # Sort rooms by typical position (living room first, bedrooms last)
        def room_priority(r):
            r_lower = r.lower()
            if 'living' in r_lower or 'kitchen' in r_lower:
                return 0
            elif 'dining' in r_lower:
                return 1
            elif 'bedroom' in r_lower or 'master' in r_lower:
                return 2
            else:
                return 3
        
        sorted_rooms = sorted(rooms, key=room_priority)
        
        y = wall
        for i, room in enumerate(sorted_rooms):
            area = self._get_room_area(room, room_sizes)
            # Adjust height based on area
            height = max(2.5, min(room_height, area / (self.config.building_width - 2 * wall)))
            result[room] = box(wall, y, self.config.building_width - wall, y + height)
            y += height + wall
        
        return result
    
    def _template_l_shaped(self, rooms: List[str], graph: nx.Graph,
                           room_sizes: Dict) -> Dict[str, Polygon]:
        """
        L-shaped layout - corner building style
        """
        result = {}
        wall = self.config.wall_thickness
        
        # Split building into two wings
        split_x = self.config.building_width * 0.6
        split_y = self.config.building_height * 0.6
        
        # Corner for living room
        living_room = None
        for room in rooms:
            if 'living' in room.lower():
                living_room = room
                break
        
        if living_room:
            result[living_room] = box(split_x - 3, split_y - 3, split_x + 2, split_y + 2)
            rooms.remove(living_room)
        
        # Horizontal wing
        n_horiz = len(rooms) // 2
        horiz_rooms = rooms[:n_horiz]
        horiz_width = (self.config.building_width - 2 * wall) / max(1, len(horiz_rooms))
        
        x = wall
        for room in horiz_rooms:
            area = self._get_room_area(room, room_sizes)
            width = max(2.5, min(horiz_width, area / (split_y - wall)))
            result[room] = box(x, wall, x + width, split_y - wall)
            x += width + wall
        
        # Vertical wing
        vert_rooms = rooms[n_horiz:]
        vert_height = (self.config.building_height - split_y - wall) / max(1, len(vert_rooms))
        
        y = split_y
        for room in vert_rooms:
            area = self._get_room_area(room, room_sizes)
            height = max(2.5, min(vert_height, area / (split_x - wall)))
            result[room] = box(wall, y, split_x - wall, y + height)
            y += height + wall
        
        return result
    
    def _template_split_level(self, rooms: List[str], graph: nx.Graph,
                               room_sizes: Dict) -> Dict[str, Polygon]:
        """
        Split level - public vs private separation
        """
        result = {}
        wall = self.config.wall_thickness
        
        # Split into two zones
        split = self.config.building_height * 0.4
        
        # Public zone (bottom) - living, kitchen, dining
        public_rooms = []
        private_rooms = []
        
        for room in rooms:
            r = room.lower()
            if 'living' in r or 'kitchen' in r or 'dining' in r:
                public_rooms.append(room)
            else:
                private_rooms.append(room)
        
        # Public zone layout
        if public_rooms:
            public_width = (self.config.building_width - 2 * wall) / len(public_rooms)
            x = wall
            for room in public_rooms:
                area = self._get_room_area(room, room_sizes)
                width = max(2.5, min(public_width, area / (split - wall)))
                result[room] = box(x, wall, x + width, split - wall)
                x += width + wall
        
        # Private zone layout (bedrooms)
        if private_rooms:
            private_height = (self.config.building_height - split - 2 * wall) / len(private_rooms)
            y = split + wall
            for room in private_rooms:
                area = self._get_room_area(room, room_sizes)
                height = max(2.5, min(private_height, area / (self.config.building_width - 2 * wall)))
                result[room] = box(wall, y, self.config.building_width - wall, y + height)
                y += height + wall
        
        # Add hallway connecting zones
        result['hallway'] = box(wall, split - wall, self.config.building_width - wall, split + wall)
        
        return result
    
    def _template_double_corridor(self, rooms: List[str], graph: nx.Graph,
                                   room_sizes: Dict) -> Dict[str, Polygon]:
        """
        Double corridor - office building style
        """
        result = {}
        wall = self.config.wall_thickness
        
        # Two corridors
        corridor_width = self.config.corridor_width
        corridor1_x = wall + 3
        corridor2_x = self.config.building_width - wall - corridor_width - 3
        
        # Add corridors
        result['corridor_1'] = box(corridor1_x, wall, corridor1_x + corridor_width, 
                                   self.config.building_height - wall)
        result['corridor_2'] = box(corridor2_x, wall, corridor2_x + corridor_width,
                                   self.config.building_height - wall)
        
        # Divide rooms between left, center, right
        left_rooms = []
        center_rooms = []
        right_rooms = []
        
        for room in rooms:
            r = room.lower()
            if 'office' in r or 'study' in r:
                left_rooms.append(room)
            elif 'conference' in r or 'meeting' in r:
                center_rooms.append(room)
            else:
                right_rooms.append(room)
        
        # Left side rooms
        left_width = corridor1_x - wall - wall
        left_height = (self.config.building_height - 2 * wall) / max(1, len(left_rooms))
        
        y = wall
        for room in left_rooms:
            area = self._get_room_area(room, room_sizes)
            height = max(2.5, min(left_height, area / left_width))
            result[room] = box(wall, y, corridor1_x - wall, y + height)
            y += height + wall
        
        # Center rooms (between corridors)
        center_width = corridor2_x - (corridor1_x + corridor_width) - 2 * wall
        center_height = (self.config.building_height - 2 * wall) / max(1, len(center_rooms))
        
        y = wall
        for room in center_rooms:
            area = self._get_room_area(room, room_sizes)
            height = max(2.5, min(center_height, area / center_width))
            result[room] = box(corridor1_x + corridor_width + wall, y,
                              corridor2_x - wall, y + height)
            y += height + wall
        
        # Right side rooms
        right_width = self.config.building_width - (corridor2_x + corridor_width) - wall
        right_height = (self.config.building_height - 2 * wall) / max(1, len(right_rooms))
        
        y = wall
        for room in right_rooms:
            area = self._get_room_area(room, room_sizes)
            height = max(2.5, min(right_height, area / right_width))
            result[room] = box(corridor2_x + corridor_width + wall, y,
                              self.config.building_width - wall, y + height)
            y += height + wall
        
        return result
    
    def _get_room_area(self, room: str, 
                       room_sizes: Dict[str, Tuple[float, float]] = None) -> float:
        """Get target area for room type"""
        
        if room_sizes and room in room_sizes:
            w, h = room_sizes[room]
            return w * h
        
        area_ranges = {
            'living': (16, 30),
            'kitchen': (8, 16),
            'dining': (10, 18),
            'master': (14, 24),
            'bedroom': (10, 18),
            'bath': (4, 9),
            'study': (8, 14),
            'office': (10, 16),
            'hallway': (5, 10)
        }
        
        room_lower = room.lower()
        for key, (min_a, max_a) in area_ranges.items():
            if key in room_lower:
                return random.uniform(min_a, max_a)
        
        return random.uniform(8, 16)
