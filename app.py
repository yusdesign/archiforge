"""
Professional Architectural Blueprint Generator
- No hallway forced
- Room legend instead of labels on rooms
- Doors, windows, entrance markers
- Proper SVG blueprint styling
"""
import streamlit as st
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, box, Point, LineString
from shapely.ops import unary_union
import plotly.graph_objects as go
import pandas as pd
from io import BytesIO
from datetime import datetime
import random
import math

# Import generator modules
from generator.layout_kdtree import RoomLayoutSolverKDTree, LayoutConfig
from generator.grammar import ArchitecturalGrammar, GrammarOptimizer
from generator.svg_export_blueprint import SVGBlueprintExporter

# Page configuration
st.set_page_config(
    page_title="Architectural Blueprint Generator",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        background: linear-gradient(90deg, #1a365d 0%, #2b6cb0 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #1a365d 0%, #2b6cb0 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .blueprint-note {
        background-color: #1a365d;
        color: white;
        padding: 1rem;
        border-radius: 10px;
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'generated' not in st.session_state:
    st.session_state.generated = False
if 'rooms' not in st.session_state:
    st.session_state.rooms = None
if 'adj_graph' not in st.session_state:
    st.session_state.adj_graph = None
if 'svg_string' not in st.session_state:
    st.session_state.svg_string = None
if 'random_seed' not in st.session_state:
    st.session_state.random_seed = random.randint(0, 9999)

# Sidebar
with st.sidebar:
    st.markdown("## 🎛️ Blueprint Controls")
    
    # Random seed control
    st.markdown("### 🎲 Randomization")
    col1, col2 = st.columns(2)
    if col1.button("🎲 New Seed", use_container_width=True):
        st.session_state.random_seed = random.randint(0, 9999)
        st.session_state.generated = False
        st.rerun()
    col2.write(f"Seed: `{st.session_state.random_seed}`")
    
    # Room selection
    st.markdown("### 📐 Room Configuration")
    available_rooms = ["Living", "Kitchen", "Bedroom", "Bathroom", "Dining", "Study", "Master Bedroom"]
    
    selected_rooms = st.multiselect(
        "Select rooms",
        available_rooms,
        default=["Living", "Kitchen", "Bedroom", "Bathroom"]
    )
    
    # Room size customization
    st.markdown("### 📏 Room Sizes (m²)")
    room_sizes = {}
    for room in selected_rooms:
        default_size = {
            "Living": 25, "Kitchen": 12, "Bedroom": 14, "Bathroom": 6,
            "Dining": 12, "Study": 10, "Master Bedroom": 20
        }.get(room, 12)
        room_sizes[room] = st.number_input(f"{room}", 4, 50, default_size, key=f"size_{room}")
    
    # Building parameters
    st.markdown("### 🏢 Building")
    col1, col2 = st.columns(2)
    building_width = col1.number_input("Width (m)", 8.0, 25.0, 14.0)
    building_height = col2.number_input("Height (m)", 8.0, 25.0, 12.0)
    
    # Blueprint options
    st.markdown("### 📋 Blueprint Options")
    show_grid = st.checkbox("Show Grid", value=True)
    show_dimensions = st.checkbox("Show Dimensions", value=True)
    
    # Generation button
    st.markdown("---")
    generate_btn = st.button("🏗️ Generate Blueprint", use_container_width=True, type="primary")

# Main content
st.markdown('<div class="main-header">🏗️ Architectural Blueprint Generator</div>', unsafe_allow_html=True)
st.markdown("*Professional floor plans with doors, windows, and dimension lines*")

if generate_btn and selected_rooms:
    with st.spinner("Generating blueprint..."):
        try:
            random.seed(st.session_state.random_seed)
            np.random.seed(st.session_state.random_seed)
            
            # Generate adjacency graph
            grammar = ArchitecturalGrammar()
            adj_graph = grammar.generate_adjacency([r.lower() for r in selected_rooms])
            
            # Create layout config (NO FORCED HALLWAY)
            layout_config = LayoutConfig(
                building_width=building_width,
                building_height=building_height,
                wall_thickness=0.15,
                random_seed=st.session_state.random_seed
            )
            
            # Use template solver
            layout_solver = RoomLayoutSolverKDTree(layout_config)
            user_room_sizes = {}
            for room in selected_rooms:
                user_room_sizes[room] = room_sizes.get(room, 12)  # from sidebar number inputs
                
            rooms_2d = layout_solver.solve(adj_graph, room_sizes)
            
            # Generate professional SVG blueprint
            exporter = SVGBlueprintExporter(width_mm=594, height_mm=420)  # A2 size
            svg_string = exporter.export(
                rooms_2d,
                adj_graph,
                room_sizes=room_sizes,
                show_grid=show_grid,
                show_dimensions=show_dimensions,
                building_width=building_width,
                building_height=building_height
            )
            
            # Store
            st.session_state.generated = True
            st.session_state.rooms = rooms_2d
            st.session_state.adj_graph = adj_graph
            st.session_state.svg_string = svg_string
            st.session_state.room_sizes = room_sizes
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.session_state.generated = False

# Display results
if st.session_state.generated and st.session_state.svg_string:
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    total_area = sum(st.session_state.room_sizes.values())
    
    col1.metric("🏠 Rooms", len(st.session_state.room_sizes))
    col2.metric("📐 Total Area", f"{total_area:.0f} m²")
    col3.metric("🎲 Seed", st.session_state.random_seed)
    
    # Room legend
    with st.expander("📋 Room Legend", expanded=True):
        legend_cols = st.columns(min(4, len(st.session_state.room_sizes)))
        colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#ffeaa7', '#dfe6e9', '#74b9ff']
        for i, (room, area) in enumerate(st.session_state.room_sizes.items()):
            col = legend_cols[i % len(legend_cols)]
            col.markdown(f"""
            <div style="display: flex; align-items: center; margin: 5px 0;">
                <div style="width: 20px; height: 20px; background: {colors[i % len(colors)]}; margin-right: 10px; border: 1px solid #333;"></div>
                <span><b>{room}</b>: {area} m² ({area * 10.764:.0f} ft²)</span>
            </div>
            """, unsafe_allow_html=True)
    
    # SVG Blueprint display
    st.markdown("### 📐 Floor Plan Blueprint")
    
    import base64
    b64 = base64.b64encode(st.session_state.svg_string.encode()).decode()
    svg_html = f'''
    <div style="background: #f5f5f5; padding: 20px; border-radius: 10px; border: 1px solid #ddd;">
        <img src="data:image/svg+xml;base64,{b64}" style="width: 100%; height: auto; border: 1px solid #333; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
    </div>
    '''
    st.markdown(svg_html, unsafe_allow_html=True)
    
    # Download buttons
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="📥 Download SVG Blueprint",
            data=st.session_state.svg_string,
            file_name=f"blueprint_{datetime.now().strftime('%Y%m%d_%H%M%S')}.svg",
            mime="image/svg+xml",
            use_container_width=True
        )
    
    with col2:
        # PDF download (via SVG converted)
        st.info("💡 SVG files can be opened in Illustrator, AutoCAD, or any web browser")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: gray; font-size: 12px;">
    🏗️ Professional Blueprint Generator | Doors 🚪 | Windows 🪟 | Dimensions 📏 | Grid 🔲
</div>
""", unsafe_allow_html=True)
