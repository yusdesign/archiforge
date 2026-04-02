"""
Simplified constraint solver for room placement
"""
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import random
import math

@dataclass
class RoomConstraint:
    name: str
    min_area: float = 9.0
    max_area: float = 25.0
    min_width: float = 2.5
    min_height: float = 2.5
    preferred_ratio: float = 1.0
    must_be_exterior: bool = False
    must_have_window: bool = True
    
class ConstraintSolver:
    def __init__(self, grid_size: Tuple[int, int] = (20, 20)):
        self.grid_width, self.grid_height = grid_size
        
    def solve_placement(self, rooms: List[str], 
                        constraints: Dict[str, RoomConstraint],
                        adjacencies: List[Tuple[str, str]]) -> Optional[Dict]:
        # Simple grid placement without complex SAT
        assignment = {}
        
        # Grid layout
        grid_cols = 5
        grid_rows = math.ceil(len(rooms) / grid_cols)
        cell_width = self.grid_width // grid_cols
        cell_height = self.grid_height // grid_rows
        
        for idx, room in enumerate(rooms):
            row = idx // grid_cols
            col = idx % grid_cols
            
            x = col * cell_width
            y = row * cell_height
            
            # Create rectangle for this room
            cells = []
            for i in range(cell_width // 2):
                for j in range(cell_height // 2):
                    cells.append((x + i, y + j))
            
            assignment[room] = cells[:max(4, len(cells)//2)]
        
        # Enforce adjacencies by moving rooms closer
        for room_a, room_b in adjacencies:
            if room_a in assignment and room_b in assignment:
                if not self._are_adjacent(assignment[room_a], assignment[room_b]):
                    # Connect them
                    self._connect_rooms(assignment[room_a], assignment[room_b])
        
        return assignment
    
    def _are_adjacent(self, cells_a: List[Tuple[int, int]], cells_b: List[Tuple[int, int]]) -> bool:
        for ax, ay in cells_a:
            for bx, by in cells_b:
                if abs(ax - bx) + abs(ay - by) == 1:
                    return True
        return False
    
    def _connect_rooms(self, cells_a: List[Tuple[int, int]], cells_b: List[Tuple[int, int]]):
        # Add bridge cells between rooms
        if not cells_a or not cells_b:
            return
        
        avg_a_x = sum(x for x, y in cells_a) // len(cells_a)
        avg_a_y = sum(y for x, y in cells_a) // len(cells_a)
        avg_b_x = sum(x for x, y in cells_b) // len(cells_b)
        avg_b_y = sum(y for x, y in cells_b) // len(cells_b)
        
        # Add connection points
        mid_x = (avg_a_x + avg_b_x) // 2
        mid_y = (avg_a_y + avg_b_y) // 2
        cells_a.append((mid_x, mid_y))
        cells_b.append((mid_x, mid_y))
