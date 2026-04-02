"""
Interactive Architectural Generator Web App
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
from io import BytesIO  # Changed from StringIO to BytesIO
import base64
from datetime import datetime

# Import generator modules
from generator.grammar import ArchitecturalGrammar, GrammarOptimizer, RoomType
from generator.layout import ProceduralLayoutSolver, LayoutConfig
from generator.constraints import ConstraintSolver, RoomConstraint
from generator.brep import BRepBuilder, BRepValidator, BRepConfig

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
if 'brep_valid' not in st.session_state:
    st.session_state.brep_valid = None

# Sidebar - User Controls
with st.sidebar:
    st.markdown("## 🎛️ Design Controls")
    
    # Room selection
    st.markdown("### 📐 Room Configuration")
    available_rooms = ["Living", "Kitchen", "Bedroom", "Bathroom", "Dining", "Study", "Hallway"]
    
    selected_rooms = st.multiselect(
        "Select rooms to include",
        available_rooms,
        default=["Living", "Kitchen", "Bedroom", "Bathroom"]
    )
    
    # Room sizes
    st.markdown("### 📏 Room Constraints")
    room_constraints = {}
    for room in selected_rooms:
        with st.expander(f"{room} Settings"):
            col1, col2 = st.columns(2)
            min_area = col1.number_input(f"Min area ({room})", 4.0, 30.0, 12.0, key=f"min_{room}")
            max_area = col2.number_input(f"Max area ({room})", 8.0, 50.0, 25.0, key=f"max_{room}")
            aspect = st.slider(f"Aspect ratio ({room})", 0.5, 2.0, 1.0, key=f"aspect_{room}")
            
            room_constraints[room.lower()] = RoomConstraint(
                name=room.lower(),
                min_area=min_area,
                max_area=max_area,
                preferred_ratio=aspect
            )
    
    # Building parameters
    st.markdown("### 🏢 Building Parameters")
    col1, col2 = st.columns(2)
    building_width = col1.number_input("Width (m)", 8.0, 30.0, 15.0)
    building_height = col2.number_input("Height (m)", 8.0, 30.0, 15.0)
    
    wall_thickness = st.slider("Wall thickness (cm)", 10, 30, 15) / 100.0
    ceiling_height = st.slider("Ceiling height (m)", 2.4, 4.0, 2.8)

    # Door settings
    st.markdown("### 🚪 Door Configuration")
    col1, col2 = st.columns(2)
    door_width = col1.slider("Door width (m)", 0.7, 1.2, 0.9)
    door_height = col2.slider("Door height (m)", 1.8, 2.4, 2.1)

    door_types = st.radio("Door type", ["Single", "Double", "Sliding"], horizontal=True)

    # Window settings
    st.markdown("### 🪟 Window Configuration")
    col1, col2 = st.columns(2)
    window_width = col1.slider("Window width (m)", 0.8, 2.0, 1.2)
    window_height = col2.slider("Window height (m)", 0.8, 1.5, 1.0)

    # Update brep config
    brep_config = BRepConfig(
        wall_thickness=wall_thickness,
        ceiling_height=ceiling_height,
        door_width=door_width,
        door_height=door_height,
        window_width=window_width,
        window_height=window_height
    )
    
    # Generation button
    st.markdown("---")
    generate_btn = st.button("🚀 Generate Architecture", use_container_width=True, type="primary")

# Main content area
st.markdown('<div class="main-header">🏗️ AI Architectural Generator</div>', unsafe_allow_html=True)
st.markdown("*Generate novel, buildable floor plans with constraint satisfaction and B-rep validation*")

if generate_btn and selected_rooms:
    with st.spinner("Generating architecture..."):
        try:
            # Step 1: Generate adjacency graph using grammar
            grammar = ArchitecturalGrammar()
            adj_graph = grammar.generate_adjacency([r.lower() for r in selected_rooms])
            
            # Optimize graph
            adj_graph = GrammarOptimizer.minimize_cycles(adj_graph)
            adj_graph = GrammarOptimizer.add_circulation(adj_graph)
            
            # Step 2: Solve layout
            layout_config = LayoutConfig(
                building_width=building_width,
                building_height=building_height,
                wall_thickness=wall_thickness,
                prefer_square_rooms=True
            )
            layout_solver = ProceduralLayoutSolver(layout_config)
            
            rooms_2d = layout_solver.solve(adj_graph, None)
            
            # Step 3: Build B-rep
            brep_config = BRepConfig(
                wall_thickness=wall_thickness,
                ceiling_height=ceiling_height
            )
            brep_builder = BRepBuilder(brep_config)
            building_solid = brep_builder.build_building(rooms_2d, add_roof=True)
            
            # Step 4: Validate
            validator = BRepValidator()
            validation_result = validator.validate(building_solid)
            
            # Store in session state
            st.session_state.generated = True
            st.session_state.rooms = rooms_2d
            st.session_state.adj_graph = adj_graph
            st.session_state.validation = validation_result
            st.session_state.building_solid = building_solid
            
        except Exception as e:
            st.error(f"Generation failed: {str(e)}")
            st.session_state.generated = False
else:
    if generate_btn and not selected_rooms:
        st.warning("Please select at least one room type.")

# Display results if generated
if st.session_state.generated and st.session_state.rooms:
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h3>🏠</h3>
            <h2>{len(st.session_state.rooms)}</h2>
            <p>Rooms</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        total_area = sum(poly.area for poly in st.session_state.rooms.values() if poly.is_valid)
        st.markdown(f"""
        <div class="metric-card">
            <h3>📐</h3>
            <h2>{total_area:.1f} m²</h2>
            <p>Total Area</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        validity = st.session_state.validation
        status = "✅ Valid" if validity.get('is_valid', False) else "⚠️ Invalid"
        color = "success-badge" if validity.get('is_valid', False) else "error-badge"
        st.markdown(f"""
        <div class="metric-card">
            <h3>🔍</h3>
            <div class="{color}">{status}</div>
            <p>B-rep Status</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        volume = validation.get('statistics', {}).get('volume_m3', 0)
        if volume > 0:
            st.markdown(f"""
            <div class="metric-card">
                <h3>📦</h3>
                <h2>{volume:.1f} m³</h2>
                <p>Total Volume</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="metric-card">
                <h3>📦</h3>
                <h2>⚠️</h2>
                <p>Volume Error</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📐 Floor Plan", "🏗️ 3D Model", "🔍 Validation", "📊 Analysis"])
    
    with tab1:
        st.markdown("### Floor Plan Visualization")
        
        # Create matplotlib figure
        fig, ax = plt.subplots(figsize=(10, 8))
        
        colors = plt.cm.Set3(np.linspace(0, 1, max(1, len(st.session_state.rooms))))
        
        color_idx = 0
        for name, poly in st.session_state.rooms.items():
            if poly.is_valid:
                x, y = poly.exterior.xy
                ax.fill(x, y, alpha=0.5, color=colors[color_idx % len(colors)], label=name.capitalize())
                
                # Add room label
                centroid = poly.centroid
                ax.text(centroid.x, centroid.y, name.capitalize(), 
                       ha='center', va='center', fontsize=10, fontweight='bold')
                color_idx += 1
        
        # Draw adjacency graph overlay
        pos = {}
        for node, poly in st.session_state.rooms.items():
            if poly.is_valid:
                pos[node] = (poly.centroid.x, poly.centroid.y)
        
        if pos:
            nx.draw(st.session_state.adj_graph, pos, ax=ax, 
                   node_size=50, node_color='red', edge_color='gray', 
                   alpha=0.6, with_labels=False)
        
        ax.set_xlabel("X (meters)")
        ax.set_ylabel("Y (meters)")
        ax.set_title("Floor Plan with Room Adjacencies")
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        if color_idx > 0:
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        
        st.pyplot(fig)
        
        # Export floor plan - FIXED: use BytesIO instead of StringIO
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches='tight')
        buf.seek(0)
        st.download_button(
            label="📥 Download Floor Plan (PNG)",
            data=buf,
            file_name=f"floor_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            mime="image/png"
        )
        plt.close(fig)
    
    with tab2:
        st.markdown("### 3D Building Model")
        st.info("3D visualization of your building massing")
        
        # Simple 3D plot using plotly
        fig_3d = go.Figure()
        
        # Add rooms as extruded polygons
        for name, poly in st.session_state.rooms.items():
            if poly.is_valid:
                x, y = poly.exterior.xy
                z = [0] * len(x)
                
                # Create mesh for extrusion
                fig_3d.add_trace(go.Mesh3d(
                    x=list(x),
                    y=list(y),
                    z=z,
                    color='lightblue',
                    opacity=0.7,
                    name=name
                ))
        
        fig_3d.update_layout(
            scene=dict(
                xaxis_title="X (m)",
                yaxis_title="Y (m)",
                zaxis_title="Z (m)",
                aspectmode='data'
            ),
            title="3D Building Massing"
        )
        
        st.plotly_chart(fig_3d, use_container_width=True)
    
    with tab3:
        st.markdown("### B-rep Validation Report")
        
        validation = st.session_state.validation
        
        if validation.get('is_valid', False):
            st.success("✅ Geometry is valid and buildable!")
        else:
            st.error("❌ Geometry has issues that need attention")
        
        # Errors
        if validation.get('errors'):
            st.markdown("#### ❌ Errors")
            for error in validation['errors']:
                st.error(f"• {error}")
        
        # Warnings
        if validation.get('warnings'):
            st.markdown("#### ⚠️ Warnings")
            for warning in validation['warnings']:
                st.warning(f"• {warning}")
        
        # Statistics
        st.markdown("#### 📊 Geometry Statistics")
        stats = validation.get('statistics', {})
        if stats:
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Volume", f"{stats.get('volume_m3', 0):.2f} m³")
                st.metric("Surface Area", f"{stats.get('surface_area_m2', 0):.2f} m²")
                st.metric("Face Count", stats.get('face_count', 0))
            
            with col2:
                st.metric("Edge Count", stats.get('edge_count', 0))
                st.metric("Vertex Count", stats.get('vertex_count', 0))
                bbox = stats.get('bounding_box', {})
                st.metric("Bounding Box", f"{bbox.get('dx', 0):.1f} × {bbox.get('dy', 0):.1f} × {bbox.get('dz', 0):.1f} m")
        
        # Repair suggestions
        if validation.get('repair_suggestions'):
            st.markdown("#### 🔧 Repair Suggestions")
            for suggestion in validation['repair_suggestions']:
                st.info(f"💡 {suggestion}")
    
    with tab4:
        st.markdown("### Design Analysis")
        
        # Room area distribution
        st.markdown("#### Room Area Distribution")
        room_areas = {name: poly.area for name, poly in st.session_state.rooms.items() if poly.is_valid}
        if room_areas:
            df_areas = pd.DataFrame(list(room_areas.items()), columns=['Room', 'Area (m²)'])
            
            fig_area = px.bar(df_areas, x='Room', y='Area (m²)', 
                             title="Room Sizes",
                             color='Area (m²)',
                             color_continuous_scale='Viridis')
            st.plotly_chart(fig_area, use_container_width=True)
        
        # Adjacency matrix
        st.markdown("#### Room Adjacency Matrix")
        adj_matrix = nx.to_pandas_adjacency(st.session_state.adj_graph)
        st.dataframe(adj_matrix, use_container_width=True)
        
        # Connectivity metrics
        if len(st.session_state.adj_graph.nodes) > 0:
            st.markdown("#### Graph Metrics")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Graph Density", f"{nx.density(st.session_state.adj_graph):.3f}")
            with col2:
                diam = nx.diameter(st.session_state.adj_graph) if nx.is_connected(st.session_state.adj_graph) else "Disconnected"
                st.metric("Diameter", diam)
            with col3:
                st.metric("Average Clustering", f"{nx.average_clustering(st.session_state.adj_graph):.3f}")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: gray;">
    🏗️ Built with Streamlit, NetworkX, Shapely, and Plotly
</div>
""", unsafe_allow_html=True)
