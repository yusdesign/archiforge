"""
Interactive Architectural Generator Web App
Using Template-Based Layout Solver (Most Reliable)
"""
import streamlit as st
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
from shapely.ops import unary_union
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from io import BytesIO
from datetime import datetime
import random

# Import ONLY the template solver (most reliable)
from generator.layout_template import RoomLayoutSolverTemplate, LayoutConfig
from generator.grammar import ArchitecturalGrammar, GrammarOptimizer
from generator.constraints import RoomConstraint
from generator.brep import BRepBuilder, BRepValidator, BRepConfig
from generator.svg_export import SVGFloorPlanExporter

# Page configuration
st.set_page_config(
    page_title="Architectural Generator",
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
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .success-badge {
        background-color: #10b981;
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        display: inline-block;
    }
    .error-badge {
        background-color: #ef4444;
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        display: inline-block;
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
if 'validation' not in st.session_state:
    st.session_state.validation = None
if 'svg_string' not in st.session_state:
    st.session_state.svg_string = None
if 'random_seed' not in st.session_state:
    st.session_state.random_seed = random.randint(0, 9999)

# Sidebar
with st.sidebar:
    st.markdown("## 🎛️ Design Controls")
    
    # Random seed control
    st.markdown("### 🎲 Randomization")
    col1, col2 = st.columns(2)
    if col1.button("🎲 New Random", use_container_width=True):
        st.session_state.random_seed = random.randint(0, 9999)
        st.session_state.generated = False
        st.rerun()
    col2.write(f"Seed: `{st.session_state.random_seed}`")
    
    # Room selection
    st.markdown("### 📐 Room Configuration")
    available_rooms = ["Living", "Kitchen", "Bedroom", "Bathroom", "Dining", "Study", "Hallway"]
    
    selected_rooms = st.multiselect(
        "Select rooms",
        available_rooms,
        default=["Living", "Kitchen", "Bedroom", "Bathroom"]
    )
    
    # Building parameters
    st.markdown("### 🏢 Building")
    col1, col2 = st.columns(2)
    building_width = col1.number_input("Width (m)", 8.0, 20.0, 12.0)
    building_height = col2.number_input("Height (m)", 8.0, 20.0, 12.0)
    
    wall_thickness = st.slider("Wall thickness (cm)", 10, 30, 15) / 100.0
    ceiling_height = st.slider("Ceiling height (m)", 2.4, 4.0, 2.8)
    
    # Generation button
    st.markdown("---")
    generate_btn = st.button("🚀 Generate", use_container_width=True, type="primary")

# Main content
st.markdown('<div class="main-header">🏗️ AI Architectural Generator</div>', unsafe_allow_html=True)
st.markdown("*Generate readable floor plans using architectural templates*")

# Generate on button click
if generate_btn and selected_rooms:
    with st.spinner("Generating floor plan..."):
        try:
            # Set random seed
            random.seed(st.session_state.random_seed)
            np.random.seed(st.session_state.random_seed)
            
            # Generate adjacency graph using grammar
            grammar = ArchitecturalGrammar()
            adj_graph = grammar.generate_adjacency([r.lower() for r in selected_rooms])
            
            # Create layout config
            layout_config = LayoutConfig(
                building_width=building_width,
                building_height=building_height,
                wall_thickness=wall_thickness,
                random_seed=st.session_state.random_seed
            )
            
            # Use template solver (MOST RELIABLE)
            layout_solver = RoomLayoutSolverTemplate(layout_config)
            rooms_2d = layout_solver.solve(adj_graph, None)
            
            # Build B-rep for validation
            brep_config = BRepConfig(
                wall_thickness=wall_thickness,
                ceiling_height=ceiling_height
            )
            brep_builder = BRepBuilder(brep_config)
            building_solid = brep_builder.build_building(rooms_2d, add_roof=True)
            
            # Validate
            validator = BRepValidator()
            validation_result = validator.validate(building_solid)
            
            # Generate SVG
            exporter = SVGFloorPlanExporter(width_mm=420, height_mm=297)
            svg_string = exporter.export(
                rooms_2d, 
                adj_graph,
                add_dimensions=True,
                add_labels=True,
                add_hatching=True
            )
            
            # Store in session state
            st.session_state.generated = True
            st.session_state.rooms = rooms_2d
            st.session_state.adj_graph = adj_graph
            st.session_state.validation = validation_result
            st.session_state.svg_string = svg_string
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.session_state.generated = False

# Display results
if st.session_state.generated and st.session_state.rooms:
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    total_area = sum(p.area for p in st.session_state.rooms.values() if p.is_valid)
    volume = st.session_state.validation.get('statistics', {}).get('volume_m3', 0)
    
    col1.metric("🏠 Rooms", len(st.session_state.rooms))
    col2.metric("📐 Area", f"{total_area:.0f} m²")
    col3.metric("📦 Volume", f"{volume:.0f} m³")
    col4.metric("🎲 Seed", st.session_state.random_seed)
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["📐 Floor Plan", "📄 SVG Export", "📊 Data"])
    
    with tab1:
        # Matplotlib floor plan
        fig, ax = plt.subplots(figsize=(12, 10))
        
        colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99', '#ff99cc', '#99ffcc', '#ffff99']
        
        for i, (name, poly) in enumerate(st.session_state.rooms.items()):
            if poly.is_valid:
                x, y = poly.exterior.xy
                ax.fill(x, y, alpha=0.5, color=colors[i % len(colors)], label=name.capitalize())
                cx, cy = poly.centroid.x, poly.centroid.y
                ax.text(cx, cy, name.capitalize(), ha='center', va='center', fontsize=11, fontweight='bold')
        
        # Draw adjacency
        pos = {n: (p.centroid.x, p.centroid.y) for n, p in st.session_state.rooms.items() if p.is_valid}
        if pos:
            nx.draw(st.session_state.adj_graph, pos, ax=ax, node_size=50, node_color='red', edge_color='gray', alpha=0.6)
        
        ax.set_xlim(-1, building_width + 1)
        ax.set_ylim(-1, building_height + 1)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        if len(st.session_state.rooms) <= 10:
            ax.legend(loc='upper left', bbox_to_anchor=(1, 1))
        
        st.pyplot(fig)
        plt.close(fig)
    
    with tab2:
        st.markdown("### SVG Floor Plan Export")
        st.markdown("*Professional vector graphics - scalable, print-ready*")
        
        if st.session_state.svg_string:
            import base64
            b64 = base64.b64encode(st.session_state.svg_string.encode()).decode()
            svg_html = f'<div style="background:#f5f5f5; padding:20px; border-radius:10px;"><img src="data:image/svg+xml;base64,{b64}" style="width:100%; height:auto; border:1px solid #ddd;"></div>'
            st.markdown(svg_html, unsafe_allow_html=True)
            
            st.download_button(
                label="📥 Download SVG File",
                data=st.session_state.svg_string,
                file_name=f"floor_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.svg",
                mime="image/svg+xml",
                use_container_width=True
            )
    
    with tab3:
        st.markdown("#### Room Areas")
        area_df = pd.DataFrame([
            {"Room": name, "Area (m²)": round(p.area, 1)} 
            for name, p in st.session_state.rooms.items() if p.is_valid
        ])
        st.dataframe(area_df, use_container_width=True)
        
        st.markdown("#### Validation")
        stats = st.session_state.validation.get('statistics', {})
        if stats:
            st.json(stats)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: gray;">
    🏗️ Built with Streamlit, NetworkX, Shapely | Template-Based Layout
</div>
""", unsafe_allow_html=True)
