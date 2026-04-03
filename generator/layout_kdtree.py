"""
Simple k-d Tree Floor Plan Generator - Working Version
No templates, no forced hallways - just clean spatial partitioning
"""
import random
import math
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Polygon, box
import networkx as nx
from dataclasses import dataclass

@dataclass
class LayoutConfig:
    building_width: float = 12.0
    building_height: float = 12.0
    wall_thickness: float = 0.15
    random_seed: int = 42
    min_room_size: float = 2.5

class KDNode:
    """K-d tree node representing a rectangular space"""
    def __init__(self, x, y, w, h, depth=0):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.depth = depth
        self.left = None
        self.right = None
        self.room = None
        
    @property
    def area(self):
        return self.w * self.h
    
    def to_polygon(self, wall_thickness=0.15):
        """Convert to shapely polygon"""
        return box(self.x, self.y, self.x + self.w, self.y + self.h)

class RoomLayoutSolverKDTree:
    """
    Pure k-d tree spatial partitioner
    No templates - just recursive space division
    """
    
    def __init__(self, config: LayoutConfig = None):
        self.config = config or LayoutConfig()
        random.seed(self.config.random_seed)
        
    def solve(self, adjacency_graph: nx.Graph,
              room_sizes: Dict[str, float] = None) -> Dict[str, Polygon]:
        """Generate floor plan using k-d tree partitioning"""
        
        rooms = list(adjacency_graph.nodes())
        if not rooms:
            return {}
        
        # Get target areas for rooms
        areas = {}
        for room in rooms:
            if room_sizes and room in room_sizes:
                areas[room] = room_sizes[room]
            else:
                areas[room] = self._get_default_area(room)
        
        # Sort rooms by area (largest first for better packing)
        sorted_rooms = sorted(rooms, key=lambda r: areas[r], reverse=True)
        
        # Create root node (full building)
        wall = self.config.wall_thickness
        root = KDNode(wall, wall, 
                      self.config.building_width - 2*wall,
                      self.config.building_height - 2*wall)
        
        # Recursively partition space
        self._partition(root, sorted_rooms, areas)
        
        # Collect leaf nodes and assign rooms
        leaves = []
        self._collect_leaves(root, leaves)
        
        # Assign rooms to leaves (largest room to largest leaf)
        leaves.sort(key=lambda l: l.area, reverse=True)
        
        result = {}
        for leaf, room in zip(leaves, sorted_rooms):
            leaf.room = room
            result[room] = leaf.to_polygon(self.config.wall_thickness)
        
        return result
    
    def _partition(self, node: KDNode, rooms: List[str], areas: Dict[str, float]):
        """Recursively partition space using k-d tree logic"""
        
        if len(rooms) <= 1:
            return
        
        # Decide split direction (alternate based on depth)
        split_vertical = (node.depth % 2 == 0)
        
        # Calculate target split position based on room areas
        mid = len(rooms) // 2
        left_rooms = rooms[:mid]
        right_rooms = rooms[mid:]
        
        left_area = sum(areas[r] for r in left_rooms)
        right_area = sum(areas[r] for r in right_rooms)
        total = left_area + right_area
        
        if split_vertical:
            # Vertical split (left/right)
            split_ratio = left_area / total if total > 0 else 0.5
            split_x = node.x + node.w * split_ratio
            
            # Ensure minimum room width
            min_w = self.config.min_room_size
            if split_x - node.x < min_w:
                split_x = node.x + min_w
            if node.x + node.w - split_x < min_w:
                split_x = node.x + node.w - min_w
            
            # Create child nodes
            node.left = KDNode(node.x, node.y, split_x - node.x, node.h, node.depth + 1)
            node.right = KDNode(split_x, node.y, node.x + node.w - split_x, node.h, node.depth + 1)
        else:
            # Horizontal split (top/bottom)
            split_ratio = left_area / total if total > 0 else 0.5
            split_y = node.y + node.h * split_ratio
            
            # Ensure minimum room height
            min_h = self.config.min_room_size
            if split_y - node.y < min_h:
                split_y = node.y + min_h
            if node.y + node.h - split_y < min_h:
                split_y = node.y + node.h - min_h
            
            # Create child nodes
            node.left = KDNode(node.x, node.y, node.w, split_y - node.y, node.depth + 1)
            node.right = KDNode(node.x, split_y, node.w, node.y + node.h - split_y, node.depth + 1)
        
        # Recursively partition children
        self._partition(node.left, left_rooms, areas)
        self._partition(node.right, right_rooms, areas)
    
    def _collect_leaves(self, node: KDNode, leaves: List[KDNode]):
        """Collect all leaf nodes from k-d tree"""
        if node.left is None and node.right is None:
            leaves.append(node)
        else:
            if node.left:
                self._collect_leaves(node.left, leaves)
            if node.right:
                self._collect_leaves(node.right, leaves)
    
    def _get_default_area(self, room: str) -> float:
        """Get default area for room type"""
        room_lower = room.lower()
        defaults = {
            'living': 25, 'kitchen': 12, 'dining': 12,
            'master': 18, 'bedroom': 14, 'bathroom': 6,
            'study': 10, 'hallway': 8
        }
        for key, area in defaults.items():
            if key in room_lower:
                return area
        return 12
