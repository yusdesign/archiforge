"""
Professional SVG floor plan generator
"""
import svgwrite
from svgwrite import mm
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Polygon, LineString, Point, MultiLineString
from shapely.ops import unary_union
import numpy as np
from datetime import datetime
import math

class SVGFloorPlanExporter:
    def __init__(self, width_mm: int = 420, height_mm: int = 297):  # A3 landscape
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.dwg = None
        self.scale = 1.0  # Will calculate from building bounds
        
    def export(self, rooms: Dict[str, Polygon], 
               adjacency_graph=None,
               filename: str = "floor_plan.svg",
               add_dimensions: bool = True,
               add_labels: bool = True,
               add_hatching: bool = True) -> str:
        """Generate SVG floor plan"""
        
        # Calculate bounds and scale
        bounds = self._get_bounds(rooms)
        self.scale = self._calculate_scale(bounds)
        
        # Create SVG drawing
        self.dwg = svgwrite.Drawing(filename, 
                                   size=(f"{self.width_mm}mm", f"{self.height_mm}mm"),
                                   profile='full')
        
        # Add defs (patterns, markers, etc.)
        self._add_defs()
        
        # Set background
        self.dwg.add(self.dwg.rect(insert=(0, 0),
                                   size=(f"{self.width_mm}mm", f"{self.height_mm}mm"),
                                   fill='white'))
        
        # Calculate offset to center drawing
        offset_x = (self.width_mm / self.scale - (bounds[2] - bounds[0])) / 2 - bounds[0]
        offset_y = (self.height_mm / self.scale - (bounds[3] - bounds[1])) / 2 - bounds[1]
        
        # Draw layers (back to front)
        
        # 1. Grid (optional, for reference)
        self._draw_grid(bounds, offset_x, offset_y)
        
        # 2. Floor hatching
        if add_hatching:
            self._draw_floor_hatching(rooms, offset_x, offset_y)
        
        # 3. Walls (thick outline)
        self._draw_walls(rooms, offset_x, offset_y)
        
        # 4. Doors (with swing arcs)
        doors = self._detect_doors(rooms, adjacency_graph)
        self._draw_doors(doors, offset_x, offset_y)
        
        # 5. Windows
        windows = self._detect_windows(rooms)
        self._draw_windows(windows, offset_x, offset_y)
        
        # 6. Room labels
        if add_labels:
            self._draw_room_labels(rooms, offset_x, offset_y)
        
        # 7. Dimensions
        if add_dimensions:
            self._draw_dimensions(bounds, rooms, offset_x, offset_y)
        
        # 8. Title block
        self._draw_title_block(rooms)
        
        # 9. North arrow
        self._draw_north_arrow()
        
        # 10. Scale bar
        self._draw_scale_bar()
        
        return self.dwg.tostring()
    
    def _get_bounds(self, rooms: Dict[str, Polygon]) -> Tuple[float, float, float, float]:
        """Get overall bounds of all rooms"""
        all_rooms = unary_union(list(rooms.values()))
        return all_rooms.bounds
    
    def _calculate_scale(self, bounds: Tuple[float, float, float, float]) -> float:
        """Calculate scale to fit on page with margins"""
        building_width = bounds[2] - bounds[0]
        building_height = bounds[3] - bounds[1]
        
        # Add 20% margin
        margin = 1.2
        width_scale = (self.width_mm - 40) / (building_width * margin)
        height_scale = (self.height_mm - 40) / (building_height * margin)
        
        return min(width_scale, height_scale)
    
    def _world_to_svg(self, x: float, y: float, offset_x: float, offset_y: float) -> Tuple[float, float]:
        """Convert world coordinates to SVG coordinates"""
        svg_x = (x + offset_x) * self.scale
        svg_y = (y + offset_y) * self.scale
        return (svg_x, svg_y)
    
    def _add_defs(self):
        """Add SVG definitions (patterns, markers)"""
        # Hatch pattern for walls
        hatch = self.dwg.pattern(id='wall_hatch', 
                                 patternUnits='userSpaceOnUse',
                                 size=(4, 4))
        hatch.add(self.dwg.line(start=(0, 0), end=(4, 4), stroke='#999', stroke_width=0.5))
        hatch.add(self.dwg.line(start=(0, 2), end=(4, 2), stroke='#999', stroke_width=0.5))
        self.dwg.defs.add(hatch)
        
        # Arrow marker for dimensions
        marker = self.dwg.marker(id='arrow', 
                                 markerUnits='strokeWidth',
                                 markerWidth=10, 
                                 markerHeight=7,
                                 refX=10, 
                                 refY=3.5,
                                 orient='auto')
        marker.add(self.dwg.polygon([(0, 0), (10, 3.5), (0, 7)], fill='black'))
        self.dwg.defs.add(marker)
        
        # Door swing arc marker
        door_marker = self.dwg.marker(id='door_swing',
                                      markerUnits='strokeWidth',
                                      markerWidth=6,
                                      markerHeight=6,
                                      refX=0,
                                      refY=0,
                                      orient='auto')
        self.dwg.defs.add(door_marker)
    
    def _draw_grid(self, bounds: Tuple[float, float, float, float], 
                   offset_x: float, offset_y: float):
        """Draw reference grid (1m spacing)"""
        start_x = math.floor(bounds[0])
        end_x = math.ceil(bounds[2])
        start_y = math.floor(bounds[1])
        end_y = math.ceil(bounds[3])
        
        grid_group = self.dwg.g(stroke='#e0e0e0', stroke_width=0.3)
        
        for x in np.arange(start_x, end_x + 1, 1):
            x1, y1 = self._world_to_svg(x, start_y, offset_x, offset_y)
            x2, y2 = self._world_to_svg(x, end_y, offset_x, offset_y)
            grid_group.add(self.dwg.line(start=(x1, y1), end=(x2, y2)))
        
        for y in np.arange(start_y, end_y + 1, 1):
            x1, y1 = self._world_to_svg(start_x, y, offset_x, offset_y)
            x2, y2 = self._world_to_svg(end_x, y, offset_x, offset_y)
            grid_group.add(self.dwg.line(start=(x1, y1), end=(x2, y2)))
        
        self.dwg.add(grid_group)
    
    def _draw_floor_hatching(self, rooms: Dict[str, Polygon], 
                             offset_x: float, offset_y: float):
        """Draw floor area with light hatching"""
        hatch_group = self.dwg.g(fill='url(#wall_hatch)', opacity=0.3)
        
        for room_name, polygon in rooms.items():
            if polygon.is_valid:
                points = []
                for x, y in polygon.exterior.coords:
                    sx, sy = self._world_to_svg(x, y, offset_x, offset_y)
                    points.append((sx, sy))
                
                # Add room fill
                self.dwg.add(self.dwg.polygon(points, fill='#f5f5f5', stroke='none'))
                
                # Add hatch pattern for non-living areas
                if 'bathroom' in room_name.lower() or 'kitchen' in room_name.lower():
                    hatch_group.add(self.dwg.polygon(points, fill='url(#wall_hatch)'))
        
        self.dwg.add(hatch_group)
    
    def _draw_walls(self, rooms: Dict[str, Polygon], 
                    offset_x: float, offset_y: float):
        """Draw walls with thick lines"""
        wall_group = self.dwg.g(stroke='#333', stroke_width=2.5, fill='none', stroke_linecap='round')
        
        for polygon in rooms.values():
            if polygon.is_valid:
                # Draw exterior walls
                coords = list(polygon.exterior.coords)
                for i in range(len(coords) - 1):
                    x1, y1 = self._world_to_svg(coords[i][0], coords[i][1], offset_x, offset_y)
                    x2, y2 = self._world_to_svg(coords[i+1][0], coords[i+1][1], offset_x, offset_y)
                    wall_group.add(self.dwg.line(start=(x1, y1), end=(x2, y2)))
                
                # Draw interior walls (thinner)
                for interior in polygon.interiors:
                    coords = list(interior.coords)
                    for i in range(len(coords) - 1):
                        x1, y1 = self._world_to_svg(coords[i][0], coords[i][1], offset_x, offset_y)
                        x2, y2 = self._world_to_svg(coords[i+1][0], coords[i+1][1], offset_x, offset_y)
                        wall_group.add(self.dwg.line(start=(x1, y1), end=(x2, y2), stroke_width=1.5))
        
        self.dwg.add(wall_group)
    
    def _detect_doors(self, rooms: Dict[str, Polygon], adjacency_graph) -> List[Dict]:
        """Detect door positions between adjacent rooms"""
        doors = []
        
        if not adjacency_graph:
            return doors
        
        for u, v in adjacency_graph.edges():
            if u in rooms and v in rooms:
                poly_u = rooms[u]
                poly_v = rooms[v]
                
                # Find shared wall
                intersection = poly_u.intersection(poly_v)
                
                if not intersection.is_empty:
                    if intersection.geom_type == 'LineString':
                        coords = list(intersection.coords)
                        if len(coords) >= 2:
                            # Door at center of shared wall
                            x1, y1 = coords[0]
                            x2, y2 = coords[1]
                            center_x = (x1 + x2) / 2
                            center_y = (y1 + y2) / 2
                            
                            # Calculate wall angle
                            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
                            
                            doors.append({
                                'x': center_x,
                                'y': center_y,
                                'angle': angle,
                                'width': 0.9,
                                'room_a': u,
                                'room_b': v
                            })
        
        return doors
    
    def _draw_doors(self, doors: List[Dict], offset_x: float, offset_y: float):
        """Draw doors with swing arcs"""
        door_group = self.dwg.g(stroke='#555', stroke_width=1.5, fill='none')
        
        for door in doors:
            x, y = self._world_to_svg(door['x'], door['y'], offset_x, offset_y)
            angle = door['angle']
            width = door['width'] * self.scale
            
            # Draw door leaf (line at 90° to wall)
            perp_angle = angle + 90
            rad = math.radians(perp_angle)
            dx = math.cos(rad) * width
            dy = math.sin(rad) * width
            
            door_group.add(self.dwg.line(start=(x, y), end=(x + dx, y + dy), stroke_width=2))
            
            # Draw door swing arc (90°)
            swing_angle_start = angle - 90
            swing_angle_end = angle
            
            import svgwrite.path
            path = svgwrite.path.Path(stroke='#888', stroke_width=1, fill='none', stroke_dasharray='4,2')
            
            # Arc path (simplified)
            radius = width
            start_rad = math.radians(swing_angle_start)
            end_rad = math.radians(swing_angle_end)
            
            path.push(f"M {x + math.cos(start_rad) * radius} {y + math.sin(start_rad) * radius}")
            path.push_arc((x, y), radius, radius, 0, False, True,
                         x + math.cos(end_rad) * radius, y + math.sin(end_rad) * radius)
            
            door_group.add(path)
        
        self.dwg.add(door_group)
    
    def _detect_windows(self, rooms: Dict[str, Polygon]) -> List[Dict]:
        """Detect window positions on exterior walls"""
        windows = []
        
        # Get exterior boundary
        all_rooms = unary_union(list(rooms.values()))
        exterior = all_rooms.boundary
        
        # Sample points along exterior walls for window placement
        if exterior.geom_type == 'LineString':
            walls = [exterior]
        elif exterior.geom_type == 'MultiLineString':
            walls = list(exterior.geoms)
        else:
            walls = []
        
        for wall in walls:
            coords = list(wall.coords)
            if len(coords) >= 2:
                # Place window in center of each wall segment
                x1, y1 = coords[0]
                x2, y2 = coords[1]
                length = math.sqrt((x2-x1)**2 + (y2-y1)**2)
                
                if length > 2.0:  # Only place windows on walls > 2m
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
                    
                    windows.append({
                        'x': center_x,
                        'y': center_y,
                        'angle': angle,
                        'width': min(1.5, length * 0.6),
                        'height': 1.2
                    })
        
        return windows
    
    def _draw_windows(self, windows: List[Dict], offset_x: float, offset_y: float):
        """Draw window symbols (three parallel lines)"""
        window_group = self.dwg.g(stroke='#4682b4', stroke_width=1.2, fill='none')
        
        for window in windows:
            x, y = self._world_to_svg(window['x'], window['y'], offset_x, offset_y)
            angle = window['angle']
            width = window['width'] * self.scale
            perp_angle = angle + 90
            
            # Calculate offsets
            rad = math.radians(perp_angle)
            dx = math.cos(rad) * 0.1 * self.scale
            dy = math.sin(rad) * 0.1 * self.scale
            
            # Draw three parallel lines
            for offset in [-0.15, 0, 0.15]:
                offset_rad = math.radians(angle + 90)
                ox = math.cos(offset_rad) * offset * self.scale
                oy = math.sin(offset_rad) * offset * self.scale
                
                x1 = x - width/2 * math.cos(math.radians(angle)) + ox
                y1 = y - width/2 * math.sin(math.radians(angle)) + oy
                x2 = x + width/2 * math.cos(math.radians(angle)) + ox
                y2 = y + width/2 * math.sin(math.radians(angle)) + oy
                
                window_group.add(self.dwg.line(start=(x1, y1), end=(x2, y2)))
        
        self.dwg.add(window_group)
    
    def _draw_room_labels(self, rooms: Dict[str, Polygon], 
                          offset_x: float, offset_y: float):
        """Draw room names and areas"""
        label_group = self.dwg.g(font_family='Arial', font_size=12, fill='#333', text_anchor='middle')
        
        for room_name, polygon in rooms.items():
            if polygon.is_valid:
                centroid = polygon.centroid
                cx, cy = self._world_to_svg(centroid.x, centroid.y, offset_x, offset_y)
                
                # Room name
                label_group.add(self.dwg.text(room_name.capitalize(), 
                                             insert=(cx, cy - 5),
                                             font_weight='bold'))
                
                # Area
                area = polygon.area
                label_group.add(self.dwg.text(f"{area:.1f} m²", 
                                             insert=(cx, cy + 10),
                                             font_size=9,
                                             fill='#666'))
        
        self.dwg.add(label_group)
    
    def _draw_dimensions(self, bounds: Tuple[float, float, float, float],
                        rooms: Dict[str, Polygon], offset_x: float, offset_y: float):
        """Draw dimension lines"""
        dim_group = self.dwg.g(stroke='#e74c3c', stroke_width=1, fill='none', font_size=10)
        
        # Horizontal dimension
        y_pos = bounds[3] + 0.5
        x1, y1 = self._world_to_svg(bounds[0], y_pos, offset_x, offset_y)
        x2, y2 = self._world_to_svg(bounds[2], y_pos, offset_x, offset_y)
        
        dim_group.add(self.dwg.line(start=(x1, y1), end=(x2, y2)))
        dim_group.add(self.dwg.line(start=(x1, y1 - 5), end=(x1, y1 + 5)))
        dim_group.add(self.dwg.line(start=(x2, y2 - 5), end=(x2, y2 + 5)))
        
        width_m = bounds[2] - bounds[0]
        dim_group.add(self.dwg.text(f"{width_m:.1f} m", 
                                   insert=((x1 + x2)/2, y1 + 15),
                                   text_anchor='middle',
                                   fill='#e74c3c'))
        
        # Vertical dimension
        x_pos = bounds[2] + 0.5
        x1, y1 = self._world_to_svg(x_pos, bounds[1], offset_x, offset_y)
        x2, y2 = self._world_to_svg(x_pos, bounds[3], offset_x, offset_y)
        
        dim_group.add(self.dwg.line(start=(x1, y1), end=(x2, y2)))
        dim_group.add(self.dwg.line(start=(x1 - 5, y1), end=(x1 + 5, y1)))
        dim_group.add(self.dwg.line(start=(x2 - 5, y2), end=(x2 + 5, y2)))
        
        height_m = bounds[3] - bounds[1]
        dim_group.add(self.dwg.text(f"{height_m:.1f} m", 
                                   insert=(x1 + 15, (y1 + y2)/2),
                                   text_anchor='middle',
                                   fill='#e74c3c'))
        
        self.dwg.add(dim_group)
    
    def _draw_title_block(self, rooms: Dict[str, Polygon]):
        """Draw title block with project info"""
        title_group = self.dwg.g(font_family='Arial', font_size=10, fill='#333')
        
        # Title block rectangle
        tb_x = self.width_mm - 140
        tb_y = self.height_mm - 60
        title_group.add(self.dwg.rect(insert=(tb_x, tb_y), 
                                     size=(130, 50),
                                     fill='white',
                                     stroke='#333',
                                     stroke_width=1))
        
        # Project title
        title_group.add(self.dwg.text("ARCHITECTURAL FLOOR PLAN", 
                                     insert=(tb_x + 5, tb_y + 15),
                                     font_weight='bold',
                                     font_size=11))
        
        # Date
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        title_group.add(self.dwg.text(f"Date: {date_str}", 
                                     insert=(tb_x + 5, tb_y + 30),
                                     font_size=9))
        
        # Room count
        title_group.add(self.dwg.text(f"Rooms: {len(rooms)}", 
                                     insert=(tb_x + 5, tb_y + 42),
                                     font_size=9))
        
        self.dwg.add(title_group)
    
    def _draw_north_arrow(self):
        """Draw north arrow"""
        north_group = self.dwg.g()
        
        # Position top-right corner
        x = self.width_mm - 60
        y = 40
        size = 20
        
        # Arrow circle
        north_group.add(self.dwg.circle(center=(x, y), r=size, fill='white', stroke='#333', stroke_width=1))
        
        # Arrow
        north_group.add(self.dwg.polygon([(x, y - size + 5), (x - 5, y + 5), (x, y + 2), (x + 5, y + 5)], 
                                        fill='#333'))
        
        # 'N' label
        north_group.add(self.dwg.text("N", insert=(x - 3, y - size + 8), 
                                     font_size=10, font_weight='bold', fill='#333'))
        
        self.dwg.add(north_group)
    
    def _draw_scale_bar(self):
        """Draw scale bar"""
        scale_group = self.dwg.g(font_family='Arial', font_size=9, fill='#333')
        
        # Position bottom-left
        x = 40
        y = self.height_mm - 40
        bar_length = 100  # pixels
        
        # Calculate meter equivalent (assume 1m = 50px at current scale)
        meters_per_pixel = 1 / 50
        total_meters = bar_length * meters_per_pixel
        
        scale_group.add(self.dwg.line(start=(x, y), end=(x + bar_length, y), stroke='#333', stroke_width=2))
        
        # Tick marks
        for i in range(0, 5):
            tick_x = x + (i * bar_length / 4)
            scale_group.add(self.dwg.line(start=(tick_x, y - 5), end=(tick_x, y + 5), stroke='#333', stroke_width=1))
            
            # Label
            label_m = i * (total_meters / 4)
            scale_group.add(self.dwg.text(f"{label_m:.1f}m", insert=(tick_x, y - 8), text_anchor='middle'))
        
        self.dwg.add(scale_group)
