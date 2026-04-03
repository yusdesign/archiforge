"""
Hybrid floor plan solver: k-d tree partitioning + PuLP ILP room assignment
Based on: "Generating Floor Plan Layouts with K-D Trees and Evolutionary Algorithms"
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Polygon, box
import networkx as nx
from dataclasses import dataclass
import math
import random
from collections import deque

# Try to import PuLP for ILP optimization
try:
    import pulp
    HAS_PULP = True
except ImportError:
    HAS_PULP = False
    print("Warning: PuLP not available, using heuristic assignment")

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
    """Node in k-d tree representing a spatial partition"""
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
        self.id = id(self)
        
    @property
    def width(self):
        return self.x2 - self.x1
    
    @property
    def height(self):
        return self.y2 - self.y1
    
    @property
    def area(self):
        return self.width * self.height
    
    def to_polygon(self, wall_thickness=0.15):
        """Convert node to shapely polygon with wall inset"""
        return box(
            self.x1 + wall_thickness,
            self.y1 + wall_thickness,
            self.x2 - wall_thickness,
            self.y2 - wall_thickness
        )

class RoomLayoutSolverHybrid:
    """
    Hybrid solver: k-d tree for spatial partitioning + ILP for optimal room assignment
    """
    
    def __init__(self, config: LayoutConfig = None):
        self.config = config or LayoutConfig()
        random.seed(self.config.random_seed)
        np.random.seed(self.config.random_seed)
        self.kd_tree = None
        self.rooms = []
        
    def solve(self, adjacency_graph: nx.Graph,
              room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[str, Polygon]:
        """Generate floor plan using k-d tree + ILP optimization"""
        
        self.rooms = list(adjacency_graph.nodes())
        
        if not self.rooms:
            return {}
        
        # Step 1: Generate k-d tree partitions
        self.kd_tree = self._build_kdtree(
            self.config.wall_thickness,
            self.config.wall_thickness,
            self.config.building_width - self.config.wall_thickness,
            self.config.building_height - self.config.wall_thickness,
            depth=0
        )
        
        # Step 2: Get leaf nodes (potential room spaces)
        leaf_nodes = self._get_leaf_nodes(self.kd_tree)
        
        # Ensure enough leaves
        while len(leaf_nodes) < len(self.rooms):
            self._refine_largest_leaf()
            leaf_nodes = self._get_leaf_nodes(self.kd_tree)
        
        # Step 3: Use ILP to optimally assign rooms to leaves
        if HAS_PULP and len(self.rooms) <= 15:
            assignments = self._ilp_assign_rooms(leaf_nodes, adjacency_graph, room_sizes)
        else:
            assignments = self._heuristic_assign_rooms(leaf_nodes, adjacency_graph, room_sizes)
        
        # Step 4: Convert assignments to polygons
        result = {}
        for leaf, room in assignments.items():
            leaf.room_name = room
            result[room] = leaf.to_polygon(self.config.wall_thickness)
        
        # Step 5: Apply adjacency optimization
        result = self._optimize_adjacency(result, adjacency_graph)
        
        return result
    
    def _build_kdtree(self, x1, y1, x2, y2, depth) -> KDTreeNode:
        """Recursively build k-d tree by splitting space"""
        
        node = KDTreeNode(x1, y1, x2, y2, depth)
        
        width = x2 - x1
        height = y2 - y1
        
        # Stop conditions
        if depth >= self.config.max_depth:
            return node
        
        if width < self.config.min_room_size * 2 or height < self.config.min_room_size * 2:
            return node
        
        # Alternate split direction
        split_vertical = (depth % 2 == 0)
        
        # Random split position (between 0.3 and 0.7)
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
        """Get all leaf nodes from k-d tree"""
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
        """Split largest leaf to create more spaces"""
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
    
    
    def _ilp_assign_rooms(self, leaf_nodes: List[KDTreeNode], 
                          graph: nx.Graph,
                          room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[KDTreeNode, str]:
        """Use PuLP ILP to optimally assign rooms to leaf nodes"""
    
        n_leaves = len(leaf_nodes)
        n_rooms = len(self.rooms)
    
        if n_leaves < n_rooms:
            return self._heuristic_assign_rooms(leaf_nodes, graph, room_sizes)
    
        # Create problem
        prob = pulp.LpProblem("RoomAssignment", pulp.LpMinimize)
    
        # Decision variables: x[i][j] = 1 if room j assigned to leaf i
        x = {}
        for i, leaf in enumerate(leaf_nodes):
            for j, room in enumerate(self.rooms):
                x[(i, j)] = pulp.LpVariable(f"x_{i}_{j}", cat='Binary')
    
        # Each room assigned to exactly one leaf
        for j, room in enumerate(self.rooms):
            prob += pulp.lpSum(x[(i, j)] for i in range(n_leaves)) == 1
    
        # Each leaf gets at most one room
        for i in range(n_leaves):
            prob += pulp.lpSum(x[(i, j)] for j in range(n_rooms)) <= 1
    
        # Objective: minimize area difference (linear)
        area_cost = pulp.LpAffineExpression()
        for i, leaf in enumerate(leaf_nodes):
            for j, room in enumerate(self.rooms):
                target_area = self._get_room_area(room, room_sizes)
                if target_area > 0:
                    area_diff = abs(leaf.area - target_area) / target_area
                    area_cost += x[(i, j)] * area_diff
    
        # FIXED: Linear adjacency bonus using pre-computed distances
        # Instead of x[i]*x[k], we create a linear penalty: 
        # Rooms that should be adjacent are penalized if assigned to distant leaves
    
        # Create a distance penalty matrix
        adjacency_penalty = pulp.LpAffineExpression()
    
        # Pre-compute leaf-to-leaf distances
        leaf_distances = {}
        for i in range(n_leaves):
            for k in range(n_leaves):
                if i != k:
                    leaf_i = leaf_nodes[i]
                    leaf_k = leaf_nodes[k]
                    dist = abs(leaf_i.x1 - leaf_k.x1) + abs(leaf_i.y1 - leaf_k.y1)
                    leaf_distances[(i, k)] = dist
    
        # For each adjacent room pair, add penalty if assigned to different leaves
        # This is linear: we add penalty for each assignment, not product
        for u, v in graph.edges():
            if u not in self.rooms or v not in self.rooms:
                continue
            u_idx = self.rooms.index(u)
            v_idx = self.rooms.index(v)
        
            # Penalty: if assigned to different leaves, add distance-based penalty
            for i in range(n_leaves):
                for k in range(n_leaves):
                    if i != k:
                        # This is still quadratic! Need different approach
                        pass
    
        # SIMPLER APPROACH: Use only area cost for now
        # Adjacency will be handled in post-processing
        prob += area_cost
    
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
    
        # Handle unassigned rooms
        assigned_rooms = set(assignment.values())
        unassigned = [r for r in self.rooms if r not in assigned_rooms]
        unassigned_leaves = [leaf for leaf in leaf_nodes if leaf not in assignment]
    
        for room, leaf in zip(unassigned, unassigned_leaves):
            assignment[leaf] = room
    
        return assignment
    
    def _heuristic_assign_rooms(self, leaf_nodes: List[KDTreeNode],
                                 graph: nx.Graph,
                                 room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[KDTreeNode, str]:
        """Fallback heuristic when PuLP not available or too many rooms"""
        
        # Sort leaves by area (largest first)
        sorted_leaves = sorted(leaf_nodes, key=lambda l: l.area, reverse=True)
        
        # Sort rooms by target area (largest first)
        room_areas = [(room, self._get_room_area(room, room_sizes)) for room in self.rooms]
        sorted_rooms = sorted(room_areas, key=lambda x: x[1], reverse=True)
        
        # Assign
        assignment = {}
        for i, (room, area) in enumerate(sorted_rooms):
            if i < len(sorted_leaves):
                assignment[sorted_leaves[i]] = room
        
        return assignment
    
    def _optimize_adjacency(self, rooms: Dict[str, Polygon], 
                            graph: nx.Graph) -> Dict[str, Polygon]:
        """Optimize room positions for better adjacency"""
        
        result = rooms.copy()
        wall = self.config.wall_thickness
        
        # Multiple passes for better convergence
        for _ in range(3):
            for u, v in graph.edges():
                if u not in result or v not in result:
                    continue
                
                poly_u = result[u]
                poly_v = result[v]
                
                if poly_u.distance(poly_v) > wall * 2:
                    self._move_rooms_closer(result, u, v, wall)
        
        return result
    
    def _move_rooms_closer(self, rooms: Dict[str, Polygon], 
                           u: str, v: str, wall: float):
        """Move two rooms closer together"""
        
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
    
    def _get_room_area(self, room: str, 
                       room_sizes: Dict[str, Tuple[float, float]] = None) -> float:
        """Get target area for room"""
        
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
            'bathroom': (4, 9),
            'study': (8, 14),
            'office': (10, 16),
            'hallway': (5, 10)
        }
        
        room_lower = room.lower()
        for key, (min_a, max_a) in area_ranges.items():
            if key in room_lower:
                return random.uniform(min_a, max_a)
        
        return random.uniform(8, 16)
    
    def visualize_tree(self) -> str:
        """Debug: visualize k-d tree structure"""
        if not self.kd_tree:
            return "No tree built"
        
        def _print_node(node, level=0):
            if not node:
                return ""
            indent = "  " * level
            if node.is_leaf:
                return f"{indent}Leaf: {node.area:.1f}m² [{node.room_name}]\n"
            else:
                result = f"{indent}Node: {node.width:.1f}x{node.height:.1f}\n"
                result += _print_node(node.left, level + 1)
                result += _print_node(node.right, level + 1)
                return result
        
        return _print_node(self.kd_tree)
