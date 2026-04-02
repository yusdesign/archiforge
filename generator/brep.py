"""
Enhanced 3D B-rep construction with extruded walls
"""
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from shapely.geometry import Polygon as ShapelyPolygon, Point, LineString
from shapely.ops import unary_union
from dataclasses import dataclass, field
from enum import Enum

class DoorType(Enum):
    SINGLE = "single"
    DOUBLE = "double"
    SLIDING = "sliding"

@dataclass
class DoorConfig:
    position: Tuple[float, float, float]  # x, y, z
    width: float = 0.9
    height: float = 2.1
    type: DoorType = DoorType.SINGLE
    swing_angle: float = 90  # degrees

@dataclass
class BRepConfig:
    wall_thickness: float = 0.15
    floor_thickness: float = 0.20
    ceiling_height: float = 2.8
    foundation_depth: float = 0.5
    roof_overhang: float = 0.5
    door_width: float = 0.9
    door_height: float = 2.1
    window_height: float = 1.2
    window_width: float = 1.0
    material: str = "concrete"

class BRepBuilder:
    def __init__(self, config: BRepConfig = None):
        self.config = config or BRepConfig()
        self.doors: List[DoorConfig] = []
        
    def build_building(self, rooms_2d: Dict[str, ShapelyPolygon],
                      add_roof: bool = True,
                      add_foundation: bool = True) -> Dict[str, Any]:
        """Build complete 3D representation with walls"""
        
        building = {
            'walls': [],
            'floors': [],
            'roof': None,
            'foundation': None,
            'doors': [],
            'windows': [],
            'bounds': self._get_bounds(rooms_2d)
        }
        
        # Get overall footprint
        footprint = unary_union(list(rooms_2d.values()))
        
        # Build foundation
        if add_foundation:
            building['foundation'] = self._build_foundation(footprint)
        
        # Build floor slab
        building['floors'].append(self._build_floor(footprint))
        
        # Build walls for each room
        all_walls = []
        for room_name, room_poly in rooms_2d.items():
            walls = self._build_room_walls(room_poly, room_name)
            all_walls.extend(walls)
        
        building['walls'] = all_walls
        
        # Add doors between adjacent rooms
        building['doors'] = self._add_doors(rooms_2d)
        
        # Build roof
        if add_roof:
            building['roof'] = self._build_roof(footprint)
        
        return building
    
    def _get_bounds(self, rooms_2d: Dict[str, ShapelyPolygon]) -> Dict:
        """Get building bounds"""
        footprint = unary_union(list(rooms_2d.values()))
        bounds = footprint.bounds
        return {
            'xmin': bounds[0], 'xmax': bounds[2],
            'ymin': bounds[1], 'ymax': bounds[3],
            'zmin': 0, 'zmax': self.config.ceiling_height
        }
    
    def _build_foundation(self, footprint: ShapelyPolygon) -> Dict:
        """Build foundation as extruded polygon"""
        return {
            'type': 'foundation',
            'polygon': footprint,
            'height': self.config.foundation_depth,
            'z_offset': -self.config.foundation_depth,
            'material': 'concrete'
        }
    
    def _build_floor(self, footprint: ShapelyPolygon) -> Dict:
        """Build floor slab"""
        return {
            'type': 'floor',
            'polygon': footprint,
            'height': self.config.floor_thickness,
            'z_offset': 0,
            'material': 'concrete'
        }
    
    def _build_room_walls(self, room_poly: ShapelyPolygon, room_name: str) -> List[Dict]:
        """Build walls for a single room"""
        walls = []
        coords = list(room_poly.exterior.coords)
        
        for i in range(len(coords) - 1):
            p1 = coords[i]
            p2 = coords[i+1]
            
            length = np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
            
            if length > 0.1:
                wall = {
                    'type': 'wall',
                    'room': room_name,
                    'start': p1,
                    'end': p2,
                    'length': length,
                    'thickness': self.config.wall_thickness,
                    'height': self.config.ceiling_height,
                    'z_offset': 0,
                    'material': 'brick'
                }
                walls.append(wall)
        
        return walls
    
    def _add_doors(self, rooms_2d: Dict[str, ShapelyPolygon]) -> List[DoorConfig]:
        """Add doors between adjacent rooms"""
        doors = []
        room_list = list(rooms_2d.keys())
        
        for i in range(len(room_list)):
            for j in range(i+1, len(room_list)):
                room_a = room_list[i]
                room_b = room_list[j]
                
                poly_a = rooms_2d[room_a]
                poly_b = rooms_2d[room_b]
                
                # Find shared boundary
                intersection = poly_a.intersection(poly_b)
                
                if not intersection.is_empty and intersection.geom_type == 'LineString':
                    # Get the shared wall segment
                    coords = list(intersection.coords)
                    if len(coords) >= 2:
                        # Calculate door position (center of shared wall)
                        x1, y1 = coords[0]
                        x2, y2 = coords[1]
                        center_x = (x1 + x2) / 2
                        center_y = (y1 + y2) / 2
                        
                        door = DoorConfig(
                            position=(center_x, center_y, 0),
                            width=self.config.door_width,
                            height=self.config.door_height,
                            type=DoorType.SINGLE
                        )
                        doors.append(door)
        
        return doors
    
    def _build_roof(self, footprint: ShapelyPolygon) -> Dict:
        """Build pitched roof"""
        bounds = footprint.bounds
        width = bounds[2] - bounds[0]
        depth = bounds[3] - bounds[1]
        pitch_height = max(width, depth) * 0.25
        
        return {
            'type': 'roof',
            'polygon': footprint,
            'pitch_height': pitch_height,
            'overhang': self.config.roof_overhang,
            'z_offset': self.config.ceiling_height,
            'material': 'tile'
        }

class BRepValidator:
    def __init__(self, tolerance: float = 1e-6):
        self.tolerance = tolerance
        
    def validate(self, building: Dict[str, Any]) -> Dict[str, Any]:
        """Validate building geometry"""
        results = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'statistics': {},
            'repair_suggestions': []
        }
        
        if not building:
            results['is_valid'] = False
            results['errors'].append("No building geometry")
            return results
        
        # Calculate statistics
        total_wall_length = sum(w.get('length', 0) for w in building.get('walls', []))
        total_wall_area = total_wall_length * building.get('bounds', {}).get('zmax', 2.8)
        
        results['statistics'] = {
            'wall_count': len(building.get('walls', [])),
            'door_count': len(building.get('doors', [])),
            'total_wall_length_m': total_wall_length,
            'total_wall_area_m2': total_wall_area,
            'floor_area_m2': building.get('bounds', {}).get('xmax', 0) * building.get('bounds', {}).get('ymax', 0),
            'height_m': building.get('bounds', {}).get('zmax', 2.8),
            'has_roof': building.get('roof') is not None,
            'has_foundation': building.get('foundation') is not None
        }
        
        # Add suggestions
        if results['statistics']['door_count'] == 0:
            results['warnings'].append("No doors detected - rooms may not be connected")
            results['repair_suggestions'].append("Ensure rooms share walls for door placement")
        
        if results['statistics']['wall_count'] == 0:
            results['is_valid'] = False
            results['errors'].append("No walls generated")
        
        return results
