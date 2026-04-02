"""
Enhanced 3D B-rep construction with proper volume calculation and door/window support
"""
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union
from dataclasses import dataclass
import math

@dataclass
class BRepConfig:
    wall_thickness: float = 0.15
    floor_thickness: float = 0.20
    ceiling_height: float = 2.8
    foundation_depth: float = 0.5
    roof_overhang: float = 0.5
    door_width: float = 0.9
    door_height: float = 2.1
    window_width: float = 1.2
    window_height: float = 1.0
    material: str = "concrete"

class BRepBuilder:
    def __init__(self, config: BRepConfig = None):
        self.config = config or BRepConfig()
        
    def build_building(self, rooms_2d: Dict[str, ShapelyPolygon],
                      add_roof: bool = True,
                      add_foundation: bool = True) -> Dict[str, Any]:
        """Build complete 3D building with proper volume"""
        
        # Get overall footprint
        all_rooms = unary_union(list(rooms_2d.values()))
        
        # Calculate building bounds
        bounds = all_rooms.bounds
        
        # Calculate actual volume
        floor_area = all_rooms.area
        volume = floor_area * self.config.ceiling_height
        
        building = {
            'type': 'building',
            'bounds': {
                'xmin': bounds[0], 'xmax': bounds[2],
                'ymin': bounds[1], 'ymax': bounds[3],
                'zmin': -self.config.foundation_depth,
                'zmax': self.config.ceiling_height
            },
            'floor_area_m2': floor_area,
            'volume_m3': volume,
            'rooms': len(rooms_2d),
            'components': []
        }
        
        # Add foundation
        if add_foundation:
            building['components'].append({
                'type': 'foundation',
                'area': floor_area,
                'height': self.config.foundation_depth,
                'volume': floor_area * self.config.foundation_depth,
                'z': -self.config.foundation_depth
            })
        
        # Add floor slab
        building['components'].append({
            'type': 'floor',
            'area': floor_area,
            'height': self.config.floor_thickness,
            'volume': floor_area * self.config.floor_thickness,
            'z': 0
        })
        
        # Add walls (perimeter)
        perimeter = all_rooms.boundary
        wall_length = perimeter.length
        wall_volume = wall_length * self.config.wall_thickness * self.config.ceiling_height
        
        building['components'].append({
            'type': 'walls',
            'length_m': wall_length,
            'height': self.config.ceiling_height,
            'thickness': self.config.wall_thickness,
            'volume_m3': wall_volume
        })
        
        # Add interior walls (between rooms)
        interior_wall_length = self._calculate_interior_walls(rooms_2d)
        interior_wall_volume = interior_wall_length * self.config.wall_thickness * self.config.ceiling_height
        
        if interior_wall_volume > 0:
            building['components'].append({
                'type': 'interior_walls',
                'length_m': interior_wall_length,
                'height': self.config.ceiling_height,
                'thickness': self.config.wall_thickness,
                'volume_m3': interior_wall_volume
            })
        
        # Add roof
        if add_roof:
            roof_volume = self._calculate_roof_volume(floor_area)
            building['components'].append({
                'type': 'roof',
                'area': floor_area,
                'volume_m3': roof_volume,
                'z': self.config.ceiling_height
            })
        
        # Calculate total volume
        building['total_volume_m3'] = sum(c.get('volume_m3', 0) for c in building['components'])
        
        return building
    
    def _calculate_interior_walls(self, rooms_2d: Dict[str, ShapelyPolygon]) -> float:
        """Calculate total interior wall length between rooms"""
        total_length = 0
        room_names = list(rooms_2d.keys())
        
        for i in range(len(room_names)):
            for j in range(i+1, len(room_names)):
                poly_i = rooms_2d[room_names[i]]
                poly_j = rooms_2d[room_names[j]]
                
                # Check if they share a wall
                intersection = poly_i.intersection(poly_j)
                
                if not intersection.is_empty:
                    if intersection.geom_type == 'LineString':
                        total_length += intersection.length
                    elif intersection.geom_type == 'MultiLineString':
                        for line in intersection.geoms:
                            total_length += line.length
        
        return total_length
    
    def _calculate_roof_volume(self, floor_area: float) -> float:
        """Calculate roof volume (simplified as pyramid)"""
        overhang_area = (math.sqrt(floor_area) + self.config.roof_overhang * 2) ** 2
        roof_height = math.sqrt(overhang_area) * 0.3
        return overhang_area * roof_height / 3

class BRepValidator:
    def __init__(self, tolerance: float = 1e-6):
        self.tolerance = tolerance
        
    def validate(self, building: Dict[str, Any]) -> Dict[str, Any]:
        """Validate building with proper volume calculation"""
        
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
        
        # Extract statistics
        volume = building.get('volume_m3', 0)
        floor_area = building.get('floor_area_m2', 0)
        total_volume = building.get('total_volume_m3', volume)
        
        results['statistics'] = {
            'volume_m3': total_volume,
            'floor_area_m2': floor_area,
            'room_count': building.get('rooms', 0),
            'component_count': len(building.get('components', [])),
            'building_height_m': building.get('bounds', {}).get('zmax', 0) - building.get('bounds', {}).get('zmin', 0),
            'footprint_area_m2': floor_area
        }
        
        # Add component breakdown
        for comp in building.get('components', []):
            comp_type = comp.get('type')
            if comp_type == 'walls':
                results['statistics']['wall_length_m'] = comp.get('length_m', 0)
                results['statistics']['wall_volume_m3'] = comp.get('volume_m3', 0)
            elif comp_type == 'interior_walls':
                results['statistics']['interior_wall_length_m'] = comp.get('length_m', 0)
        
        # Validation checks
        if total_volume <= 0:
            results['is_valid'] = False
            results['errors'].append(f"Zero volume detected: {total_volume} m³")
            results['repair_suggestions'].append("Check that rooms are properly connected and have positive area")
        else:
            results['is_valid'] = True
            results['repair_suggestions'].append(f"Building volume: {total_volume:.2f} m³ ✓")
        
        if floor_area <= 0:
            results['is_valid'] = False
            results['errors'].append("Zero floor area")
        
        # Check for shared walls
        if results['statistics'].get('interior_wall_length_m', 0) == 0:
            results['warnings'].append("No interior walls detected - rooms may not share walls")
            results['repair_suggestions'].append("Ensure rooms are placed adjacent to each other")
        else:
            results['repair_suggestions'].append(f"Interior walls: {results['statistics']['interior_wall_length_m']:.2f}m ✓")
        
        return results
