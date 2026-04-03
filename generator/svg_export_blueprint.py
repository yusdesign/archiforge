"""
Professional SVG Blueprint Exporter with doors, windows, entrance
"""
import math
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union

class SVGBlueprintExporter:
    def __init__(self, width_mm: int = 594, height_mm: int = 420):  # A2 landscape
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        
    def export(self, rooms: Dict[str, Polygon], 
               adjacency_graph,
               room_sizes: Dict[str, float] = None,
               show_grid: bool = True,
               show_dimensions: bool = True,
               building_width: float = 14.0,
               building_height: float = 12.0) -> str:
        """Generate professional SVG blueprint"""
        
        # Calculate bounds
        all_rooms = unary_union(list(rooms.values()))
        bounds = all_rooms.bounds
        
        # Calculate scale
        margin = 60
        building_w = bounds[2] - bounds[0]
        building_h = bounds[3] - bounds[1]
        
        scale_x = (self.width_mm - margin * 2) / building_w if building_w > 0 else 1
        scale_y = (self.height_mm - margin * 2) / building_h if building_h > 0 else 1
        self.scale = min(scale_x, scale_y)
        
        # Center on page
        self.offset_x = margin + (self.width_mm - margin * 2 - building_w * self.scale) / 2 - bounds[0] * self.scale
        self.offset_y = margin + (self.height_mm - margin * 2 - building_h * self.scale) / 2 - bounds[1] * self.scale
        
        # Build SVG
        svg_lines = []
        
        # SVG header
        svg_lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width_mm}mm" height="{self.height_mm}mm" viewBox="0 0 {self.width_mm} {self.height_mm}" style="background: #faf8f0;">')
        svg_lines.append('<defs>')
        svg_lines.append('<style>')
        svg_lines.append('.wall { stroke: #1a1a2e; stroke-width: 2.5; fill: none; stroke-linecap: round; }')
        svg_lines.append('.wall-interior { stroke: #1a1a2e; stroke-width: 1.2; fill: none; }')
        svg_lines.append('.room-fill { fill: #f0f0f0; stroke: none; }')
        svg_lines.append('.dimension { stroke: #e74c3c; stroke-width: 0.8; fill: none; }')
        svg_lines.append('.dimension-text { font-family: "Courier New", monospace; font-size: 8px; fill: #e74c3c; text-anchor: middle; }')
        svg_lines.append('.grid { stroke: #d0d0d0; stroke-width: 0.3; }')
        svg_lines.append('.door { stroke: #2c3e50; stroke-width: 1.5; fill: none; }')
        svg_lines.append('.door-swing { stroke: #2c3e50; stroke-width: 0.8; fill: none; stroke-dasharray: 3,3; }')
        svg_lines.append('.window { stroke: #3498db; stroke-width: 2; fill: #d6eaf8; }')
        svg_lines.append('.entrance { stroke: #27ae60; stroke-width: 2; fill: #2ecc71; }')
        svg_lines.append('.title { font-family: "Courier New", monospace; font-size: 14px; font-weight: bold; fill: #1a1a2e; }')
        svg_lines.append('.subtitle { font-family: "Courier New", monospace; font-size: 10px; fill: #7f8c8d; }')
        svg_lines.append('</style>')
        svg_lines.append('</defs>')
        
        # Background (parchment/blueprint color)
        svg_lines.append(f'<rect width="{self.width_mm}" height="{self.height_mm}" fill="#faf8f0"/>')
        
        # Grid
        if show_grid:
            grid_group = svg_lines
            for x in range(0, int(building_w) + 1):
                sx = x * self.scale + self.offset_x
                if 0 <= sx <= self.width_mm:
                    svg_lines.append(f'<line x1="{sx:.2f}" y1="{margin:.2f}" x2="{sx:.2f}" y2="{self.height_mm - margin:.2f}" class="grid"/>')
            for y in range(0, int(building_h) + 1):
                sy = y * self.scale + self.offset_y
                if 0 <= sy <= self.height_mm:
                    svg_lines.append(f'<line x1="{margin:.2f}" y1="{sy:.2f}" x2="{self.width_mm - margin:.2f}" y2="{sy:.2f}" class="grid"/>')
        
        # Draw rooms with light fill
        room_colors = ['#ffcdd2', '#c8e6c9', '#bbdefb', '#fff9c4', '#e1bee7', '#b2dfdb', '#ffccbc']
        color_idx = 0
        
        for name, poly in rooms.items():
            if poly.is_valid and not poly.is_empty:
                coords = list(poly.exterior.coords)
                points = []
                for x, y in coords:
                    sx = x * self.scale + self.offset_x
                    sy = y * self.scale + self.offset_y
                    points.append(f"{sx:.2f},{sy:.2f}")
                
                # Room fill
                svg_lines.append(f'<polygon points="{" ".join(points)}" fill="{room_colors[color_idx % len(room_colors)]}" opacity="0.3" stroke="none"/>')
                color_idx += 1
        
        # Draw walls
        for name, poly in rooms.items():
            if poly.is_valid:
                coords = list(poly.exterior.coords)
                for i in range(len(coords) - 1):
                    x1, y1 = coords[i]
                    x2, y2 = coords[i+1]
                    sx1 = x1 * self.scale + self.offset_x
                    sy1 = y1 * self.scale + self.offset_y
                    sx2 = x2 * self.scale + self.offset_x
                    sy2 = y2 * self.scale + self.offset_y
                    svg_lines.append(f'<line x1="{sx1:.2f}" y1="{sy1:.2f}" x2="{sx2:.2f}" y2="{sy2:.2f}" class="wall"/>')
        
        # Add doors between rooms
        if adjacency_graph:
            for u, v in adjacency_graph.edges():
                if u in rooms and v in rooms:
                    self._add_door(svg_lines, rooms[u], rooms[v])
        
        # Add entrance (front door)
        self._add_entrance(svg_lines, rooms, building_width, building_height)
        
        # Add windows on exterior walls
        self._add_windows(svg_lines, rooms, building_width, building_height)
        
        # Add dimensions
        if show_dimensions:
            self._add_dimensions(svg_lines, bounds)
        
        # Title block
        svg_lines.append(f'<rect x="{self.width_mm - 160}" y="{self.height_mm - 65}" width="150" height="55" fill="white" stroke="#1a1a2e" stroke-width="1.5"/>')
        svg_lines.append(f'<text x="{self.width_mm - 85}" y="{self.height_mm - 48}" text-anchor="middle" class="title">FLOOR PLAN</text>')
        svg_lines.append(f'<text x="{self.width_mm - 85}" y="{self.height_mm - 35}" text-anchor="middle" class="subtitle">{datetime.now().strftime("%Y-%m-%d")}</text>')
        svg_lines.append(f'<text x="{self.width_mm - 85}" y="{self.height_mm - 22}" text-anchor="middle" class="subtitle">Scale: 1:50</text>')
        
        # North arrow
        north_x = 50
        north_y = 50
        svg_lines.append(f'<circle cx="{north_x}" cy="{north_y}" r="15" fill="white" stroke="#1a1a2e" stroke-width="1"/>')
        svg_lines.append(f'<polygon points="{north_x},{north_y-10} {north_x-5},{north_y+3} {north_x},{north_y} {north_x+5},{north_y+3}" fill="#1a1a2e"/>')
        svg_lines.append(f'<text x="{north_x}" y="{north_y-12}" text-anchor="middle" font-family="Courier New" font-size="9" font-weight="bold" fill="#1a1a2e">N</text>')
        
        # Scale bar
        bar_x = 50
        bar_y = self.height_mm - 40
        bar_length = 100
        svg_lines.append(f'<line x1="{bar_x}" y1="{bar_y}" x2="{bar_x + bar_length}" y2="{bar_y}" stroke="#1a1a2e" stroke-width="1.5"/>')
        
        for i in range(5):
            tick_x = bar_x + i * bar_length / 4
            svg_lines.append(f'<line x1="{tick_x}" y1="{bar_y-3}" x2="{tick_x}" y2="{bar_y+3}" stroke="#1a1a2e" stroke-width="0.8"/>')
            label_m = i * 2
            svg_lines.append(f'<text x="{tick_x}" y="{bar_y-6}" text-anchor="middle" font-family="Courier New" font-size="7" fill="#1a1a2e">{label_m}m</text>')
        
        svg_lines.append('</svg>')
        
        return '\n'.join(svg_lines)
    
    def _add_door(self, svg_lines, poly1: Polygon, poly2: Polygon):
        """Add door symbol between two rooms"""
        intersection = poly1.intersection(poly2)
        if not intersection.is_empty and intersection.geom_type == 'LineString':
            coords = list(intersection.coords)
            if len(coords) >= 2:
                x1, y1 = coords[0]
                x2, y2 = coords[1]
                
                # Door position (center of shared wall)
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
                
                sx = cx * self.scale + self.offset_x
                sy = cy * self.scale + self.offset_y
                door_width = 0.9 * self.scale
                
                # Door perpendicular
                perp_angle = angle + 90
                rad = math.radians(perp_angle)
                dx = math.cos(rad) * door_width
                dy = math.sin(rad) * door_width
                
                svg_lines.append(f'<line x1="{sx:.2f}" y1="{sy:.2f}" x2="{sx + dx:.2f}" y2="{sy + dy:.2f}" class="door"/>')
                
                # Door swing arc (90 degrees)
                import svgwrite.path
                radius = door_width
                start_rad = math.radians(angle - 90)
                end_rad = math.radians(angle)
                
                arc_points = []
                for t in [0.25, 0.5, 0.75, 1]:
                    rad_t = start_rad + (end_rad - start_rad) * t
                    arc_x = sx + math.cos(rad_t) * radius
                    arc_y = sy + math.sin(rad_t) * radius
                    arc_points.append(f"{arc_x:.2f},{arc_y:.2f}")
                
                svg_lines.append(f'<polyline points="{" ".join(arc_points)}" class="door-swing"/>')
    
    def _add_entrance(self, svg_lines, rooms: Dict[str, Polygon], width: float, height: float):
        """Add entrance marker on exterior wall"""
        # Find front wall (bottom wall)
        entrance_x = width / 2
        entrance_y = 0
        
        sx = entrance_x * self.scale + self.offset_x
        sy = entrance_y * self.scale + self.offset_y
        
        # Entrance door (double doors)
        door_width = 1.2 * self.scale
        svg_lines.append(f'<line x1="{sx - door_width/2:.2f}" y1="{sy:.2f}" x2="{sx + door_width/2:.2f}" y2="{sy:.2f}" class="entrance"/>')
        svg_lines.append(f'<circle cx="{sx - door_width/4:.2f}" cy="{sy:.2f}" r="2" fill="#27ae60"/>')
        svg_lines.append(f'<circle cx="{sx + door_width/4:.2f}" cy="{sy:.2f}" r="2" fill="#27ae60"/>')
    
    def _add_windows(self, svg_lines, rooms: Dict[str, Polygon], width: float, height: float):
        """Add window symbols on exterior walls"""
        # Simple: add windows on exterior walls at regular intervals
        for x in [2, 4, 6, 8, 10]:
            if x < width:
                sx = x * self.scale + self.offset_x
                sy_top = 0.5 * self.scale + self.offset_y
                sy_bottom = (height - 0.5) * self.scale + self.offset_y
                
                # Top wall windows
                svg_lines.append(f'<rect x="{sx - 1:.2f}" y="{sy_top:.2f}" width="2" height="0.8" class="window"/>')
                # Bottom wall windows
                svg_lines.append(f'<rect x="{sx - 1:.2f}" y="{sy_bottom - 0.8:.2f}" width="2" height="0.8" class="window"/>')
    
    def _add_dimensions(self, svg_lines, bounds: Tuple[float, float, float, float]):
        """Add dimension lines"""
        # Horizontal dimension
        y_dim = bounds[3] + 0.5
        x1 = bounds[0] * self.scale + self.offset_x
        x2 = bounds[2] * self.scale + self.offset_x
        y_line = y_dim * self.scale + self.offset_y
        
        svg_lines.append(f'<line x1="{x1:.2f}" y1="{y_line:.2f}" x2="{x2:.2f}" y2="{y_line:.2f}" class="dimension"/>')
        svg_lines.append(f'<line x1="{x1:.2f}" y1="{y_line-4:.2f}" x2="{x1:.2f}" y2="{y_line+4:.2f}" class="dimension"/>')
        svg_lines.append(f'<line x1="{x2:.2f}" y1="{y_line-4:.2f}" x2="{x2:.2f}" y2="{y_line+4:.2f}" class="dimension"/>')
        
        width_m = bounds[2] - bounds[0]
        svg_lines.append(f'<text x="{(x1+x2)/2:.2f}" y="{y_line+10:.2f}" class="dimension-text">{width_m:.1f} m</text>')
        
        # Vertical dimension
        x_dim = bounds[2] + 0.5
        y1 = bounds[1] * self.scale + self.offset_y
        y2 = bounds[3] * self.scale + self.offset_y
        x_line = x_dim * self.scale + self.offset_x
        
        svg_lines.append(f'<line x1="{x_line:.2f}" y1="{y1:.2f}" x2="{x_line:.2f}" y2="{y2:.2f}" class="dimension"/>')
        svg_lines.append(f'<line x1="{x_line-4:.2f}" y1="{y1:.2f}" x2="{x_line+4:.2f}" y2="{y1:.2f}" class="dimension"/>')
        svg_lines.append(f'<line x1="{x_line-4:.2f}" y1="{y2:.2f}" x2="{x_line+4:.2f}" y2="{y2:.2f}" class="dimension"/>')
        
        height_m = bounds[3] - bounds[1]
        svg_lines.append(f'<text x="{x_line+10:.2f}" y="{(y1+y2)/2:.2f}" class="dimension-text" transform="rotate(-90, {x_line+10:.2f}, {(y1+y2)/2:.2f})">{height_m:.1f} m</text>')
