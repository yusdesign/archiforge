"""
Professional SVG floor plan generator - Working Version
"""
import math
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union

class SVGFloorPlanExporter:
    def __init__(self, width_mm: int = 420, height_mm: int = 297):
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        
    def export(self, rooms: Dict[str, Polygon], 
               adjacency_graph=None,
               add_dimensions: bool = True,
               add_labels: bool = True,
               add_hatching: bool = True) -> str:
        """Generate SVG floor plan"""
        
        # Get bounds
        all_rooms = unary_union(list(rooms.values()))
        bounds = all_rooms.bounds
        
        # Calculate scale to fit on page (with 50px margin)
        margin = 80
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
        svg_lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width_mm}mm" height="{self.height_mm}mm" viewBox="0 0 {self.width_mm} {self.height_mm}">')
        svg_lines.append('<defs>')
        svg_lines.append('<style>')
        svg_lines.append('.wall { stroke: #2c3e50; stroke-width: 2.5; fill: none; stroke-linecap: round; }')
        svg_lines.append('.wall-interior { stroke: #7f8c8d; stroke-width: 1.2; fill: none; }')
        svg_lines.append('.hatch { fill: #ecf0f1; stroke: none; }')
        svg_lines.append('.label { font-family: Arial, sans-serif; font-size: 11px; font-weight: bold; fill: #2c3e50; text-anchor: middle; }')
        svg_lines.append('.area { font-family: Arial, sans-serif; font-size: 9px; fill: #7f8c8d; text-anchor: middle; }')
        svg_lines.append('.dimension { stroke: #e74c3c; stroke-width: 1; fill: none; }')
        svg_lines.append('.dimension-text { font-family: Arial, sans-serif; font-size: 9px; fill: #e74c3c; text-anchor: middle; }')
        svg_lines.append('.door { stroke: #2c3e50; stroke-width: 1.5; fill: none; }')
        svg_lines.append('.door-swing { stroke: #95a5a6; stroke-width: 1; fill: none; stroke-dasharray: 4,3; }')
        svg_lines.append('.window { stroke: #3498db; stroke-width: 2; fill: none; }')
        svg_lines.append('</style>')
        svg_lines.append('</defs>')
        
        # Background
        svg_lines.append(f'<rect width="{self.width_mm}" height="{self.height_mm}" fill="#ffffff"/>')
        
        # Draw rooms
        room_colors = ['#ffcdd2', '#c8e6c9', '#bbdefb', '#fff9c4', '#e1bee7', '#b2dfdb', '#ffccbc']
        color_idx = 0
        
        for name, poly in rooms.items():
            if poly.is_valid and not poly.is_empty:
                # Get polygon points
                coords = list(poly.exterior.coords)
                points = []
                for x, y in coords:
                    sx = x * self.scale + self.offset_x
                    sy = y * self.scale + self.offset_y
                    points.append(f"{sx:.2f},{sy:.2f}")
                
                # Room fill
                svg_lines.append(f'<polygon points="{" ".join(points)}" fill="{room_colors[color_idx % len(room_colors)]}" opacity="0.4" stroke="none"/>')
                color_idx += 1
                
                # Walls
                for i in range(len(coords) - 1):
                    x1, y1 = coords[i]
                    x2, y2 = coords[i+1]
                    sx1 = x1 * self.scale + self.offset_x
                    sy1 = y1 * self.scale + self.offset_y
                    sx2 = x2 * self.scale + self.offset_x
                    sy2 = y2 * self.scale + self.offset_y
                    svg_lines.append(f'<line x1="{sx1:.2f}" y1="{sy1:.2f}" x2="{sx2:.2f}" y2="{sy2:.2f}" class="wall"/>')
                
                # Room label
                if add_labels:
                    cx = poly.centroid.x * self.scale + self.offset_x
                    cy = poly.centroid.y * self.scale + self.offset_y
                    svg_lines.append(f'<text x="{cx:.2f}" y="{cy-5:.2f}" class="label">{name.capitalize()}</text>')
                    svg_lines.append(f'<text x="{cx:.2f}" y="{cy+8:.2f}" class="area">{poly.area:.1f} m²</text>')
        
        # Add dimension lines
        if add_dimensions:
            bounds = all_rooms.bounds
            # Horizontal dimension
            y_dim = bounds[3] + 0.5
            x1 = bounds[0] * self.scale + self.offset_x
            x2 = bounds[2] * self.scale + self.offset_x
            y_line = y_dim * self.scale + self.offset_y
            
            svg_lines.append(f'<line x1="{x1:.2f}" y1="{y_line:.2f}" x2="{x2:.2f}" y2="{y_line:.2f}" class="dimension"/>')
            svg_lines.append(f'<line x1="{x1:.2f}" y1="{y_line-5:.2f}" x2="{x1:.2f}" y2="{y_line+5:.2f}" class="dimension"/>')
            svg_lines.append(f'<line x1="{x2:.2f}" y1="{y_line-5:.2f}" x2="{x2:.2f}" y2="{y_line+5:.2f}" class="dimension"/>')
            
            width_m = bounds[2] - bounds[0]
            svg_lines.append(f'<text x="{(x1+x2)/2:.2f}" y="{y_line+12:.2f}" class="dimension-text">{width_m:.1f} m</text>')
            
            # Vertical dimension
            x_dim = bounds[2] + 0.5
            y1 = bounds[1] * self.scale + self.offset_y
            y2 = bounds[3] * self.scale + self.offset_y
            x_line = x_dim * self.scale + self.offset_x
            
            svg_lines.append(f'<line x1="{x_line:.2f}" y1="{y1:.2f}" x2="{x_line:.2f}" y2="{y2:.2f}" class="dimension"/>')
            svg_lines.append(f'<line x1="{x_line-5:.2f}" y1="{y1:.2f}" x2="{x_line+5:.2f}" y2="{y1:.2f}" class="dimension"/>')
            svg_lines.append(f'<line x1="{x_line-5:.2f}" y1="{y2:.2f}" x2="{x_line+5:.2f}" y2="{y2:.2f}" class="dimension"/>')
            
            height_m = bounds[3] - bounds[1]
            svg_lines.append(f'<text x="{x_line+12:.2f}" y="{(y1+y2)/2:.2f}" class="dimension-text" transform="rotate(-90, {x_line+12:.2f}, {(y1+y2)/2:.2f})">{height_m:.1f} m</text>')
        
        # Title block
        svg_lines.append(f'<rect x="{self.width_mm-140}" y="{self.height_mm-55}" width="130" height="50" fill="white" stroke="#2c3e50" stroke-width="1"/>')
        svg_lines.append(f'<text x="{self.width_mm-75}" y="{self.height_mm-42}" text-anchor="middle" font-family="Arial" font-size="11" font-weight="bold" fill="#2c3e50">FLOOR PLAN</text>')
        svg_lines.append(f'<text x="{self.width_mm-75}" y="{self.height_mm-30}" text-anchor="middle" font-family="Arial" font-size="9" fill="#7f8c8d">{datetime.now().strftime("%Y-%m-%d")}</text>')
        svg_lines.append(f'<text x="{self.width_mm-75}" y="{self.height_mm-20}" text-anchor="middle" font-family="Arial" font-size="9" fill="#7f8c8d">Rooms: {len(rooms)}</text>')
        
        # North arrow
        north_x = 50
        north_y = 50
        svg_lines.append(f'<circle cx="{north_x}" cy="{north_y}" r="18" fill="white" stroke="#2c3e50" stroke-width="1"/>')
        svg_lines.append(f'<polygon points="{north_x},{north_y-12} {north_x-6},{north_y+4} {north_x},{north_y} {north_x+6},{north_y+4}" fill="#2c3e50"/>')
        svg_lines.append(f'<text x="{north_x}" y="{north_y-14}" text-anchor="middle" font-family="Arial" font-size="10" font-weight="bold" fill="#2c3e50">N</text>')
        
        # Scale bar
        bar_x = 50
        bar_y = self.height_mm - 40
        bar_length = 80
        svg_lines.append(f'<line x1="{bar_x}" y1="{bar_y}" x2="{bar_x+bar_length}" y2="{bar_y}" stroke="#2c3e50" stroke-width="2"/>')
        
        for i in range(5):
            tick_x = bar_x + i * bar_length / 4
            svg_lines.append(f'<line x1="{tick_x}" y1="{bar_y-4}" x2="{tick_x}" y2="{bar_y+4}" stroke="#2c3e50" stroke-width="1"/>')
            label_m = i * 2  # 2m segments
            svg_lines.append(f'<text x="{tick_x}" y="{bar_y-8}" text-anchor="middle" font-family="Arial" font-size="8" fill="#7f8c8d">{label_m}m</text>')
        
        svg_lines.append('</svg>')
        
        return '\n'.join(svg_lines)
