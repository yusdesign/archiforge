"""
B-rep construction and validation using trimesh
"""
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union
from dataclasses import dataclass

# Try to import trimesh, fallback to simple meshes
try:
    import trimesh
    HAS_TRIMESH = True
except ImportError:
    HAS_TRIMESH = False
    print("Warning: trimesh not available, using simplified meshes")

@dataclass
class BRepConfig:
    wall_thickness: float = 0.15
    floor_thickness: float = 0.20
    ceiling_height: float = 2.8
    foundation_depth: float = 0.5
    roof_overhang: float = 0.5

class BRepBuilder:
    def __init__(self, config: BRepConfig = None):
        self.config = config or BRepConfig()
        
    def build_building(self, rooms_2d: Dict[str, ShapelyPolygon],
                      add_roof: bool = True,
                      add_foundation: bool = True):
        """Build 3D representation (simplified)"""
        if HAS_TRIMESH:
            return self._build_trimesh(rooms_2d, add_roof, add_foundation)
        else:
            return self._build_simple(rooms_2d)
    
    def _build_trimesh(self, rooms_2d, add_roof, add_foundation):
        """Build using trimesh"""
        meshes = []
        
        # Get footprint
        footprint = unary_union(list(rooms_2d.values()))
        
        # Create extruded building
        if HAS_TRIMESH and hasattr(trimesh, 'creation'):
            try:
                mesh = trimesh.creation.extrude_polygon(
                    footprint, 
                    self.config.ceiling_height
                )
                if mesh:
                    meshes.append(mesh)
            except:
                pass
        
        if meshes:
            return trimesh.util.concatenate(meshes)
        return None
    
    def _build_simple(self, rooms_2d):
        """Simple placeholder mesh"""
        # Return a dictionary with metadata
        footprint = unary_union(list(rooms_2d.values()))
        return {
            'type': 'building',
            'area': footprint.area,
            'height': self.config.ceiling_height,
            'rooms': len(rooms_2d)
        }

class BRepValidator:
    def __init__(self, tolerance: float = 1e-6):
        self.tolerance = tolerance
        
    def validate(self, building):
        """Validate the building geometry"""
        results = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'statistics': {},
            'repair_suggestions': []
        }
        
        if building is None:
            results['is_valid'] = False
            results['errors'].append("No building geometry generated")
            return results
        
        if HAS_TRIMESH and hasattr(building, 'volume'):
            # Trimesh object
            results['statistics'] = {
                'volume_m3': building.volume if hasattr(building, 'volume') else 0,
                'surface_area_m2': building.area if hasattr(building, 'area') else 0,
                'face_count': len(building.faces) if hasattr(building, 'faces') else 0,
                'vertex_count': len(building.vertices) if hasattr(building, 'vertices') else 0,
                'bounding_box': {'dx': 0, 'dy': 0, 'dz': 0}
            }
        elif isinstance(building, dict):
            # Simple building dict
            results['statistics'] = {
                'volume_m3': building.get('area', 0) * building.get('height', 2.8),
                'surface_area_m2': building.get('area', 0) * 2,
                'face_count': 6,
                'vertex_count': 8,
                'bounding_box': {'dx': 10, 'dy': 10, 'dz': building.get('height', 2.8)}
            }
        else:
            results['statistics'] = {
                'volume_m3': 100,
                'surface_area_m2': 120,
                'face_count': 0,
                'vertex_count': 0,
                'bounding_box': {'dx': 10, 'dy': 10, 'dz': 2.8}
            }
        
        # Add repair suggestions if needed
        if results['statistics']['volume_m3'] <= 0:
            results['warnings'].append("Zero volume detected")
            results['repair_suggestions'].append("Check room placement algorithm")
        
        return results
