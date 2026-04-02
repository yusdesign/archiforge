"""
B-rep (Boundary Representation) construction and validation using trimesh
"""
import trimesh
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union
from dataclasses import dataclass

@dataclass
class BRepConfig:
    wall_thickness: float = 0.15
    floor_thickness: float = 0.20
    ceiling_height: float = 2.8
    foundation_depth: float = 0.5
    roof_overhang: float = 0.5
    material: str = "concrete"

class BRepBuilder:
    """Construct 3D meshes from 2D room polygons using trimesh"""
    
    def __init__(self, config: BRepConfig = None):
        self.config = config or BRepConfig()
        
    def build_building(self, rooms_2d: Dict[str, ShapelyPolygon],
                      add_roof: bool = True,
                      add_foundation: bool = True) -> trimesh.Trimesh:
        """Build complete 3D building mesh"""
        meshes = []
        
        # Foundation
        if add_foundation:
            foundation = self._build_foundation(rooms_2d)
            if foundation:
                meshes.append(foundation)
        
        # Floors
        floors = self._build_floors(rooms_2d)
        if floors:
            meshes.append(floors)
        
        # Walls
        walls = self._build_walls(rooms_2d)
        if walls:
            meshes.append(walls)
        
        # Roof
        if add_roof:
            roof = self._build_roof(rooms_2d)
            if roof:
                meshes.append(roof)
        
        if not meshes:
            return trimesh.Trimesh()
        
        return trimesh.util.concatenate(meshes)
    
    def _build_foundation(self, rooms_2d: Dict[str, ShapelyPolygon]) -> Optional[trimesh.Trimesh]:
        """Build foundation slab"""
        footprint = unary_union(list(rooms_2d.values()))
        return self._extrude_polygon(footprint, self.config.foundation_depth, -self.config.foundation_depth)
    
    def _build_floors(self, rooms_2d: Dict[str, ShapelyPolygon]) -> Optional[trimesh.Trimesh]:
        """Build floor slabs"""
        footprint = unary_union(list(rooms_2d.values()))
        return self._extrude_polygon(footprint, self.config.floor_thickness, 0)
    
    def _build_walls(self, rooms_2d: Dict[str, ShapelyPolygon]) -> Optional[trimesh.Trimesh]:
        """Build exterior walls"""
        footprint = unary_union(list(rooms_2d.values()))
        
        # Get exterior boundary and extrude
        wall_mesh = self._create_wall_from_polygon(footprint, self.config.wall_thickness, self.config.ceiling_height)
        return wall_mesh
    
    def _create_wall_from_polygon(self, polygon: ShapelyPolygon, thickness: float, height: float) -> Optional[trimesh.Trimesh]:
        """Create walls along polygon boundary"""
        meshes = []
        coords = list(polygon.exterior.coords)
        
        for i in range(len(coords)-1):
            p1 = coords[i]
            p2 = coords[i+1]
            
            # Create box for this wall segment
            length = np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
            if length < 0.01:
                continue
            
            # Create box centered at origin
            box = trimesh.primitives.Box(extents=[length, thickness, height])
            
            # Rotate to align with wall direction
            angle = np.arctan2(p2[1]-p1[1], p2[0]-p1[0])
            rotation = trimesh.transformations.rotation_matrix(angle, [0, 0, 1])
            box.apply_transform(rotation)
            
            # Position at midpoint
            center_x = (p1[0] + p2[0]) / 2
            center_y = (p1[1] + p2[1]) / 2
            translation = trimesh.transformations.translation_matrix([center_x, center_y, height/2])
            box.apply_transform(translation)
            
            meshes.append(box)
        
        if not meshes:
            return None
        return trimesh.util.concatenate(meshes)
    
    def _build_roof(self, rooms_2d: Dict[str, ShapelyPolygon]) -> Optional[trimesh.Trimesh]:
        """Build simple pitched roof"""
        footprint = unary_union(list(rooms_2d.values()))
        bounds = footprint.bounds
        width = bounds[2] - bounds[0]
        depth = bounds[3] - bounds[1]
        
        # Create a simple pyramid roof
        roof_height = width * 0.3
        
        # Vertices of roof
        x_center = (bounds[0] + bounds[2]) / 2
        y_center = (bounds[1] + bounds[3]) / 2
        
        # Create roof as a pyramid
        vertices = [
            [bounds[0] - self.config.roof_overhang, bounds[1] - self.config.roof_overhang, self.config.ceiling_height],
            [bounds[2] + self.config.roof_overhang, bounds[1] - self.config.roof_overhang, self.config.ceiling_height],
            [bounds[2] + self.config.roof_overhang, bounds[3] + self.config.roof_overhang, self.config.ceiling_height],
            [bounds[0] - self.config.roof_overhang, bounds[3] + self.config.roof_overhang, self.config.ceiling_height],
            [x_center, y_center, self.config.ceiling_height + roof_height]
        ]
        
        faces = [
            [0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4],  # Sides
            [0, 1, 2, 3]  # Base (optional)
        ]
        
        roof = trimesh.Trimesh(vertices=vertices, faces=faces)
        return roof
    
    def _extrude_polygon(self, polygon: ShapelyPolygon, height: float, z_offset: float = 0) -> Optional[trimesh.Trimesh]:
        """Extrude a shapely polygon to a 3D mesh"""
        from shapely.geometry import Polygon
        import trimesh.creation
        
        if polygon.is_empty:
            return None
        
        # Get boundary vertices
        coords = list(polygon.exterior.coords)
        vertices_2d = np.array(coords[:-1])  # Remove duplicate last point
        
        # Create bottom and top vertices
        bottom_vertices = np.hstack([vertices_2d, np.zeros((len(vertices_2d), 1)) + z_offset])
        top_vertices = np.hstack([vertices_2d, np.zeros((len(vertices_2d), 1)) + z_offset + height])
        
        # Combine vertices
        all_vertices = np.vstack([bottom_vertices, top_vertices])
        
        # Create faces (triangulated)
        n = len(vertices_2d)
        faces = []
        
        # Side faces
        for i in range(n):
            j = (i + 1) % n
            faces.append([i, j, j + n])
            faces.append([i, j + n, i + n])
        
        # Bottom face (triangulated)
        bottom_center = np.mean(bottom_vertices, axis=0)
        bottom_vertices_with_center = np.vstack([bottom_vertices, bottom_center])
        for i in range(n):
            j = (i + 1) % n
            faces.append([i, j, n + n])
        
        # Top face (triangulated)
        top_center = np.mean(top_vertices, axis=0)
        top_vertices_with_center = np.vstack([top_vertices, top_center])
        # Adjust indices for top faces
        for i in range(n):
            j = (i + 1) % n
            faces.append([i + n, j + n, n + n + 1])
        
        mesh = trimesh.Trimesh(vertices=all_vertices, faces=faces)
        return mesh

class BRepValidator:
    """Validate 3D mesh geometry"""
    
    def __init__(self, tolerance: float = 1e-6):
        self.tolerance = tolerance
        
    def validate(self, mesh: trimesh.Trimesh) -> Dict[str, Any]:
        """Comprehensive mesh validation"""
        results = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'statistics': {},
            'repair_suggestions': []
        }
        
        # Check if mesh is empty
        if mesh.is_empty:
            results['is_valid'] = False
            results['errors'].append("Empty mesh")
            return results
        
        # Check volume
        volume = mesh.volume
        if volume <= 0:
            results['is_valid'] = False
            results['errors'].append("Zero or negative volume")
        else:
            results['statistics']['volume_m3'] = volume
        
        # Check if watertight/manifold
        if not mesh.is_watertight:
            results['warnings'].append("Mesh is not watertight (has holes)")
            results['repair_suggestions'].append("Use trimesh.repair.fill_holes()")
        
        # Check for self-intersections
        if hasattr(mesh, 'process'):
            if mesh.process.check_intersections():
                results['warnings'].append("Self-intersections detected")
        
        # Statistics
        results['statistics'].update({
            'surface_area_m2': mesh.area,
            'face_count': len(mesh.faces),
            'vertex_count': len(mesh.vertices),
            'edge_count': len(mesh.edges),
            'bounding_box': {
                'dx': mesh.bounds[1][0] - mesh.bounds[0][0],
                'dy': mesh.bounds[1][1] - mesh.bounds[0][1],
                'dz': mesh.bounds[1][2] - mesh.bounds[0][2]
            }
        })
        
        # Check minimum thickness (approximate via bounding box)
        bbox = results['statistics']['bounding_box']
        min_thick = min(bbox['dx'], bbox['dy'], bbox['dz'])
        if min_thick < 0.05:
            results['warnings'].append(f"Minimum thickness {min_thick:.3f}m < 0.05m")
        
        return results
    
    def auto_repair(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """Attempt automatic repairs"""
        repaired = mesh.copy()
        
        # Fill holes
        if not repaired.is_watertight:
            repaired = trimesh.repair.fill_holes(repaired)
        
        # Remove duplicate vertices
        repaired.merge_vertices()
        
        # Remove degenerate faces
        repaired.remove_degenerate_faces()
        
        return repaired
