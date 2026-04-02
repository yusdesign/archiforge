"""
Constraint satisfaction for architectural layouts (simplified version)
"""
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import numpy as np
import random
from itertools import product

@dataclass
class RoomConstraint:
    name: str
    min_area: float = 9.0  # square meters
    max_area: float = 25.0
    min_width: float = 2.5
    min_height: float = 2.5
    preferred_ratio: float = 1.0
    must_be_exterior: bool = False
    must_have_window: bool = True
    
class ConstraintSolver:
    """Simplified constraint solver using greedy algorithm with backtracking"""
    
    def __init__(self, grid_size: Tuple[int, int] = (10, 10)):
        self.grid_width, self.grid_height = grid_size
        self.cell_area = 1.0  # 1m² per cell
        
    def solve_placement(self, rooms: List[str], 
                        constraints: Dict[str, RoomConstraint],
                        adjacencies: List[Tuple[str, str]]) -> Optional[Dict]:
        """
        Solve room placement using recursive backtracking
        
        Returns: {room: set of (x,y) cells} or None if unsatisfiable
        """
        # Sort rooms by importance (largest first, then most connected)
        room_priority = []
        for room in rooms:
            area = constraints[room].min_area if room in constraints else 9.0
            connectivity = sum(1 for a, b in adjacencies if room in (a, b))
            room_priority.append((room, area, connectivity))
        
        room_priority.sort(key=lambda x: (-x[1], -x[2]))
        sorted_rooms = [r[0] for r in room_priority]
        
        # Initialize empty grid
        grid = [[None for _ in range(self.grid_width)] for _ in range(self.grid_height)]
        assignment = {room: [] for room in rooms}
        
        # Place rooms recursively
        if self._backtrack_placement(0, sorted_rooms, constraints, adjacencies, grid, assignment):
            return assignment
        return None
    
    def _backtrack_placement(self, idx: int, rooms: List[str],
                            constraints: Dict[str, RoomConstraint],
                            adjacencies: List[Tuple[str, str]],
                            grid: List[List[Optional[str]]],
                            assignment: Dict[str, List[Tuple[int, int]]]) -> bool:
        """Recursive backtracking for room placement"""
        if idx >= len(rooms):
            return self._verify_adjacencies(assignment, adjacencies)
        
        room = rooms[idx]
        
        # Get room size
        if room in constraints:
            area = constraints[room].min_area
        else:
            area = 9.0
        
        cells_needed = int(np.ceil(area / self.cell_area))
        
        # Try all possible positions
        for y in range(self.grid_height):
            for x in range(self.grid_width):
                # Try different shapes
                for width in range(1, min(cells_needed + 1, self.grid_width - x + 1)):
                    height = int(np.ceil(cells_needed / width))
                    
                    if y + height > self.grid_height:
                        continue
                    
                    # Check if space is available
                    cells = []
                    valid = True
                    for i in range(width):
                        for j in range(height):
                            if grid[y + j][x + i] is not None:
                                valid = False
                                break
                            cells.append((x + i, y + j))
                        if not valid:
                            break
                    
                    if valid and len(cells) >= cells_needed * 0.8:  # Allow slight underfill
                        # Place room
                        for cx, cy in cells:
                            grid[cy][cx] = room
                            assignment[room].append((cx, cy))
                        
                        # Recurse
                        if self._backtrack_placement(idx + 1, rooms, constraints, adjacencies, grid, assignment):
                            return True
                        
                        # Backtrack
                        for cx, cy in cells:
                            grid[cy][cx] = None
                            assignment[room] = []
        
        return False
    
    def _verify_adjacencies(self, assignment: Dict[str, List[Tuple[int, int]]],
                           adjacencies: List[Tuple[str, str]]) -> bool:
        """Verify all adjacency constraints are satisfied"""
        # Create set of cells for quick lookup
        cell_sets = {room: set(cells) for room, cells in assignment.items()}
        
        for room_a, room_b in adjacencies:
            if room_a not in cell_sets or room_b not in cell_sets:
                continue
            
            adjacent = False
            for ax, ay in cell_sets[room_a]:
                for bx, by in cell_sets[room_b]:
                    if abs(ax - bx) + abs(ay - by) == 1:  # Manhattan distance = 1 (share edge)
                        adjacent = True
                        break
                if adjacent:
                    break
            
            if not adjacent:
                return False
        
        return True
    
    def _get_room_placement(self, grid, rooms):
        """Convert grid to assignment dictionary"""
        assignment = {room: [] for room in rooms}
        for y in range(self.grid_height):
            for x in range(self.grid_width):
                room = grid[y][x]
                if room and room in assignment:
                    assignment[room].append((x, y))
        return assignment
