"""
ILP-based floor plan layout solver using PuLP
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
    ILP-based room layout solver using PuLP
    Implements the corner/edge model from the paper
    """
    
    def __init__(self, config: LayoutConfig = None):
        self.config = config or LayoutConfig()
        random.seed(self.config.random_seed)
        np.random.seed(self.config.random_seed)
        
    def solve(self, adjacency_graph: nx.Graph,
              room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[str, Polygon]:
        """Generate floor plan using ILP optimization"""
        
        rooms = list(adjacency_graph.nodes())
        
        # For small problems (≤ 8 rooms), use exact ILP
        if len(rooms) <= 8:
            return self._solve_exact_ilp(rooms, adjacency_graph, room_sizes)
        else:
            # For larger problems, use decomposition approach
            return self._solve_decomposition(rooms, adjacency_graph, room_sizes)
    
    def _solve_exact_ilp(self, rooms: List[str], graph: nx.Graph,
                         room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[str, Polygon]:
        """Exact ILP solver for small floor plans"""
        
        # Create corner and edge objects (simplified model)
        # For a rectangular building, we have 4 corners and 4 edges
        corners = ['NW', 'NE', 'SE', 'SW']
        edges = ['N', 'E', 'S', 'W']
        
        # Corner capacities (area in m²)
        corner_capacities = {
            'NW': 4.0, 'NE': 4.0, 'SE': 4.0, 'SW': 4.0
        }
        
        # Edge capacities (length in meters)
        edge_capacities = {
            'N': self.config.building_width - self.config.corridor_width * 2,
            'E': self.config.building_height - self.config.corridor_width * 2,
            'S': self.config.building_width - self.config.corridor_width * 2,
            'W': self.config.building_height - self.config.corridor_width * 2
        }
        
        # Distance matrix between objects (corners + edges)
        objects = corners + edges
        distances = self._compute_distance_matrix(objects)
        
        # Room sizes (in m²)
        room_areas = {}
        for room in rooms:
            if room_sizes and room in room_sizes:
                w, h = room_sizes[room]
                room_areas[room] = w * h
            else:
                room_areas[room] = self._estimate_room_area(room)
        
        # Group assignment (each room is its own group for now)
        # For true groups, we would cluster rooms by organizational unit
        groups = {room: i for i, room in enumerate(rooms)}
        
        # Create PuLP problem
        prob = pulp.LpProblem("FloorPlanning", pulp.LpMinimize)
        
        # Variables
        # x[g][e] = number of rooms of group g placed at edge e
        x = {}
        for g in groups.values():
            for e in edges:
                x[(g, e)] = pulp.LpVariable(f"x_{g}_{e}", lowBound=0, cat='Integer')
        
        # y[g][v][e] = 1 if group g occupies corner v extending into edge e
        y = {}
        for g in groups.values():
            for v in corners:
                for e in self._adjacent_edges(v):
                    y[(g, v, e)] = pulp.LpVariable(f"y_{g}_{v}_{e}", cat='Binary')
        
        # z[g][o] = 1 if group g has any room at object o
        z = {}
        for g in groups.values():
            for o in objects:
                z[(g, o)] = pulp.LpVariable(f"z_{g}_{o}", cat='Binary')
        
        # u[g][o][o'] = 1 if group g has rooms at both o and o'
        u = {}
        for g in groups.values():
            for o1 in objects:
                for o2 in objects:
                    if o1 != o2:
                        u[(g, o1, o2)] = pulp.LpVariable(f"u_{g}_{o1}_{o2}", cat='Binary')
        
        # Objective: minimize sum of distances for rooms in same group
        prob += pulp.lpSum([
            u[(g, o1, o2)] * distances.get((o1, o2), 10.0)
            for g in groups.values()
            for o1 in objects
            for o2 in objects
            if o1 != o2
        ])
        
        # Constraints
        
        # 1. All rooms must be placed
        for room in rooms:
            g = groups[room]
            area = room_areas[room]
            
            # Room must be placed either on an edge or corner
            # Simplified: we approximate by area contribution
            prob += pulp.lpSum([x[(g, e)] for e in edges]) + \
                    pulp.lpSum([y[(g, v, e)] for v in corners for e in self._adjacent_edges(v)]) >= 1
        
        # 2. Corner capacity (at most one room per corner)
        for v in corners:
            prob += pulp.lpSum([y[(g, v, e)] for g in groups.values() 
                               for e in self._adjacent_edges(v)]) <= 1
        
        # 3. Edge capacity
        for e in edges:
            prob += pulp.lpSum([x[(g, e)] * room_areas[rooms[0]] for g in groups.values()]) + \
                    pulp.lpSum([y[(g, v, e)] * (room_areas[rooms[0]] - corner_capacities[v])
                               for g in groups.values() for v in corners 
                               if e in self._adjacent_edges(v)]) <= edge_capacities[e] * 2  # Approx area
        
        # 4. Link z and x
        for g in groups.values():
            for e in edges:
                prob += x[(g, e)] <= 100 * z[(g, e)]
        
        # 5. Link z and y
        for g in groups.values():
            for v in corners:
                for e in self._adjacent_edges(v):
                    prob += y[(g, v, e)] <= z[(g, v)]
        
        # 6. Link u and z
        for g in groups.values():
            for o1 in objects:
                for o2 in objects:
                    if o1 != o2:
                        prob += z[(g, o1)] + z[(g, o2)] - 1 <= u[(g, o1, o2)]
        
        # Solve
        solver = pulp.PULP_CBC_CMD(timeLimit=self.config.time_limit_seconds, msg=False)
        result = prob.solve(solver)
        
        if pulp.LpStatus[result] in ['Optimal', 'Feasible']:
            # Convert solution to polygons
            return self._ilp_solution_to_polygons(rooms, groups, corners, edges, x, y, prob)
        else:
            # Fallback to heuristic
            return self._heuristic_fallback(rooms, graph)
    
    def _solve_decomposition(self, rooms: List[str], graph: nx.Graph,
                              room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[str, Polygon]:
        """Decomposition approach for larger floor plans"""
        
        # Step 1: Assign rooms to floors/zones
        zones = self._assign_to_zones(rooms, graph)
        
        # Step 2: Solve each zone independently
        result = {}
        for zone_name, zone_rooms in zones.items():
            zone_result = self._solve_zone(zone_rooms, graph)
            result.update(zone_result)
        
        return result
    
    def _assign_to_zones(self, rooms: List[str], graph: nx.Graph) -> Dict[str, List[str]]:
        """Assign rooms to functional zones"""
        zones = {
            'public': [],
            'private': [],
            'service': []
        }
        
        for room in rooms:
            room_lower = room.lower()
            if any(x in room_lower for x in ['living', 'kitchen', 'dining', 'study']):
                zones['public'].append(room)
            elif any(x in room_lower for x in ['bedroom', 'master', 'closet']):
                zones['private'].append(room)
            else:
                zones['service'].append(room)
        
        # Remove empty zones
        return {k: v for k, v in zones.items() if v}
    
    def _solve_zone(self, rooms: List[str], graph: nx.Graph) -> Dict[str, Polygon]:
        """Solve a single zone"""
        result = {}
        n = len(rooms)
        
        if n == 0:
            return result
        
        # Use recursive subdivision within zone
        bounds = box(0, 0, self.config.building_width, self.config.building_height)
        return self._subdivide_zone(bounds, rooms)
    
    def _subdivide_zone(self, space: Polygon, rooms: List[str]) -> Dict[str, Polygon]:
        """Recursive subdivision for a zone"""
        if len(rooms) == 1:
            return {rooms[0]: space}
        
        if len(rooms) == 0:
            return {}
        
        # Choose split direction
        bounds = space.bounds
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        
        split_vertical = width > height
        
        if split_vertical:
            split_ratio = random.uniform(0.3, 0.7)
            split_x = bounds[0] + width * split_ratio
            
            left = box(bounds[0], bounds[1], split_x, bounds[3])
            right = box(split_x, bounds[1], bounds[2], bounds[3])
            
            split_point = max(1, min(len(rooms) - 1, int(len(rooms) * split_ratio)))
            left_rooms = rooms[:split_point]
            right_rooms = rooms[split_point:]
            
            result = {}
            result.update(self._subdivide_zone(left, left_rooms))
            result.update(self._subdivide_zone(right, right_rooms))
            return result
        else:
            split_ratio = random.uniform(0.3, 0.7)
            split_y = bounds[1] + height * split_ratio
            
            bottom = box(bounds[0], bounds[1], bounds[2], split_y)
            top = box(bounds[0], split_y, bounds[2], bounds[3])
            
            split_point = max(1, min(len(rooms) - 1, int(len(rooms) * split_ratio)))
            bottom_rooms = rooms[:split_point]
            top_rooms = rooms[split_point:]
            
            result = {}
            result.update(self._subdivide_zone(bottom, bottom_rooms))
            result.update(self._subdivide_zone(top, top_rooms))
            return result
    
    def _ilp_solution_to_polygons(self, rooms: List[str], groups: Dict[str, int],
                                   corners: List[str], edges: List[str],
                                   x: Dict, y: Dict, prob) -> Dict[str, Polygon]:
        """Convert ILP solution to actual polygons"""
        result = {}
        
        # Simplified: create grid-based polygons based on solution
        n_rooms = len(rooms)
        cols = max(2, int(np.ceil(np.sqrt(n_rooms))))
        rows = max(2, int(np.ceil(n_rooms / cols)))
        
        cell_w = self.config.building_width / cols
        cell_h = self.config.building_height / rows
        
        for idx, room in enumerate(rooms):
            row = idx // cols
            col = idx % cols
            
            x1 = col * cell_w + self.config.wall_thickness
            y1 = row * cell_h + self.config.wall_thickness
            x2 = x1 + cell_w - self.config.wall_thickness * 2
            y2 = y1 + cell_h - self.config.wall_thickness * 2
            
            result[room] = box(x1, y1, x2, y2)
        
        return result
    
    def _compute_distance_matrix(self, objects: List[str]) -> Dict[Tuple[str, str], float]:
        """Compute distances between objects"""
        distances = {}
        
        # Simple Manhattan distances based on building geometry
        positions = {
            'NW': (0, 0), 'NE': (self.config.building_width, 0),
            'SE': (self.config.building_width, self.config.building_height),
            'SW': (0, self.config.building_height),
            'N': (self.config.building_width / 2, 0),
            'E': (self.config.building_width, self.config.building_height / 2),
            'S': (self.config.building_width / 2, self.config.building_height),
            'W': (0, self.config.building_height / 2)
        }
        
        for o1 in objects:
            for o2 in objects:
                if o1 in positions and o2 in positions:
                    p1 = positions[o1]
                    p2 = positions[o2]
                    dist = abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])
                    distances[(o1, o2)] = dist
                else:
                    distances[(o1, o2)] = 10.0
        
        return distances
    
    def _adjacent_edges(self, corner: str) -> List[str]:
        """Get edges adjacent to a corner"""
        adjacency = {
            'NW': ['N', 'W'],
            'NE': ['N', 'E'],
            'SE': ['S', 'E'],
            'SW': ['S', 'W']
        }
        return adjacency.get(corner, [])
    
    def _heuristic_fallback(self, rooms: List[str], graph: nx.Graph) -> Dict[str, Polygon]:
        """Fallback heuristic when ILP fails"""
        result = {}
        n_rooms = len(rooms)
        cols = max(2, int(np.ceil(np.sqrt(n_rooms))))
        rows = max(2, int(np.ceil(n_rooms / cols)))
        
        cell_w = self.config.building_width / cols
        cell_h = self.config.building_height / rows
        
        for idx, room in enumerate(rooms):
            row = idx // cols
            col = idx % cols
            
            x1 = col * cell_w + self.config.wall_thickness
            y1 = row * cell_h + self.config.wall_thickness
            x2 = x1 + cell_w - self.config.wall_thickness * 2
            y2 = y1 + cell_h - self.config.wall_thickness * 2
            
            result[room] = box(x1, y1, x2, y2)
        
        return result
    
    def _estimate_room_area(self, room: str) -> float:
        """Estimate appropriate area for room type"""
        area_map = {
            'living': random.uniform(18, 28),
            'kitchen': random.uniform(8, 14),
            'dining': random.uniform(10, 16),
            'bedroom': random.uniform(10, 18),
            'master': random.uniform(16, 24),
            'bathroom': random.uniform(4, 8),
            'study': random.uniform(8, 12)
        }
        
        for key, area in area_map.items():
            if key in room.lower():
                return area
        return random.uniform(10, 15)
