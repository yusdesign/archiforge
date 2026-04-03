"""
k-d Tree Floor Plan Generator with Multiple Branching Strategies
Strategies: Area-based, Aspect-based, Connectivity-based, Random, Hybrid
"""
import random
import math
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Polygon, box
import networkx as nx
from dataclasses import dataclass
from enum import Enum

class BranchingStrategy(Enum):
    AREA_BASED = "area"           # Split based on room areas
    ASPECT_BASED = "aspect"       # Split to create square-ish rooms
    CONNECTIVITY_BASED = "connect" # Split to keep connected rooms together
    RANDOM = "random"              # Pure random splits
    HYBRID = "hybrid"              # Mix of all strategies

@dataclass
class LayoutConfig:
    building_width: float = 12.0
    building_height: float = 12.0
    wall_thickness: float = 0.15
    random_seed: int = 42
    min_room_size: float = 2.0
    strategy: BranchingStrategy = BranchingStrategy.HYBRID
    depth_limit: int = 6

class KDNode:
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
        self.score = 0  # For strategy evaluation
        
    @property
    def area(self):
        return self.w * self.h
    
    @property
    def aspect_ratio(self):
        return max(self.w, self.h) / min(self.w, self.h) if min(self.w, self.h) > 0 else 1
    
    def to_polygon(self, wall_thickness=0.15):
        return box(self.x, self.y, self.x + self.w, self.y + self.h)

class RoomLayoutSolverKDTree:
    """
    k-d Tree with multiple branching strategies
    """
    
    def __init__(self, config: LayoutConfig = None):
        self.config = config or LayoutConfig()
        random.seed(self.config.random_seed)
        
    def solve(self, adjacency_graph: nx.Graph,
              room_sizes: Dict[str, float] = None) -> Dict[str, Polygon]:
        """Generate floor plan using k-d tree with selected strategy"""
        
        rooms = list(adjacency_graph.nodes())
        if not rooms:
            return {}
        
        # Generate randomized room areas
        areas = {}
        for room in rooms:
            if room_sizes and room in room_sizes:
                base = room_sizes[room]
                areas[room] = base * random.uniform(0.85, 1.15)
            else:
                areas[room] = self._get_random_room_area(room)
        
        # Shuffle rooms for variety
        shuffled_rooms = rooms.copy()
        random.shuffle(shuffled_rooms)
        shuffled_rooms.sort(key=lambda r: areas[r], reverse=True)
        
        # Create root node with margins
        wall = self.config.wall_thickness
        margin = wall * 2
        root = KDNode(margin, margin, 
                      self.config.building_width - 2*margin,
                      self.config.building_height - 2*margin)
        
        # Recursively partition with selected strategy
        self._partition_with_strategy(root, shuffled_rooms, areas, adjacency_graph)
        
        # Collect leaves and assign rooms
        leaves = []
        self._collect_leaves(root, leaves)
        
        # Ensure enough leaves
        while len(leaves) < len(shuffled_rooms):
            # Find deepest node to split further
            deepest = max(leaves, key=lambda l: l.depth)
            self._split_node(deepest, areas, shuffled_rooms, adjacency_graph)
            leaves = []
            self._collect_leaves(root, leaves)
        
        # Balance leaves if too many
        while len(leaves) > len(shuffled_rooms) * 1.5:
            # Merge smallest adjacent leaves
            self._merge_smallest_leaves(root)
            leaves = []
            self._collect_leaves(root, leaves)
        
        # Assign rooms to leaves
        leaves.sort(key=lambda l: l.area, reverse=True)
        
        result = {}
        for leaf, room in zip(leaves, shuffled_rooms):
            leaf.room = room
            result[room] = leaf.to_polygon(self.config.wall_thickness)
        
        # Post-process adjacency
        result = self._enforce_adjacency(result, adjacency_graph)
        
        return result
    
    def _partition_with_strategy(self, node: KDNode, rooms: List[str], 
                                  areas: Dict[str, float], graph: nx.Graph):
        """Partition using selected branching strategy"""
        
        if len(rooms) <= 1 or node.depth >= self.config.depth_limit:
            return
        
        # Calculate split based on strategy
        split_vertical, split_ratio = self._calculate_split(node, rooms, areas, graph)
        
        # Apply split
        if split_vertical:
            split_x = node.x + node.w * split_ratio
            min_w = self.config.min_room_size
            
            if split_x - node.x < min_w:
                split_x = node.x + min_w
            if node.x + node.w - split_x < min_w:
                split_x = node.x + node.w - min_w
            
            if split_x > node.x and split_x < node.x + node.w:
                node.split_vertical = True
                node.split_pos = split_x
                
                # Split rooms
                mid = int(len(rooms) * split_ratio)
                mid = max(1, min(mid, len(rooms) - 1))
                left_rooms = rooms[:mid]
                right_rooms = rooms[mid:]
                
                node.left = KDNode(node.x, node.y, split_x - node.x, node.h, node.depth + 1)
                node.right = KDNode(split_x, node.y, node.x + node.w - split_x, node.h, node.depth + 1)
                
                self._partition_with_strategy(node.left, left_rooms, areas, graph)
                self._partition_with_strategy(node.right, right_rooms, areas, graph)
        else:
            split_y = node.y + node.h * split_ratio
            min_h = self.config.min_room_size
            
            if split_y - node.y < min_h:
                split_y = node.y + min_h
            if node.y + node.h - split_y < min_h:
                split_y = node.y + node.h - min_h
            
            if split_y > node.y and split_y < node.y + node.h:
                node.split_vertical = False
                node.split_pos = split_y
                
                mid = int(len(rooms) * split_ratio)
                mid = max(1, min(mid, len(rooms) - 1))
                bottom_rooms = rooms[:mid]
                top_rooms = rooms[mid:]
                
                node.left = KDNode(node.x, node.y, node.w, split_y - node.y, node.depth + 1)
                node.right = KDNode(node.x, split_y, node.w, node.y + node.h - split_y, node.depth + 1)
                
                self._partition_with_strategy(node.left, bottom_rooms, areas, graph)
                self._partition_with_strategy(node.right, top_rooms, areas, graph)
    
    def _calculate_split(self, node: KDNode, rooms: List[str], 
                         areas: Dict[str, float], graph: nx.Graph) -> Tuple[bool, float]:
        """Calculate split based on current strategy"""
        
        total_area = sum(areas[r] for r in rooms)
        if total_area == 0:
            return (True, 0.5)
        
        if self.config.strategy == BranchingStrategy.AREA_BASED:
            return self._area_based_split(node, rooms, areas, total_area)
        elif self.config.strategy == BranchingStrategy.ASPECT_BASED:
            return self._aspect_based_split(node, rooms, areas, total_area)
        elif self.config.strategy == BranchingStrategy.CONNECTIVITY_BASED:
            return self._connectivity_based_split(node, rooms, areas, graph, total_area)
        elif self.config.strategy == BranchingStrategy.RANDOM:
            return self._random_split(node)
        else:  # HYBRID
            return self._hybrid_split(node, rooms, areas, graph, total_area)
    
    def _area_based_split(self, node: KDNode, rooms: List[str], 
                          areas: Dict[str, float], total_area: float) -> Tuple[bool, float]:
        """Split based on room areas (original k-d tree method)"""
        split_vertical = node.w > node.h
        
        # Cumulative area for finding median
        sorted_rooms = sorted(rooms, key=lambda r: areas[r])
        cum_area = 0
        target = total_area / 2
        
        for i, room in enumerate(sorted_rooms):
            cum_area += areas[room]
            if cum_area >= target:
                split_ratio = (i + 1) / len(rooms)
                break
        else:
            split_ratio = 0.5
        
        # Add randomness
        split_ratio *= random.uniform(0.9, 1.1)
        split_ratio = max(0.3, min(0.7, split_ratio))
        
        return (split_vertical, split_ratio)
    
    def _aspect_based_split(self, node: KDNode, rooms: List[str],
                            areas: Dict[str, float], total_area: float) -> Tuple[bool, float]:
        """Split to create more square-shaped rooms"""
        
        current_aspect = node.aspect_ratio
        
        # If current space is very wide, split vertically
        if current_aspect > 1.5:
            split_vertical = True
            split_ratio = 0.5
        # If very tall, split horizontally
        elif current_aspect < 0.67:
            split_vertical = False
            split_ratio = 0.5
        else:
            # Already square-ish, use area-based with preference
            split_vertical = node.w > node.h
            # Target equal areas
            split_ratio = 0.5
        
        # Add randomness
        split_ratio *= random.uniform(0.85, 1.15)
        split_ratio = max(0.3, min(0.7, split_ratio))
        
        return (split_vertical, split_ratio)
    
    def _connectivity_based_split(self, node: KDNode, rooms: List[str],
                                   areas: Dict[str, float], graph: nx.Graph,
                                   total_area: float) -> Tuple[bool, float]:
        """Split to keep connected rooms together"""
        
        # Build subgraph of these rooms
        subgraph = graph.subgraph(rooms)
        
        # Find connected components
        components = list(nx.connected_components(subgraph))
        
        if len(components) >= 2:
            # Split between components
            comp_sizes = [sum(areas[r] for r in comp) for comp in components]
            total = sum(comp_sizes)
            cum = 0
            
            for i, size in enumerate(comp_sizes):
                cum += size
                if cum >= total / 2:
                    split_ratio = (i + 1) / len(components)
                    break
            else:
                split_ratio = 0.5
        else:
            # All connected, use area-based
            split_ratio = 0.5
        
        split_vertical = node.w > node.h
        split_ratio = max(0.3, min(0.7, split_ratio))
        
        return (split_vertical, split_ratio)
    
    def _random_split(self, node: KDNode) -> Tuple[bool, float]:
        """Pure random split"""
        split_vertical = random.choice([True, False])
        split_ratio = random.uniform(0.3, 0.7)
        return (split_vertical, split_ratio)
    
    def _hybrid_split(self, node: KDNode, rooms: List[str],
                      areas: Dict[str, float], graph: nx.Graph,
                      total_area: float) -> Tuple[bool, float]:
        """Hybrid: evaluate multiple strategies and pick best"""
        
        strategies = [
            self._area_based_split(node, rooms, areas, total_area),
            self._aspect_based_split(node, rooms, areas, total_area),
            self._connectivity_based_split(node, rooms, areas, graph, total_area),
            self._random_split(node)
        ]
        
        # Score each strategy
        scores = []
        for vert, ratio in strategies:
            score = 0
            # Prefer splits that create balanced areas
            left_ratio = ratio
            right_ratio = 1 - ratio
            balance = 1 - abs(left_ratio - right_ratio)
            score += balance * 0.4
            
            # Prefer splits that create good aspect ratios
            if vert:
                new_aspect = (node.w * ratio) / node.h
            else:
                new_aspect = node.w / (node.h * ratio)
            aspect_score = 1 / (1 + abs(new_aspect - 1))
            score += aspect_score * 0.3
            
            # Add randomness
            score += random.random() * 0.3
            
            scores.append(score)
        
        # Pick best strategy
        best_idx = scores.index(max(scores))
        return strategies[best_idx]
    
    def _split_node(self, node: KDNode, areas: Dict[str, float],
                    rooms: List[str], graph: nx.Graph):
        """Split a leaf node further"""
        split_vertical = node.w > node.h
        split_ratio = 0.5
        
        node.split_vertical = split_vertical
        
        if split_vertical:
            split_x = node.x + node.w * split_ratio
            node.left = KDNode(node.x, node.y, split_x - node.x, node.h, node.depth + 1)
            node.right = KDNode(split_x, node.y, node.x + node.w - split_x, node.h, node.depth + 1)
        else:
            split_y = node.y + node.h * split_ratio
            node.left = KDNode(node.x, node.y, node.w, split_y - node.y, node.depth + 1)
            node.right = KDNode(node.x, split_y, node.w, node.y + node.h - split_y, node.depth + 1)
    
    def _merge_smallest_leaves(self, root: KDNode):
        """Merge the smallest leaf with its sibling"""
        leaves = []
        self._collect_leaves(root, leaves)
        
        if len(leaves) < 2:
            return
        
        smallest = min(leaves, key=lambda l: l.area)
        parent = self._find_parent(root, smallest)
        
        if parent:
            # Convert parent back to leaf
            parent.left = None
            parent.right = None
    
    def _collect_leaves(self, node: KDNode, leaves: List[KDNode]):
        if node.left is None and node.right is None:
            leaves.append(node)
        else:
            if node.left:
                self._collect_leaves(node.left, leaves)
            if node.right:
                self._collect_leaves(node.right, leaves)
    
    def _find_parent(self, root: KDNode, target: KDNode) -> Optional[KDNode]:
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
    
    def _enforce_adjacency(self, rooms: Dict[str, Polygon], graph: nx.Graph) -> Dict[str, Polygon]:
        result = rooms.copy()
        
        for u, v in graph.edges():
            if u in result and v in result:
                pu = result[u]
                pv = result[v]
                
                if pu.distance(pv) > 0.1:
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
                            new_x2 = bu[2] + dx * 0.3
                            new_x1 = bv[0] - dx * 0.3
                            result[u] = box(bu[0], bu[1], new_x2, bu[3])
                            result[v] = box(new_x1, bv[1], bv[2], bv[3])
                        else:
                            new_y2 = bu[3] + dy * 0.3
                            new_y1 = bv[1] - dy * 0.3
                            result[u] = box(bu[0], bu[1], bu[2], new_y2)
                            result[v] = box(bv[0], new_y1, bv[2], bv[3])
        
        return result
    
    def _get_random_room_area(self, room: str) -> float:
        room_lower = room.lower()
        ranges = {
            'living': (18, 35), 'kitchen': (8, 20), 'dining': (8, 18),
            'master': (16, 28), 'bedroom': (10, 22), 'bathroom': (4, 12),
            'study': (6, 16), 'hallway': (4, 12)
        }
        for key, (min_a, max_a) in ranges.items():
            if key in room_lower:
                area = random.uniform(min_a, max_a) * random.uniform(0.85, 1.15)
                return max(min_a * 0.8, min(max_a * 1.2, area))
        return random.uniform(8, 25)
