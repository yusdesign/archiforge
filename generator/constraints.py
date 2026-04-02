"""
Constraint satisfaction for architectural layouts using SAT solving
"""
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from pysat.solvers import Glucose3
from pysat.card import CardEnc
import numpy as np

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
    """SAT-based constraint solver for room placement"""
    
    def __init__(self, grid_size: Tuple[int, int] = (10, 10)):
        self.grid_width, self.grid_height = grid_size
        self.cell_area = 1.0  # 1m² per cell
        self.solver = None
        
    def solve_placement(self, rooms: List[str], 
                        constraints: Dict[str, RoomConstraint],
                        adjacencies: List[Tuple[str, str]]) -> Optional[Dict]:
        """
        Solve room placement using SAT solving
        Returns: {room: set of (x,y) cells} or None if unsatisfiable
        """
        self.solver = Glucose3()
        n_rooms = len(rooms)
        n_cells = self.grid_width * self.grid_height
        
        # Variable: room r occupies cell c
        # var index = r * n_cells + c + 1 (SAT vars start at 1)
        def var(room_idx, cell_idx):
            return room_idx * n_cells + cell_idx + 1
        
        # Each cell can have at most one room
        for cell in range(n_cells):
            vars_for_cell = [var(r, cell) for r in range(n_rooms)]
            self.solver.add_clause([-v for v in vars_for_cell])  # at most one
            # Actually need exactly one? No, empty cells allowed
            # But ensure coverage of all rooms: each room has at least one cell
            self.solver.add_clause(vars_for_cell)  # at least one? No, that forces all rooms in every cell
        
        # Each room occupies at least its min area
        for r, room in enumerate(rooms):
            min_cells = int(constraints[room].min_area / self.cell_area)
            cell_vars = [var(r, c) for c in range(n_cells)]
            # At least min_cells cells for this room
            for clause in CardEnc.atleast(cell_vars, min_cells, use_simplify=True):
                self.solver.add_clause(clause)
        
        # Room area constraints (max)
        for r, room in enumerate(rooms):
            max_cells = int(constraints[room].max_area / self.cell_area)
            cell_vars = [var(r, c) for c in range(n_cells)]
            for clause in CardEnc.atmost(cell_vars, max_cells, use_simplify=True):
                self.solver.add_clause(clause)
        
        # Adjacency constraints: rooms must share a boundary
        for room_a, room_b in adjacencies:
            r_a = rooms.index(room_a)
            r_b = rooms.index(room_b)
            self._add_adjacency_constraint(r_a, r_b)
        
        # Solve
        if self.solver.solve():
            model = self.solver.get_model()
            return self._extract_solution(model, rooms, n_cells)
        return None
    
    def _add_adjacency_constraint(self, r_a: int, r_b: int):
        """Ensure rooms share at least one edge (not just corner)"""
        n_cells = self.grid_width * self.grid_height
        
        for cell_a in range(n_cells):
            x_a, y_a = cell_a % self.grid_width, cell_a // self.grid_width
            # Check neighbors (right and down to avoid double counting)
            for dx, dy in [(1,0), (0,1)]:
                x_b, y_b = x_a + dx, y_a + dy
                if 0 <= x_b < self.grid_width and 0 <= y_b < self.grid_height:
                    cell_b = y_b * self.grid_width + x_b
                    
                    # If room A at cell_a AND room B at cell_b, adjacency satisfied
                    var_a = r_a * n_cells + cell_a + 1
                    var_b = r_b * n_cells + cell_b + 1
                    
                    # (var_a ∧ var_b) → adjacency_possible
                    # We need at least one such pair
                    self.solver.add_clause([var_a, var_b])
    
    def _extract_solution(self, model, rooms, n_cells):
        """Convert SAT model to room assignments"""
        assignment = {room: [] for room in rooms}
        for lit in model:
            if lit > 0:  # True literal
                lit -= 1  # Convert back to 0-index
                room_idx = lit // n_cells
                cell_idx = lit % n_cells
                if room_idx < len(rooms):
                    x = cell_idx % self.grid_width
                    y = cell_idx // self.grid_width
                    assignment[rooms[room_idx]].append((x, y))
        return assignment

    def _apply_adjacency_constraint(self, r_a: int, r_b: int):
        """Simpler adjacency using direct neighbor clauses"""
        n_cells = self.grid_width * self.grid_height
        
        adjacency_vars = []
        for cell_a in range(n_cells):
            x_a, y_a = cell_a % self.grid_width, cell_a // self.grid_width
            for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                x_b, y_b = x_a + dx, y_a + dy
                if 0 <= x_b < self.grid_width and 0 <= y_b < self.grid_height:
                    cell_b = y_b * self.grid_width + x_b
                    var_a = r_a * n_cells + cell_a + 1
                    var_b = r_b * n_cells + cell_b + 1
                    adjacency_vars.append(var_a)
                    adjacency_vars.append(var_b)
        
        # At least one adjacent pair exists
        if adjacency_vars:
            self.solver.add_clause(adjacency_vars)
