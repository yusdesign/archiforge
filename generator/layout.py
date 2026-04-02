"""
Procedural layout generation with true randomization
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Polygon, box, Point
from shapely.ops import unary_union
import networkx as nx
from dataclasses import dataclass
import random
import math

@dataclass
class LayoutConfig:
    building_width: float = 12.0
    building_height: float = 12.0
    wall_thickness: float = 0.15
    min_room_area: float = 4.0
    hallway_width: float = 1.2
    random_seed: int = 42

class ProceduralLayoutSolver:
    def __init__(self, config: LayoutConfig = None):
        self.config = config or LayoutConfig()
        random.seed(self.config.random_seed)
        np.random.seed(self.config.random_seed)
        
    def solve(self, adjacency_graph: nx.Graph,
              room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[str, Polygon]:
        """Generate truly randomized room layouts"""
        
        # Get rooms sorted by importance
        rooms = list(adjacency_graph.nodes())
        
        # Different layout strategies based on seed
        strategy = self.config.random_seed % 4
        
        if strategy == 0:
            return self._layout_spiral(rooms, adjacency_graph)
        elif strategy == 1:
            return self._layout_organic(rooms, adjacency_graph)
        elif strategy == 2:
            return self._layout_radial(rooms, adjacency_graph)
        else:
            return self._layout_recursive(rooms, adjacency_graph)
    
    def _layout_spiral(self, rooms: List[str], graph: nx.Graph) -> Dict[str, Polygon]:
        """Spiral layout starting from center"""
        result = {}
        
        # Start from center
        center_x = self.config.building_width / 2
        center_y = self.config.building_height / 2
        
        # Find main room (living or largest)
        main_room = self._find_main_room(rooms, graph)
        
        # Place main room at center
        main_size = self._get_room_size(main_room)
        main_w = math.sqrt(main_size) * random.uniform(0.8, 1.2)
        main_h = main_size / main_w
        result[main_room] = box(
            center_x - main_w/2, center_y - main_h/2,
            center_x + main_w/2, center_y + main_h/2
        )
        
        # Place other rooms in spiral pattern
        angle = 0
        radius = max(main_w, main_h) / 2 + 1
        other_rooms = [r for r in rooms if r != main_room]
        
        for i, room in enumerate(other_rooms):
            # Spiral angle increases
            angle += math.pi / 4  # 45 degrees
            radius += 0.5
            
            x = center_x + math.cos(angle) * radius
            y = center_y + math.sin(angle) * radius
            
            size = self._get_room_size(room)
            w = math.sqrt(size) * random.uniform(0.7, 1.3)
            h = size / w
            
            result[room] = box(x - w/2, y - h/2, x + w/2, y + h/2)
        
        return result
    
    def _layout_organic(self, rooms: List[str], graph: nx.Graph) -> Dict[str, Polygon]:
        """Organic, irregular layout"""
        result = {}
        
        # Create grid of possible positions
        grid_size = 20
        used_cells = set()
        
        # Sort by connectivity (most connected first)
        room_order = sorted(rooms, key=lambda r: graph.degree(r), reverse=True)
        
        for room in room_order:
            size = self._get_room_size(room)
            cells_needed = max(4, int(size / 2))
            
            # Try to find available cells
            best_cells = None
            best_compactness = float('inf')
            
            for attempt in range(100):
                # Random starting position
                start_x = random.randint(0, grid_size - 3)
                start_y = random.randint(0, grid_size - 3)
                
                # Try to find contiguous cells
                cells = self._find_contiguous_cells(start_x, start_y, cells_needed, used_cells, grid_size)
                
                if cells and len(cells) >= cells_needed * 0.7:
                    # Calculate compactness (how square-like)
                    min_x = min(c[0] for c in cells)
                    max_x = max(c[0] for c in cells)
                    min_y = min(c[1] for c in cells)
                    max_y = max(c[1] for c in cells)
                    width = max_x - min_x + 1
                    height = max_y - min_y + 1
                    compactness = abs(width - height)
                    
                    if compactness < best_compactness:
                        best_compactness = compactness
                        best_cells = cells
                        
                        if compactness == 0:
                            break
            
            if best_cells:
                # Convert cells to polygon
                min_x = min(c[0] for c in best_cells)
                max_x = max(c[0] for c in best_cells)
                min_y = min(c[1] for c in best_cells)
                max_y = max(c[1] for c in best_cells)
                
                # Scale to building dimensions
                scale_x = self.config.building_width / grid_size
                scale_y = self.config.building_height / grid_size
                
                x1 = min_x * scale_x + self.config.wall_thickness
                y1 = min_y * scale_y + self.config.wall_thickness
                x2 = (max_x + 1) * scale_x - self.config.wall_thickness
                y2 = (max_y + 1) * scale_y - self.config.wall_thickness
                
                result[room] = box(x1, y1, x2, y2)
                
                # Mark cells as used
                for cx, cy in best_cells:
                    used_cells.add((cx, cy))
            else:
                # Fallback: place randomly
                x = random.uniform(1, self.config.building_width - 3)
                y = random.uniform(1, self.config.building_height - 3)
                w = math.sqrt(size) * random.uniform(0.7, 1.3)
                h = size / w
                result[room] = box(x, y, x + w, y + h)
        
        return result
    
    def _layout_radial(self, rooms: List[str], graph: nx.Graph) -> Dict[str, Polygon]:
        """Radial layout around central point"""
        result = {}
        
        # Center
        cx = self.config.building_width / 2
        cy = self.config.building_height / 2
        
        # Main room at center
        main_room = self._find_main_room(rooms, graph)
        main_size = self._get_room_size(main_room)
        main_r = math.sqrt(main_size / math.pi) * random.uniform(0.8, 1.2)
        result[main_room] = self._circle_to_polygon(cx, cy, main_r)
        
        # Other rooms in rings
        other_rooms = [r for r in rooms if r != main_room]
        ring = 0
        angle_step = 2 * math.pi / max(1, len(other_rooms))
        
        for i, room in enumerate(other_rooms):
            ring = i // 6
            angle = (i % 6) * angle_step + random.uniform(-0.3, 0.3)
            radius = main_r + 1 + ring * 2 + random.uniform(-0.5, 0.5)
            
            x = cx + math.cos(angle) * radius
            y = cy + math.sin(angle) * radius
            
            size = self._get_room_size(room)
            room_r = math.sqrt(size / math.pi) * random.uniform(0.7, 1.3)
            
            result[room] = self._circle_to_polygon(x, y, room_r)
        
        return result
    
    def _layout_recursive(self, rooms: List[str], graph: nx.Graph) -> Dict[str, Polygon]:
        """Recursive subdivision with random split points"""
        
        def subdivide(space: Polygon, room_list: List[str], depth: int) -> Dict[str, Polygon]:
            if len(room_list) == 1:
                return {room_list[0]: space}
            
            if len(room_list) == 0:
                return {}
            
            # Random split orientation
            split_vertical = random.choice([True, False])
            bounds = space.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            
            # Random split ratio between 0.3 and 0.7
            split_ratio = random.uniform(0.35, 0.65)
            
            if split_vertical:
                split_x = bounds[0] + width * split_ratio
                space1 = box(bounds[0], bounds[1], split_x, bounds[3])
                space2 = box(split_x, bounds[1], bounds[2], bounds[3])
            else:
                split_y = bounds[1] + height * split_ratio
                space1 = box(bounds[0], bounds[1], bounds[2], split_y)
                space2 = box(bounds[0], split_y, bounds[2], bounds[3])
            
            # Split rooms randomly
            split_point = random.randint(1, len(room_list) - 1)
            rooms1 = room_list[:split_point]
            rooms2 = room_list[split_point:]
            
            result = {}
            result.update(subdivide(space1, rooms1, depth + 1))
            result.update(subdivide(space2, rooms2, depth + 1))
            
            return result
        
        # Start with full building
        building = box(0, 0, self.config.building_width, self.config.building_height)
        
        # Randomize room order
        room_order = rooms.copy()
        random.shuffle(room_order)
        
        return subdivide(building, room_order, 0)
    
    def _find_main_room(self, rooms: List[str], graph: nx.Graph) -> str:
        """Find the main/largest room"""
        priority = ['living', 'kitchen', 'dining']
        for room in rooms:
            for p in priority:
                if p in room.lower():
                    return room
        return rooms[0] if rooms else ""
    
    def _get_room_size(self, room: str) -> float:
        """Get appropriate size for room type"""
        size_map = {
            'living': random.uniform(20, 35),
            'kitchen': random.uniform(10, 18),
            'dining': random.uniform(10, 16),
            'bedroom': random.uniform(12, 20),
            'master': random.uniform(18, 28),
            'bathroom': random.uniform(5, 10),
            'study': random.uniform(8, 14),
            'hallway': random.uniform(6, 12)
        }
        
        for key, size_range in size_map.items():
            if key in room.lower():
                return size_range
        return random.uniform(8, 15)
    
    def _find_contiguous_cells(self, start_x: int, start_y: int, needed: int, 
                                used: set, grid_size: int) -> List[Tuple[int, int]]:
        """Find contiguous cells using flood fill"""
        cells = []
        to_visit = [(start_x, start_y)]
        visited = set()
        
        while to_visit and len(cells) < needed:
            x, y = to_visit.pop(0)
            if (x, y) in visited:
                continue
            visited.add((x, y))
            
            if (x, y) not in used and 0 <= x < grid_size and 0 <= y < grid_size:
                cells.append((x, y))
                
                # Add neighbors
                for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                    to_visit.append((x + dx, y + dy))
        
        return cells
    
    def _circle_to_polygon(self, cx: float, cy: float, radius: float) -> Polygon:
        """Convert circle to polygon (approximated)"""
        points = []
        for i in range(12):
            angle = 2 * math.pi * i / 12
            x = cx + math.cos(angle) * radius
            y = cy + math.sin(angle) * radius
            points.append((x, y))
        return Polygon(points)
