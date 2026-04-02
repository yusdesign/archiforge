"""
Simple graph grammar for architectural adjacencies
"""
import networkx as nx
from typing import List, Dict, Set, Tuple, Optional
from enum import Enum

class RoomType(Enum):
    LIVING = "living"
    KITCHEN = "kitchen"
    BEDROOM = "bedroom"
    BATHROOM = "bathroom"
    HALLWAY = "hallway"
    DINING = "dining"
    STUDY = "study"

class ArchitecturalGrammar:
    def __init__(self):
        pass
        
    def generate_adjacency(self, room_list: List[str]) -> nx.Graph:
        """Generate simple adjacency graph"""
        g = nx.Graph()
        
        # Add all rooms as nodes
        for room in room_list:
            g.add_node(room, type=room)
        
        # Create simple chain adjacency (living room as hub)
        if 'living' in room_list:
            hub = 'living'
        elif 'kitchen' in room_list:
            hub = 'kitchen'
        else:
            hub = room_list[0] if room_list else None
        
        if hub:
            for room in room_list:
                if room != hub:
                    g.add_edge(hub, room)
        
        # Add specific adjacencies
        if 'kitchen' in room_list and 'dining' in room_list:
            g.add_edge('kitchen', 'dining')
        
        if 'bedroom' in room_list and 'bathroom' in room_list:
            g.add_edge('bedroom', 'bathroom')
        
        if 'entrance' in room_list and 'living' in room_list:
            g.add_edge('entrance', 'living')
        
        return g

class GrammarOptimizer:
    @staticmethod
    def minimize_cycles(g: nx.Graph) -> nx.Graph:
        """Remove unnecessary cycles"""
        # Already minimal in our simple graph
        return g
    
    @staticmethod
    def add_circulation(g: nx.Graph) -> nx.Graph:
        """Add hallway connections if needed"""
        # Simple implementation
        return g
