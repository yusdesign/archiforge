"""
B-rep (Boundary Representation) construction and validation
"""
import cadquery as cq
from cadquery import Workplane, Solid, Face, Shell
from typing import Dict, List, Tuple, Optional, Any
from shapely.geometry import Polygon as ShapelyPolygon
import numpy as np
from dataclasses import dataclass

@dataclass
class BRepConfig:
    wall_thickness: float = 0.15  # meters (150mm typical)
    floor_thickness: float = 0.20  # 200mm slab
    ceiling_height: float = 2.8  # meters
    foundation_depth: float = 0.5
    roof_overhang: float = 0.5
    material: str = "concrete"

class BRepBuilder:
    """Construct 3D solids from 2D room polygons"""
    
    def __init__(self, config: BRepConfig = None):
        self.config = config or BRepConfig()
        
    def build_building(self, rooms_2d: Dict[str, ShapelyPolygon],
                      add_roof: bool = True,
                      add_foundation: bool = True) -> cq.Solid:
        """
        Build complete 3D building from 2D room layout
        
        Returns:
            CadQuery Solid object
        """
        # Build each component
        foundation = self._build_foundation(rooms_2d) if add_foundation else None
        floors = self._build_floors(rooms_2d)
        walls = self._build_walls(rooms_2d)
        roof = self._build_roof(rooms_2d) if add_roof else None
        
        # Combine everything
        building = floors
        building = building.union(walls)
        
        if foundation:
            building = building.union(foundation)
        if roof:
            building = building.union(roof)
        
        return building.val()
    
    def _build_foundation(self, rooms_2d: Dict[str, ShapelyPolygon]) -> cq.Solid:
        """Build foundation slab"""
        # Union all room polygons
        from shapely.ops import unary_union
        footprint = unary_union(list(rooms_2d.values()))
        
        # Extrude to create foundation
        foundation = self._polygon_to_solid(footprint, 
                                           height=self.config.foundation_depth,
                                           offset_z=-self.config.foundation_depth)
        return foundation
    
    def _build_floors(self, rooms_2d: Dict[str, ShapelyPolygon]) -> cq.Solid:
        """Build floor slabs for each level"""
        from shapely.ops import unary_union
        footprint = unary_union(list(rooms_2d.values()))
        
        floor = self._polygon_to_solid(footprint,
                                      height=self.config.floor_thickness,
                                      offset_z=0)
        return floor
    
    def _build_walls(self, rooms_2d: Dict[str, ShapelyPolygon]) -> cq.Solid:
        """Build exterior and interior walls"""
        from shapely.ops import unary_union, polygonize
        from shapely.geometry import MultiLineString
        
        # Get exterior boundary
        footprint = unary_union(list(rooms_2d.values()))
        exterior_boundary = footprint.boundary
        
        # Get interior boundaries (between rooms)
        all_walls = []
        
        # Exterior walls
        exterior_wall = self._create_wall_from_polygon(footprint, 
                                                       offset=-self.config.wall_thickness/2,
                                                       is_exterior=True)
        all_walls.append(exterior_wall)
        
        # Interior walls (between adjacent rooms)
        room_names = list(rooms_2d.keys())
        for i in range(len(room_names)):
            for j in range(i+1, len(room_names)):
                poly_i = rooms_2d[room_names[i]]
                poly_j = rooms_2d[room_names[j]]
                
                # Check if they share a boundary
                intersection = poly_i.intersection(poly_j)
                if not intersection.is_empty and intersection.length > 0.1:
                    # Create wall along shared boundary
                    wall = self._create_wall_between_polygons(poly_i, poly_j)
                    if wall:
                        all_walls.append(wall)
        
        # Union all walls
        if all_walls:
            result = all_walls[0]
            for wall in all_walls[1:]:
                result = result.union(wall)
            return result
        return cq.Solid.makeBox(0, 0, 0)
    
    def _create_wall_from_polygon(self, polygon: ShapelyPolygon, 
                                  offset: float,
                                  is_exterior: bool = True) -> cq.Solid:
        """Create walls along polygon boundary"""
        walls = []
        coords = list(polygon.exterior.coords)
        
        for i in range(len(coords)-1):
            p1 = coords[i]
            p2 = coords[i+1]
            
            # Wall segment length
            length = np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
            
            # Create wall as box
            wall = cq.Solid.makeBox(length, 
                                   self.config.wall_thickness,
                                   self.config.ceiling_height)
            
            # Rotate and position
            angle = np.degrees(np.arctan2(p2[1]-p1[1], p2[0]-p1[0]))
            center_x = (p1[0] + p2[0]) / 2
            center_y = (p1[1] + p2[1]) / 2
            
            # Move to position
            wall = wall.move(cq.Vector(center_x, center_y, 0))
            wall = wall.rotate(cq.Vector(0,0,0), cq.Vector(0,0,1), angle)
            
            # Offset outward for exterior walls
            if is_exterior:
                normal_x = -(p2[1]-p1[1])  # Perpendicular
                normal_y = (p2[0]-p1[0])
                norm = np.sqrt(normal_x**2 + normal_y**2)
                if norm > 0:
                    normal_x /= norm
                    normal_y /= norm
                    wall = wall.translate(cq.Vector(normal_x * offset, 
                                                    normal_y * offset, 0))
            
            walls.append(wall)
        
        # Union all wall segments
        if walls:
            result = walls[0]
            for wall in walls[1:]:
                result = result.fuse(wall)
            return result
        return cq.Solid.makeBox(0, 0, 0)
    
    def _create_wall_between_polygons(self, poly1: ShapelyPolygon, 
                                     poly2: ShapelyPolygon) -> Optional[cq.Solid]:
        """Create wall along shared boundary between two rooms"""
        intersection = poly1.intersection(poly2)
        
        if intersection.is_empty or not hasattr(intersection, 'coords'):
            return None
        
        # Get shared edge coordinates
        coords = list(intersection.coords)
        if len(coords) < 2:
            return None
        
        p1 = coords[0]
        p2 = coords[1]
        
        length = np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
        
        # Create wall
        wall = cq.Solid.makeBox(length,
                               self.config.wall_thickness,
                               self.config.ceiling_height)
        
        # Position
        angle = np.degrees(np.arctan2(p2[1]-p1[1], p2[0]-p1[0]))
        center_x = (p1[0] + p2[0]) / 2
        center_y = (p1[1] + p2[1]) / 2
        
        wall = wall.move(cq.Vector(center_x, center_y, 0))
        wall = wall.rotate(cq.Vector(0,0,0), cq.Vector(0,0,1), angle)
        
        return wall
    
    def _build_roof(self, rooms_2d: Dict[str, ShapelyPolygon]) -> cq.Solid:
        """Build simple pitched roof"""
        from shapely.ops import unary_union
        footprint = unary_union(list(rooms_2d.values()))
        
        # Create roof as extruded triangle (simplified)
        bounds = footprint.bounds
        width = bounds[2] - bounds[0]
        depth = bounds[3] - bounds[1]
        
        # Roof pitch (30 degrees)
        pitch_height = width * 0.3
        
        # Create roof using loft
        base = cq.Workplane().rect(width + self.config.roof_overhang * 2,
                                   depth + self.config.roof_overhang * 2)
        
        # Ridge line
        ridge = cq.Workplane().rect(width * 0.2, depth).translate((0, 0, pitch_height))
        
        # Loft to create roof
        roof = base.loft(ridge, combine=False)
        
        # Position roof
        roof = roof.translate((bounds[0] + width/2, bounds[1] + depth/2, self.config.ceiling_height))
        
        return roof.val()
    
    def _polygon_to_solid(self, polygon: ShapelyPolygon, 
                         height: float, 
                         offset_z: float = 0) -> cq.Solid:
        """Convert Shapely polygon to CadQuery solid by extrusion"""
        # Get polygon vertices
        coords = list(polygon.exterior.coords)
        
        # Create wire
        wire = cq.Workplane().polyline(coords).close()
        
        # Extrude
        solid = wire.extrude(height)
        
        # Move to correct Z height
        solid = solid.translate((0, 0, offset_z))
        
        return solid.val()
    
    def export_to_step(self, solid: cq.Solid, filename: str):
        """Export B-rep to STEP file for CAD interoperability"""
        cq.exporters.export(solid, filename)
    
    def export_to_stl(self, solid: cq.Solid, filename: str):
        """Export to STL for 3D printing"""
        cq.exporters.export(solid, filename)

class BRepValidator:
    """Validate B-rep geometry for constructability"""
    
    def __init__(self, tolerance: float = 1e-6):
        self.tolerance = tolerance
        
    def validate(self, solid: cq.Solid) -> Dict[str, Any]:
        """
        Comprehensive B-rep validation
        
        Returns:
            Dictionary with validation results and repair suggestions
        """
        results = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'statistics': {},
            'repair_suggestions': []
        }
        
        # Check 1: Manifold geometry
        if not self._check_manifold(solid):
            results['is_valid'] = False
            results['errors'].append("Non-manifold geometry detected")
            results['repair_suggestions'].append("Use cq.Solid.fix() to repair")
        
        # Check 2: Self-intersections
        intersections = self._check_self_intersections(solid)
        if intersections:
            results['is_valid'] = False
            results['errors'].append(f"Found {len(intersections)} self-intersections")
            results['repair_suggestions'].append("Apply Boolean union with tolerance")
        
        # Check 3: Minimum thickness
        min_thick = self._check_min_thickness(solid)
        if min_thick < 0.05:  # Less than 5cm
            results['warnings'].append(f"Minimum thickness {min_thick:.3f}m < 0.05m")
            results['repair_suggestions'].append("Increase wall thickness")
        
        # Check 4: Volume statistics
        volume = solid.Volume()
        if volume <= 0:
            results['is_valid'] = False
            results['errors'].append("Zero or negative volume")
        
        results['statistics'] = {
            'volume_m3': volume,
            'surface_area_m2': solid.SurfaceArea(),
            'bounding_box': self._get_bounding_box(solid),
            'face_count': len(solid.Faces()),
            'edge_count': len(solid.Edges()),
            'vertex_count': len(solid.Vertices())
        }
        
        # Check 5: Planarity of faces
        non_planar = self._check_face_planarity(solid)
        if non_planar:
            results['warnings'].append(f"Found {len(non_planar)} non-planar faces")
        
        return results
    
    def _check_manifold(self, solid: cq.Solid) -> bool:
        """Check if solid is manifold (every edge has exactly 2 faces)"""
        try:
            # CadQuery internal check
            return solid.isValid()
        except:
            return False
    
    def _check_self_intersections(self, solid: cq.Solid) -> List:
        """Detect self-intersections in the solid"""
        intersections = []
        
        # Check each face against others
        faces = list(solid.Faces())
        for i in range(len(faces)):
            for j in range(i+1, len(faces)):
                if faces[i].intersect(faces[j]).Area() > self.tolerance:
                    intersections.append((i, j))
        
        return intersections
    
    def _check_min_thickness(self, solid: cq.Solid) -> float:
        """Estimate minimum thickness using sampling"""
        # Sample points on surface and compute distance to opposite face
        # Simplified: use bounding box smallest dimension
        bbox = self._get_bounding_box(solid)
        min_thickness = min(bbox['dx'], bbox['dy'], bbox['dz'])
        
        return min_thickness
    
    def _check_face_planarity(self, solid: cq.Solid) -> List[int]:
        """Check if all faces are planar"""
        non_planar = []
        
        for i, face in enumerate(solid.Faces()):
            # Check if all vertices lie on same plane
            vertices = list(face.Vertices())
            if len(vertices) >= 3:
                # Compute plane from first 3 vertices
                p1 = vertices[0].Center()
                p2 = vertices[1].Center()
                p3 = vertices[2].Center()
                
                # Normal vector
                v1 = p2 - p1
                v2 = p3 - p1
                normal = v1.cross(v2)
                
                # Check all other vertices
                for v in vertices[3:]:
                    v_rel = v.Center() - p1
                    distance = abs(v_rel.dot(normal) / normal.Length)
                    if distance > self.tolerance:
                        non_planar.append(i)
                        break
        
        return non_planar
    
    def _get_bounding_box(self, solid: cq.Solid) -> Dict[str, float]:
        """Get bounding box dimensions"""
        bbox = solid.BoundingBox()
        return {
            'xmin': bbox.xmin,
            'xmax': bbox.xmax,
            'ymin': bbox.ymin,
            'ymax': bbox.ymax,
            'zmin': bbox.zmin,
            'zmax': bbox.zmax,
            'dx': bbox.xmax - bbox.xmin,
            'dy': bbox.ymax - bbox.ymin,
            'dz': bbox.zmax - bbox.zmin
        }
    
    def auto_repair(self, solid: cq.Solid) -> cq.Solid:
        """Attempt automatic repairs on invalid geometry"""
        repaired = solid
        
        # Fix 1: Remove duplicate vertices
        repaired = repaired.clean()
        
        # Fix 2: Defeature (remove small artifacts)
        repaired = repaired.defeature()
        
        # Fix 3: Sew faces if needed
        # (CadQuery specific)
        
        return repaired
