"""
k-d Tree Floor Plan Generator with Full Randomization
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
    min_room_size: float = 2.0
    max_room_size: float = 8.0

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
        self.split_vertical = None
        self.split_pos = None
        
    @property
    def area(self):
        return self.w * self.h
    
    def to_polygon(self, wall_thickness=0.15):
        """Convert to shapely polygon"""
        return box(self.x, self.y, self.x + self.w, self.y + self.h)

class RoomLayoutSolverKDTree:
    """
    k-d Tree spatial partitioner with full randomization
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
        
        # Generate RANDOMIZED room areas
        areas = {}
        for room in rooms:
            if room_sizes and room in room_sizes:
                # Use user size with random variation ±20%
                base = room_sizes[room]
                areas[room] = base * random.uniform(0.8, 1.2)
            else:
                # Generate random size based on room type
                areas[room] = self._get_random_room_area(room)
        
        # Shuffle rooms randomly for different tree structures
        shuffled_rooms = rooms.copy()
        random.shuffle(shuffled_rooms)
        
        # Sort by area (largest first) but with randomness
        shuffled_rooms.sort(key=lambda r: areas[r], reverse=True)
        # Add some randomness to ordering
        if len(shuffled_rooms) > 2:
            for i in range(random.randint(1, 3)):
                if i+1 < len(shuffled_rooms):
                    shuffled_rooms[i], shuffled_rooms[i+1] = shuffled_rooms[i+1], shuffled_rooms[i]
        
        # Create root node (full building with margin)
        wall = self.config.wall_thickness
        margin = wall * 2
        root = KDNode(margin, margin, 
                      self.config.building_width - 2*margin,
                      self.config.building_height - 2*margin)
        
        # Recursively partition space
        self._partition(root, shuffled_rooms, areas, depth=0)
        
        # Collect leaf nodes
        leaves = []
        self._collect_leaves(root, leaves)
        
        # If we have more leaves than rooms, merge some
        while len(leaves) > len(shuffled_rooms):
            # Find smallest leaf to merge with neighbor
            smallest = min(leaves, key=lambda l: l.area)
            # Find parent and merge
            parent = self._find_parent(root, smallest)
            if parent:
                # Convert parent to leaf
                parent.left = None
                parent.right = None
                leaves = []
                self._collect_leaves(root, leaves)
        
        # Sort leaves by area (largest first)
        leaves.sort(key=lambda l: l.area, reverse=True)
        
        # Assign rooms to leaves (largest room to largest leaf)
        result = {}
        for leaf, room in zip(leaves, shuffled_rooms):
            leaf.room = room
            result[room] = leaf.to_polygon(self.config.wall_thickness)
        
        # Post-process to ensure rooms touch
        result = self._ensure_adjacency(result, adjacency_graph)
        
        return result
    
    def _partition(self, node: KDNode, rooms: List[str], areas: Dict[str, float], depth: int):
        """Recursively partition space with RANDOM splits"""
        
        if len(rooms) <= 1:
            return
        
        # RANDOM split direction (not just alternating)
        # 60% vertical, 40% horizontal for variety
        split_vertical = random.random() < 0.6
        
        # RANDOM split position based on area (not exact)
        mid = len(rooms) // 2
        left_rooms = rooms[:mid]
        right_rooms = rooms[mid:]
        
        left_area = sum(areas[r] for r in left_rooms)
        right_area = sum(areas[r] for r in right_rooms)
        total = left_area + right_area
        
        if split_vertical:
            # Vertical split
            # RANDOM split ratio with bias from area
            area_ratio = left_area / total if total > 0 else 0.5
            # Add randomness to split position (±15%)
            random_factor = random.uniform(0.85, 1.15)
            split_ratio = min(0.85, max(0.15, area_ratio * random_factor))
            split_x = node.x + node.w * split_ratio
            
            # Ensure minimum room width
            min_w = self.config.min_room_size
            if split_x - node.x < min_w:
                split_x = node.x + min_w
            if node.x + node.w - split_x < min_w:
                split_x = node.x + node.w - min_w
            
            if split_x > node.x and split_x < node.x + node.w:
                node.split_vertical = True
                node.split_pos = split_x
                node.left = KDNode(node.x, node.y, split_x - node.x, node.h, depth + 1)
                node.right = KDNode(split_x, node.y, node.x + node.w - split_x, node.h, depth + 1)
                
                # Recursively partition
                self._partition(node.left, left_rooms, areas, depth + 1)
                self._partition(node.right, right_rooms, areas, depth + 1)
        else:
            # Horizontal split
            area_ratio = left_area / total if total > 0 else 0.5
            random_factor = random.uniform(0.85, 1.15)
            split_ratio = min(0.85, max(0.15, area_ratio * random_factor))
            split_y = node.y + node.h * split_ratio
            
            # Ensure minimum room height
            min_h = self.config.min_room_size
            if split_y - node.y < min_h:
                split_y = node.y + min_h
            if node.y + node.h - split_y < min_h:
                split_y = node.y + node.h - min_h
            
            if split_y > node.y and split_y < node.y + node.h:
                node.split_vertical = False
                node.split_pos = split_y
                node.left = KDNode(node.x, node.y, node.w, split_y - node.y, depth + 1)
                node.right = KDNode(node.x, split_y, node.w, node.y + node.h - split_y, depth + 1)
                
                self._partition(node.left, left_rooms, areas, depth + 1)
                self._partition(node.right, right_rooms, areas, depth + 1)
    
    def _collect_leaves(self, node: KDNode, leaves: List[KDNode]):
        """Collect all leaf nodes"""
        if node.left is None and node.right is None:
            leaves.append(node)
        else:
            if node.left:
                self._collect_leaves(node.left, leaves)
            if node.right:
                self._collect_leaves(node.right, leaves)
    
    def _find_parent(self, root: KDNode, target: KDNode) -> Optional[KDNode]:
        """Find parent of a node"""
        if root.left == target or root.right == target:
            return root
        if root.left:
            result = self._find_parent(root.left, target)
            if result:
                return result
        if root.right:
            result = self._find_parent(root.right, target)
            if result:
                return result
        return None
    
    def _ensure_adjacency(self, rooms: Dict[str, Polygon], graph: nx.Graph) -> Dict[str, Polygon]:
        """Ensure adjacent rooms actually touch"""
        result = rooms.copy()
        
        for u, v in graph.edges():
            if u in result and v in result:
                pu = result[u]
                pv = result[v]
                
                if pu.distance(pv) > 0.1:
                    # Move them closer
                    cu = pu.centroid
                    cv = pv.centroid
                    
                    dx = cv.x - cu.x
                    dy = cv.y - cu.y
                    dist = math.sqrt(dx*dx + dy*dy)
                    
                    if dist > 0:
                        dx /= dist
                        dy /= dist
                        
                        bu = pu.bounds
                        bv = pv.bounds
                        
                        if abs(dx) > abs(dy):
                            # Horizontal adjustment
                            new_x2 = bu[2] + dx * 0.5
                            new_x1 = bv[0] - dx * 0.5
                            result[u] = box(bu[0], bu[1], new_x2, bu[3])
                            result[v] = box(new_x1, bv[1], bv[2], bv[3])
                        else:
                            # Vertical adjustment
                            new_y2 = bu[3] + dy * 0.5
                            new_y1 = bv[1] - dy * 0.5
                            result[u] = box(bu[0], bu[1], bu[2], new_y2)
                            result[v] = box(bv[0], new_y1, bv[2], bv[3])
        
        return result
    
    def _get_random_room_area(self, room: str) -> float:
        """Generate RANDOM area for room type with wide variation"""
        room_lower = room.lower()
        
        # Wide ranges for each room type
        ranges = {
            'living': (18, 35),
            'kitchen': (8, 20),
            'dining': (8, 18),
            'master': (16, 28),
            'bedroom': (10, 22),
            'bathroom': (4, 12),
            'study': (6, 16),
            'hallway': (4, 12)
        }
        
        for key, (min_a, max_a) in ranges.items():
            if key in room_lower:
                # Random area within range
                area = random.uniform(min_a, max_a)
                # Add extra randomness (±15%)
                area *= random.uniform(0.85, 1.15)
                return max(min_a * 0.8, min(max_a * 1.2, area))
        
        # Default random range
        return random.uniform(8, 25)
