"""
Procedural layout generation from adjacency graphs
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Polygon, Point, box, LineString
from shapely.ops import polygonize, unary_union
from shapely.affinity import scale, translate
import networkx as nx
from dataclasses import dataclass
import random

@dataclass
class LayoutConfig:
    """User-controllable layout parameters"""
    building_width: float = 12.0  # meters
    building_height: float = 12.0
    grid_resolution: float = 0.1  # meters per grid cell
    wall_thickness: float = 0.15
    min_room_area: float = 4.0
    max_aspect_ratio: float = 2.5
    hallway_width: float = 1.2
    prefer_square_rooms: bool = True
    seed: int = 42

class ProceduralLayoutSolver:
    """Convert adjacency graph to 2D room polygons using force-directed layout"""
    
    def __init__(self, config: LayoutConfig = None):
        self.config = config or LayoutConfig()
        random.seed(self.config.seed)
        np.random.seed(self.config.seed)
        
    def solve(self, adjacency_graph: nx.Graph,
              room_sizes: Dict[str, Tuple[float, float]] = None) -> Dict[str, Polygon]:
        """
        Generate room polygons from adjacency graph
        
        Returns:
            Dictionary mapping room name to Shapely Polygon
        """
        # Step 1: Initial graph layout (force-directed)
        pos = self._graph_layout(adjacency_graph)
        
        # Step 2: Assign room sizes
        if room_sizes is None:
            room_sizes = self._estimate_room_sizes(adjacency_graph)
        
        # Step 3: Generate polygons using Voronoi-like partitioning
        rooms = self._voronoi_partitioning(adjacency_graph, pos, room_sizes)
        
        # Step 4: Optimize shapes
        rooms = self._optimize_shapes(rooms, adjacency_graph)
        
        # Step 5: Ensure connectivity
        rooms = self._enforce_adjacency(rooms, adjacency_graph)
        
        # Step 6: Scale to fit building envelope
        rooms = self._fit_to_envelope(rooms)
        
        return rooms
    
    def _graph_layout(self, g: nx.Graph) -> Dict[str, Tuple[float, float]]:
        """Force-directed layout for initial room positions"""
        # Use Fruchterman-Reingold for organic placement
        pos = nx.spring_layout(g, k=2.0, iterations=100, seed=self.config.seed)
        
        # Scale to building dimensions
        pos = {node: (x * self.config.building_width, 
                      y * self.config.building_height) 
               for node, (x, y) in pos.items()}
        return pos
    
    def _estimate_room_sizes(self, g: nx.Graph) -> Dict[str, Tuple[float, float]]:
        """Estimate room dimensions based on degree and type"""
        sizes = {}
        
        for node in g.nodes:
            degree = g.degree(node)
            room_type = g.nodes[node].get('type', 'living')
            
            # Base area based on room type
            base_areas = {
                'living': 20.0,
                'kitchen': 12.0,
                'bedroom': 14.0,
                'bathroom': 6.0,
                'hallway': 4.0,
                'dining': 12.0,
                'study': 10.0
            }
            
            area = base_areas.get(str(room_type).lower(), 12.0)
            
            # Adjust for connectivity (more connections = larger)
            area *= (1 + degree * 0.1)
            
            # Constrain to reasonable bounds
            area = np.clip(area, self.config.min_room_area, 40.0)
            
            # Calculate dimensions (prefer square if configured)
            if self.config.prefer_square_rooms:
                side = np.sqrt(area)
                width = height = side
            else:
                # Random aspect ratio
                aspect = np.random.uniform(0.7, 1.4)
                width = np.sqrt(area * aspect)
                height = area / width
            
            sizes[node] = (width, height)
        
        return sizes
    
    def _voronoi_partitioning(self, g: nx.Graph, pos: Dict, 
                               sizes: Dict) -> Dict[str, Polygon]:
        """Generate rooms using weighted Voronoi diagram"""
        from scipy.spatial import Voronoi
        
        # Generate points for each room
        points = []
        room_order = []
        for room, (x, y) in pos.items():
            points.append([x, y])
            room_order.append(room)
        
        points = np.array(points)
        
        # Compute Voronoi
        vor = Voronoi(points)
        
        # Assign Voronoi regions to rooms
        rooms = {}
        for i, room in enumerate(room_order):
            region_idx = vor.point_region[i]
            region = vor.regions[region_idx]
            
            if -1 not in region and region:
                # Convert to polygon
                vertices = [vor.vertices[v] for v in region]
                poly = Polygon(vertices)
                
                if poly.is_valid and poly.area > 0:
                    # Adjust size to target area
                    target_area = sizes[room][0] * sizes[room][1]
                    if poly.area > 0:
                        scale_factor = np.sqrt(target_area / poly.area)
                        poly = scale(poly, xfact=scale_factor, yfact=scale_factor, origin='center')
                    
                    rooms[room] = poly
        
        return rooms
    
    def _optimize_shapes(self, rooms: Dict[str, Polygon], 
                         g: nx.Graph) -> Dict[str, Polygon]:
        """Optimize room shapes to be more rectangular"""
        optimized = {}
        
        for room, poly in rooms.items():
            # Get bounding box
            bounds = poly.bounds
            bbox = box(*bounds)
            
            # Check if room should be rectangular
            if self.config.prefer_square_rooms:
                # Use bounding box
                optimized[room] = bbox
            else:
                # Keep original but simplify
                simplified = poly.simplify(0.2, preserve_topology=True)
                if simplified.is_valid and simplified.area > 0:
                    optimized[room] = simplified
                else:
                    optimized[room] = bbox
        
        return optimized
    
    def _enforce_adjacency(self, rooms: Dict[str, Polygon], 
                          g: nx.Graph) -> Dict[str, Polygon]:
        """Ensure adjacent rooms actually touch"""
        for u, v in g.edges():
            if u in rooms and v in rooms:
                poly_u = rooms[u]
                poly_v = rooms[v]
                
                # Check if they already touch
                if poly_u.distance(poly_v) > 0.01:
                    # Move them closer
                    centroid_u = poly_u.centroid
                    centroid_v = poly_v.centroid
                    
                    # Direction to move
                    direction = np.array([centroid_v.x - centroid_u.x, 
                                         centroid_v.y - centroid_u.y])
                    if np.linalg.norm(direction) > 0:
                        direction /= np.linalg.norm(direction)
                    
                    # Shift towards each other
                    shift_distance = poly_u.distance(poly_v) / 2
                    rooms[u] = translate(poly_u, 
                                        xoff=direction[0] * shift_distance,
                                        yoff=direction[1] * shift_distance)
                    rooms[v] = translate(poly_v,
                                        xoff=-direction[0] * shift_distance,
                                        yoff=-direction[1] * shift_distance)
        
        return rooms
    
    def _fit_to_envelope(self, rooms: Dict[str, Polygon]) -> Dict[str, Polygon]:
        """Scale and translate rooms to fit within building envelope"""
        # Get all rooms
        all_rooms = unary_union(list(rooms.values()))
        envelope = box(0, 0, self.config.building_width, self.config.building_height)
        
        # Center the layout
        centroid = all_rooms.centroid
        envelope_center = envelope.centroid
        
        dx = envelope_center.x - centroid.x
        dy = envelope_center.y - centroid.y
        
        translated = {name: translate(poly, xoff=dx, yoff=dy) 
                     for name, poly in rooms.items()}
        
        # Scale if needed
        all_translated = unary_union(list(translated.values()))
        if not envelope.contains(all_translated):
            # Scale down to fit
            scale_factor = min(
                envelope.width / all_translated.bounds[2] - all_translated.bounds[0],
                envelope.height / all_translated.bounds[3] - all_translated.bounds[1]
            ) * 0.9
            
            scaled = {name: scale(poly, xfact=scale_factor, yfact=scale_factor,
                                  origin='center') 
                     for name, poly in translated.items()}
            return scaled
        
        return translated

class RoomOptimizer:
    """Additional room shape optimization"""
    
    @staticmethod
    def make_convex(rooms: Dict[str, Polygon]) -> Dict[str, Polygon]:
        """Convert rooms to convex hull (simplifies but may lose shape)"""
        return {name: poly.convex_hull for name, poly in rooms.items()}
    
    @staticmethod
    def add_doors(rooms: Dict[str, Polygon], 
                  adjacency: nx.Graph) -> List[Tuple[str, str, Point]]:
        """Add door positions between adjacent rooms"""
        doors = []
        
        for u, v in adjacency.edges():
            if u in rooms and v in rooms:
                # Find intersecting wall segment
                intersection = rooms[u].intersection(rooms[v])
                if not intersection.is_empty:
                    # Place door at midpoint of shared wall
                    if isinstance(intersection, LineString):
                        midpoint = intersection.interpolate(0.5, normalized=True)
                    else:
                        midpoint = intersection.centroid
                    
                    doors.append((u, v, midpoint))
        
        return doors
