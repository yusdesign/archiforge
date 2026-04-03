"""
Hybrid floor plan solver: k-d tree partitioning + PuLP ILP room assignment
With proper room type constraints
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Polygon, box
import networkx as nx
from dataclasses import dataclass
import math
import random
from collections import deque

try:
    import pulp
    HAS_PULP = True
except ImportError:
    HAS_PULP = False
    print("Warning: PuLP not available")

@dataclass
class LayoutConfig:
    building_width: float = 12.0
    building_height: float = 12.0
    wall_thickness: float = 0.15
    corridor_width: float = 1.2
    random_seed: int = 42
    max_depth: int = 4
    min_room_size: float = 2.0

class KDTreeNode:
    def __init__(self, x1, y1, x2, y2, depth=0):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.depth = depth
        self.left = None
        self.right = None
        self.room_name = None
        self.is_leaf = True
        
    @property
    def width(self):
        return self.x2 - self.x1
    
    @property
    def height(self):
        return self.y2 - self.y1
    
    @property
    def area(self):
        return self.width * self.height
    
    @property
    def aspect_ratio(self):
        return self.width / self.height if self.height > 0 else 1
    
    def to_polygon(self, wall_thickness=0.15):
        return box(
            self.x1 + wall_thickness,
            self.y1 + wall_thickness,
            self.x2 - wall_thickness,
            self.y2 - wall_thickness
        )

class RoomLayoutSolverHybrid:
    
    def __init__(self, config: LayoutConfig = None):
        self.config = config or LayoutConfig()
        random.seed(self.config.random_seed)
        np.random.seed(self.config.random_seed)
        self.kd_tree = None
        self.rooms = []
        
    def solve(self, adjacency_graph: nx.Graph,
              room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[str, Polygon]:
        
        self.rooms = list(adjacency_graph.nodes())
        
        if not self.rooms:
            return {}
        
        # Step 1: Build k-d tree
        self.kd_tree = self._build_kdtree(
            self.config.wall_thickness,
            self.config.wall_thickness,
            self.config.building_width - self.config.wall_thickness,
            self.config.building_height - self.config.wall_thickness,
            depth=0
        )
        
        # Step 2: Get leaf nodes
        leaf_nodes = self._get_leaf_nodes(self.kd_tree)
        
        # Ensure enough leaves
        while len(leaf_nodes) < len(self.rooms):
            self._refine_largest_leaf()
            leaf_nodes = self._get_leaf_nodes(self.kd_tree)
        
        # Step 3: Assign rooms using ILP or heuristic
        if HAS_PULP and len(self.rooms) <= 15:
            assignments = self._ilp_assign_rooms_constrained(leaf_nodes, adjacency_graph, room_sizes)
        else:
            assignments = self._heuristic_assign_rooms_constrained(leaf_nodes, adjacency_graph, room_sizes)
        
        # Step 4: Convert to polygons
        result = {}
        for leaf, room in assignments.items():
            leaf.room_name = room
            result[room] = leaf.to_polygon(self.config.wall_thickness)
        
        # Step 5: Optimize adjacency
        result = self._optimize_adjacency(result, adjacency_graph)
        
        return result
    
    def _build_kdtree(self, x1, y1, x2, y2, depth) -> KDTreeNode:
        node = KDTreeNode(x1, y1, x2, y2, depth)
        
        width = x2 - x1
        height = y2 - y1
        
        if depth >= self.config.max_depth:
            return node
        if width < self.config.min_room_size * 2 or height < self.config.min_room_size * 2:
            return node
        
        split_vertical = (depth % 2 == 0)
        split_ratio = random.uniform(0.35, 0.65)
        
        if split_vertical:
            split_x = x1 + width * split_ratio
            if split_x - x1 < self.config.min_room_size:
                split_x = x1 + self.config.min_room_size
            if x2 - split_x < self.config.min_room_size:
                split_x = x2 - self.config.min_room_size
            node.left = self._build_kdtree(x1, y1, split_x, y2, depth + 1)
            node.right = self._build_kdtree(split_x, y1, x2, y2, depth + 1)
        else:
            split_y = y1 + height * split_ratio
            if split_y - y1 < self.config.min_room_size:
                split_y = y1 + self.config.min_room_size
            if y2 - split_y < self.config.min_room_size:
                split_y = y2 - self.config.min_room_size
            node.left = self._build_kdtree(x1, y1, x2, split_y, depth + 1)
            node.right = self._build_kdtree(x1, split_y, x2, y2, depth + 1)
        
        node.is_leaf = False
        return node
    
    def _get_leaf_nodes(self, node: KDTreeNode) -> List[KDTreeNode]:
        leaves = []
        queue = deque([node])
        while queue:
            current = queue.popleft()
            if current.is_leaf:
                leaves.append(current)
            else:
                if current.left:
                    queue.append(current.left)
                if current.right:
                    queue.append(current.right)
        return leaves
    
    def _refine_largest_leaf(self):
        leaves = self._get_leaf_nodes(self.kd_tree)
        if not leaves:
            return
        largest = max(leaves, key=lambda l: l.area)
        largest.is_leaf = False
        width = largest.width
        height = largest.height
        split_vertical = width > height
        if split_vertical:
            split_x = largest.x1 + width / 2
            largest.left = KDTreeNode(largest.x1, largest.y1, split_x, largest.y2, largest.depth + 1)
            largest.right = KDTreeNode(split_x, largest.y1, largest.x2, largest.y2, largest.depth + 1)
        else:
            split_y = largest.y1 + height / 2
            largest.left = KDTreeNode(largest.x1, largest.y1, largest.x2, split_y, largest.depth + 1)
            largest.right = KDTreeNode(largest.x1, split_y, largest.x2, largest.y2, largest.depth + 1)
    
    def _ilp_assign_rooms_constrained(self, leaf_nodes: List[KDTreeNode],
                                       graph: nx.Graph,
                                       room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[KDTreeNode, str]:
        """ILP with room type constraints (size ranges)"""
        
        n_leaves = len(leaf_nodes)
        n_rooms = len(self.rooms)
        
        if n_leaves < n_rooms:
            return self._heuristic_assign_rooms_constrained(leaf_nodes, graph, room_sizes)
        
        prob = pulp.LpProblem("RoomAssignment", pulp.LpMinimize)
        
        # Variables
        x = {}
        for i, leaf in enumerate(leaf_nodes):
            for j, room in enumerate(self.rooms):
                x[(i, j)] = pulp.LpVariable(f"x_{i}_{j}", cat='Binary')
        
        # Each room assigned once
        for j in range(n_rooms):
            prob += pulp.lpSum(x[(i, j)] for i in range(n_leaves)) == 1
        
        # Each leaf gets at most one room
        for i in range(n_leaves):
            prob += pulp.lpSum(x[(i, j)] for j in range(n_rooms)) <= 1
        
        # NEW: Room type constraints - only allow assignment if leaf area is appropriate
        for i, leaf in enumerate(leaf_nodes):
            for j, room in enumerate(self.rooms):
                min_area, max_area, pref_ratio = self._get_room_constraints(room, room_sizes)
                
                # Check if leaf area is within acceptable range
                if leaf.area < min_area * 0.7 or leaf.area > max_area * 1.3:
                    # Forbid this assignment
                    prob += x[(i, j)] == 0
                else:
                    # Calculate how good this assignment is (for objective)
                    area_penalty = abs(leaf.area - (min_area + max_area) / 2) / max_area
                    # Aspect ratio penalty
                    ratio_penalty = abs(leaf.aspect_ratio - pref_ratio) / pref_ratio
                    total_penalty = area_penalty * 0.7 + ratio_penalty * 0.3
        
        # Objective: minimize total penalty
        objective = pulp.LpAffineExpression()
        for i, leaf in enumerate(leaf_nodes):
            for j, room in enumerate(self.rooms):
                min_area, max_area, pref_ratio = self._get_room_constraints(room, room_sizes)
                if leaf.area >= min_area * 0.7 and leaf.area <= max_area * 1.3:
                    area_penalty = abs(leaf.area - (min_area + max_area) / 2) / max_area
                    ratio_penalty = abs(leaf.aspect_ratio - pref_ratio) / pref_ratio if pref_ratio > 0 else 0
                    penalty = area_penalty * 0.7 + ratio_penalty * 0.3
                    objective += x[(i, j)] * penalty
        
        prob += objective
        
        # Solve
        solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=10)
        prob.solve(solver)
        
        # Extract assignment
        assignment = {}
        for i, leaf in enumerate(leaf_nodes):
            for j, room in enumerate(self.rooms):
                if pulp.value(x[(i, j)]) == 1:
                    assignment[leaf] = room
                    break
        
        # Fill unassigned
        assigned_rooms = set(assignment.values())
        unassigned = [r for r in self.rooms if r not in assigned_rooms]
        unassigned_leaves = [leaf for leaf in leaf_nodes if leaf not in assignment]
        
        # Sort by area for fallback
        unassigned.sort(key=lambda r: self._get_room_constraints(r, room_sizes)[0], reverse=True)
        unassigned_leaves.sort(key=lambda l: l.area, reverse=True)
        
        for room, leaf in zip(unassigned, unassigned_leaves):
            assignment[leaf] = room
        
        return assignment
    
    def _heuristic_assign_rooms_constrained(self, leaf_nodes: List[KDTreeNode],
                                             graph: nx.Graph,
                                             room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[KDTreeNode, str]:
        """Heuristic assignment respecting room constraints"""
        
        # Sort leaves by area
        sorted_leaves = sorted(leaf_nodes, key=lambda l: l.area, reverse=True)
        
        # Sort rooms by target area (largest first)
        room_info = [(room, self._get_room_constraints(room, room_sizes)) for room in self.rooms]
        # Sort by preferred area (average of min/max)
        room_info.sort(key=lambda x: (x[1][0] + x[1][1]) / 2, reverse=True)
        
        assignment = {}
        for i, (room, (min_a, max_a, pref_ratio)) in enumerate(room_info):
            if i < len(sorted_leaves):
                assignment[sorted_leaves[i]] = room
        
        return assignment
    
    def _get_room_constraints(self, room: str, 
                              room_sizes: Dict[str, Tuple[float, float]] = None) -> Tuple[float, float, float]:
        """Get min_area, max_area, preferred aspect ratio for room type"""
        
        if room_sizes and room in room_sizes:
            w, h = room_sizes[room]
            area = w * h
            ratio = w / h
            return (area * 0.8, area * 1.2, ratio)
        
        # Realistic constraints for each room type
        constraints = {
            'living': (16, 30, 1.2),      # slightly wider than tall
            'kitchen': (8, 16, 1.0),
            'dining': (10, 18, 1.2),
            'master': (14, 24, 1.1),
            'bedroom': (10, 18, 1.0),
            'bath': (4, 9, 0.8),          # often square or slightly taller
            'bathroom': (4, 9, 0.8),
            'study': (8, 14, 1.0),
            'office': (10, 16, 1.0),
            'hallway': (5, 10, 2.0),      # long and narrow
            'closet': (2, 5, 0.5)         # small, narrow
        }
        
        room_lower = room.lower()
        for key, (min_a, max_a, ratio) in constraints.items():
            if key in room_lower:
                # Add some randomness based on seed
                variation = 0.8 + (self.config.random_seed % 40) / 100  # 0.8 to 1.2
                return (min_a * variation, max_a * variation, ratio)
        
        return (8, 16, 1.0)
    
    def _optimize_adjacency(self, rooms: Dict[str, Polygon], 
                            graph: nx.Graph) -> Dict[str, Polygon]:
        result = rooms.copy()
        wall = self.config.wall_thickness
        
        for _ in range(3):
            for u, v in graph.edges():
                if u not in result or v not in result:
                    continue
                if result[u].distance(result[v]) > wall * 2:
                    self._move_rooms_closer(result, u, v, wall)
        
        return result
    
    def _move_rooms_closer(self, rooms: Dict[str, Polygon], 
                           u: str, v: str, wall: float):
        poly_u = rooms[u]
        poly_v = rooms[v]
        
        cu = poly_u.centroid
        cv = poly_v.centroid
        
        dx = cv.x - cu.x
        dy = cv.y - cu.y
        dist = max(0.01, math.sqrt(dx*dx + dy*dy))
        
        dx /= dist
        dy /= dist
        
        move_dist = min(poly_u.distance(poly_v) / 2, 0.5)
        
        bounds_u = poly_u.bounds
        bounds_v = poly_v.bounds
        
        if abs(dx) > abs(dy):
            new_x2_u = bounds_u[2] + dx * move_dist
            new_x1_v = bounds_v[0] - dx * move_dist
            rooms[u] = box(bounds_u[0], bounds_u[1], new_x2_u, bounds_u[3])
            rooms[v] = box(new_x1_v, bounds_v[1], bounds_v[2], bounds_v[3])
        else:
            new_y2_u = bounds_u[3] + dy * move_dist
            new_y1_v = bounds_v[1] - dy * move_dist
            rooms[u] = box(bounds_u[0], bounds_u[1], bounds_u[2], new_y2_u)
            rooms[v] = box(bounds_v[0], new_y1_v, bounds_v[2], bounds_v[3])
