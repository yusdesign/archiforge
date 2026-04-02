# archiforge
Architectural Forge 🆎

# 🏗️ AI Architectural Generator

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://arciforge.streamlit.app)

Generate novel, buildable floor plans using graph grammar, constraint satisfaction, and B-rep validation.

## Features

- 🎯 **Constraint-based design** - SAT solver ensures room adjacency and size requirements
- 📐 **Procedural layout** - Force-directed graph layout with Voronoi partitioning  
- 🔧 **B-rep validation** - CAD-quality geometry checking (manifold, thickness, intersections)
- 🎨 **Interactive web UI** - Real-time parameter tuning
- 💾 **Export options** - STEP, STL, PNG floor plans

## Quick Start

### Local Development

```bash
git clone https://github.com/yourusername/architectural-generator.git
cd architectural-generator
pip install -r requirements.txt
streamlit run app.py
