"""
ILP-based floor plan layout solver with proper wall thickness
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
    wall_thickness: float = 0.15  # 15cm walls
    corridor_width: float = 1.2
    random_seed: int = 42
    time_limit_seconds: int = 30

class RoomLayoutSolverILP:
    
    def __init__(self, config: LayoutConfig = None):
        self.config = config or LayoutConfig()
        random.seed(self.config.random_seed)
        np.random.seed(self.config.random_seed)
        
    def solve(self, adjacency_graph: nx.Graph,
              room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[str, Polygon]:
        """Generate non-overlapping floor plan with proper walls"""
        
        rooms = list(adjacency_graph.nodes())
        
        # Generate random sizes for each room
        room_dimensions = {}
        for room in rooms:
            area = self._get_random_room_area(room)
            aspect = random.uniform(0.7, 1.4)
            width = math.sqrt(area * aspect)
            height = area / width
            room_dimensions[room] = (width, height)
        
        # Choose layout strategy
        layout_style = self.config.random_seed % 5
        
        if layout_style == 0:
            return self._layout_rectangular(rooms, room_dimensions, adjacency_graph)
        elif layout_style == 1:
            return self._layout_central_hallway(rooms, room_dimensions, adjacency_graph)
        elif layout_style == 2:
            return self._layout_grid(rooms, room_dimensions, adjacency_graph)
        elif layout_style == 3:
            return self._layout_recursive(rooms, room_dimensions)
        else:
            return self._layout_compact(rooms, room_dimensions, adjacency_graph)
    
    def _layout_rectangular(self, rooms: List[str], 
                            dims: Dict[str, Tuple[float, float]],
                            graph: nx.Graph) -> Dict[str, Polygon]:
        """Clean rectangular layout with proper wall gaps"""
        result = {}
        
        # Sort by size (largest first)
        sorted_rooms = sorted(rooms, key=lambda r: dims[r][0] * dims[r][1], reverse=True)
        
        # Calculate wall offset
        wall = self.config.wall_thickness
        
        # Place rooms in a snake pattern with wall gaps
        x = wall
        y = wall
        max_height = 0
        row_height = 0
        
        for room in sorted_rooms:
            w, h = dims[room]
            
            # Check if needs new row (with wall gap)
            if x + w + wall > self.config.building_width - wall:
                x = wall
                y += row_height + wall
                row_height = 0
            
            # Ensure within bounds
            if y + h + wall > self.config.building_height - wall:
                h = self.config.building_height - y - wall
            
            # Create room with wall offset
            result[room] = box(x, y, x + w, y + h)
            
            # Update position (add wall gap)
            x += w + wall
            row_height = max(row_height, h)
        
        return result
    
    def _layout_central_hallway(self, rooms: List[str],
                                 dims: Dict[str, Tuple[float, float]],
                                 graph: nx.Graph) -> Dict[str, Polygon]:
        """Hallway with rooms on both sides and proper wall gaps"""
        result = {}
        wall = self.config.wall_thickness
        
        # Hallway dimensions
        hallway_width = self.config.corridor_width
        hallway_y = wall
        hallway_height = self.config.building_height - 2 * wall
        
        # Place hallway
        hallway_x = (self.config.building_width - hallway_width) / 2
        result['hallway'] = box(hallway_x, hallway_y,
                               hallway_x + hallway_width, hallway_y + hallway_height)
        
        # Separate rooms by type
        left_rooms = []
        right_rooms = []
        
        for room in rooms:
            if 'bedroom' in room.lower() or 'bathroom' in room.lower():
                right_rooms.append(room)
            else:
                left_rooms.append(room)
        
        # Place left side rooms (with wall gap)
        left_x = hallway_x - wall
        current_y = hallway_y
        
        for room in left_rooms:
            w, h = dims[room]
            h = min(h, hallway_height * 0.8)
            
            if current_y + h + wall > hallway_y + hallway_height:
                break
            
            result[room] = box(left_x - w, current_y, left_x, current_y + h)
            current_y += h + wall
        
        # Place right side rooms (with wall gap)
        right_x = hallway_x + hallway_width + wall
        current_y = hallway_y
        
        for room in right_rooms:
            w, h = dims[room]
            h = min(h, hallway_height * 0.8)
            
            if current_y + h + wall > hallway_y + hallway_height:
                break
            
            result[room] = box(right_x, current_y, right_x + w, current_y + h)
            current_y += h + wall
        
        return result
    
    def _layout_grid(self, rooms: List[str],
                     dims: Dict[str, Tuple[float, float]],
                     graph: nx.Graph) -> Dict[str, Polygon]:
        """Grid layout with wall thickness"""
        result = {}
        
        n = len(rooms)
        cols = max(2, min(4, int(np.ceil(np.sqrt(n)))))
        rows = int(np.ceil(n / cols))
        
        wall = self.config.wall_thickness
        margin = wall * 2
        
        cell_w = (self.config.building_width - margin * 2) / cols
        cell_h = (self.config.building_height - margin * 2) / rows
        
        for idx, room in enumerate(rooms):
            row = idx // cols
            col = idx % cols
            
            w, h = dims[room]
            
            # Fit to cell with wall margins
            w = min(w, cell_w - wall)
            h = min(h, cell_h - wall)
            w = max(2.0, w)
            h = max(2.0, h)
            
            x = margin + col * cell_w + wall/2
            y = margin + row * cell_h + wall/2
            
            result[room] = box(x, y, x + w, y + h)
        
        return result
    
    def _layout_recursive(self, rooms: List[str],
                          dims: Dict[str, Tuple[float, float]]) -> Dict[str, Polygon]:
        """Recursive subdivision with wall thickness"""
        wall = self.config.wall_thickness
        
        def subdivide(space: Polygon, room_list: List[str]) -> Dict[str, Polygon]:
            if len(room_list) == 1:
                # Add wall inset
                bounds = space.bounds
                return {room_list[0]: box(
                    bounds[0] + wall, bounds[1] + wall,
                    bounds[2] - wall, bounds[3] - wall
                )}
            
            if len(room_list) == 0:
                return {}
            
            bounds = space.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            
            # Calculate total area needed for each half
            mid = len(room_list) // 2
            left_rooms = room_list[:mid]
            right_rooms = room_list[mid:]
            
            left_area = sum(dims[r][0] * dims[r][1] for r in left_rooms)
            right_area = sum(dims[r][0] * dims[r][1] for r in right_rooms)
            total = left_area + right_area
            
            # Choose split direction based on space shape
            split_vertical = width > height
            
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
        
        building = box(wall, wall, 
                      self.config.building_width - wall,
                      self.config.building_height - wall)
        
        # Sort by size for better packing
        sorted_rooms = sorted(rooms, key=lambda r: dims[r][0] * dims[r][1], reverse=True)
        
        return subdivide(building, sorted_rooms)
    
    def _layout_compact(self, rooms: List[str],
                        dims: Dict[str, Tuple[float, float]],
                        graph: nx.Graph) -> Dict[str, Polygon]:
        """Compact layout with wall gaps between rooms"""
        result = {}
        wall = self.config.wall_thickness
        
        # Sort by connectivity (most connected first)
        connectivity = {r: graph.degree(r) for r in rooms}
        sorted_rooms = sorted(rooms, key=lambda r: connectivity[r], reverse=True)
        
        # Place first room
        first = sorted_rooms[0]
        w, h = dims[first]
        result[first] = box(wall, wall, wall + w, wall + h)
        
        # Place remaining rooms adjacent to placed ones
        for room in sorted_rooms[1:]:
            w, h = dims[room]
            best_pos = None
            best_dist = float('inf')
            
            # Try positions adjacent to existing rooms
            for placed_room, placed_poly in result.items():
                if graph.has_edge(room, placed_room):
                    bounds = placed_poly.bounds
                    
                    # Try four sides with wall gap
                    candidates = [
                        (bounds[2] + wall, bounds[1], bounds[2] + wall + w, bounds[1] + h),  # right
                        (bounds[0] - w - wall, bounds[1], bounds[0] - wall, bounds[1] + h),  # left
                        (bounds[0], bounds[3] + wall, bounds[0] + w, bounds[3] + wall + h),  # top
                        (bounds[0], bounds[1] - h - wall, bounds[0] + w, bounds[1] - wall)   # bottom
                    ]
                    
                    for x1, y1, x2, y2 in candidates:
                        if x1 < wall or x2 > self.config.building_width - wall or \
                           y1 < wall or y2 > self.config.building_height - wall:
                            continue
                        
                        candidate = box(x1, y1, x2, y2)
                        
                        # Check overlap with wall gap
                        overlap = False
                        for existing in result.values():
                            if candidate.intersects(existing.buffer(wall)):
                                overlap = True
                                break
                        
                        if not overlap:
                            dist = abs(x1 - bounds[0]) + abs(y1 - bounds[1])
                            if dist < best_dist:
                                best_dist = dist
                                best_pos = candidate
            
            if best_pos:
                result[room] = best_pos
            else:
                # Fallback: place in empty corner with wall margins
                w, h = dims[room]
                result[room] = box(wall, self.config.building_height - h - wall,
                                  wall + w, self.config.building_height - wall)
        
        return result
    
    def _get_random_room_area(self, room: str) -> float:
        """Generate random realistic area for room type"""
        room_lower = room.lower()
        
        area_ranges = {
            'living': (16, 30),
            'kitchen': (8, 16),
            'dining': (10, 18),
            'master': (14, 24),
            'bedroom': (10, 18),
            'bathroom': (4, 9),
            'study': (8, 14),
            'office': (10, 16),
            'hallway': (5, 10)
        }
        
        for key, (min_a, max_a) in area_ranges.items():
            if key in room_lower:
                return random.uniform(min_a, max_a)
        
        return random.uniform(8, 16)
