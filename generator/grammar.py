"""
Graph grammar for architectural spatial relationships
"""
import networkx as nx
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, field
import random
from enum import Enum

class RoomType(Enum):
    LIVING = "living"
    KITCHEN = "kitchen"
    BEDROOM = "bedroom"
    BATHROOM = "bathroom"
    HALLWAY = "hallway"
    DINING = "dining"
    STUDY = "study"
    CLOSET = "closet"
    ENTRANCE = "entrance"

@dataclass
class SpatialRule:
    """Production rule for graph rewriting"""
    condition: callable
    action: callable
    priority: int = 0

class ArchitecturalGrammar:
    """Graph grammar for generating valid architectural adjacencies"""
    
    def __init__(self):
        self.room_types = list(RoomType)
        self.rules: List[SpatialRule] = []
        self._initialize_rules()
        
    def _initialize_rules(self):
        """Define architectural best practices as graph rewriting rules"""
        
        # Rule 1: Entrance connects to living or hallway
        def entrance_rule_condition(g: nx.Graph, node: str):
            return g.nodes[node].get('type') == RoomType.ENTRANCE and g.degree(node) == 0
        
        def entrance_rule_action(g: nx.Graph, node: str):
            possible = ['living', 'hallway']
            target = random.choice([n for n in g.nodes if g.nodes[n].get('type').value in possible])
            g.add_edge(node, target)
            return g
        
        self.rules.append(SpatialRule(entrance_rule_condition, entrance_rule_action, priority=10))
        
        # Rule 2: Kitchen adjacent to dining/living
        def kitchen_rule_condition(g: nx.Graph, node: str):
            return g.nodes[node].get('type') == RoomType.KITCHEN and g.degree(node) < 2
        
        def kitchen_rule_action(g: nx.Graph, node: str):
            for target in g.nodes:
                if target != node and g.nodes[target].get('type') in [RoomType.LIVING, RoomType.DINING]:
                    if not g.has_edge(node, target):
                        g.add_edge(node, target)
                        break
            return g
        
        self.rules.append(SpatialRule(kitchen_rule_condition, kitchen_rule_action, priority=8))
        
        # Rule 3: Bathroom adjacent to bedroom(s)
        def bathroom_rule_condition(g: nx.Graph, node: str):
            return g.nodes[node].get('type') == RoomType.BATHROOM and g.degree(node) < 2
        
        def bathroom_rule_action(g: nx.Graph, node: str):
            bedrooms = [n for n in g.nodes if g.nodes[n].get('type') == RoomType.BEDROOM]
            for bedroom in bedrooms[:2]:  # Max 2 bedrooms per bathroom
                if not g.has_edge(node, bedroom):
                    g.add_edge(node, bedroom)
            return g
        
        self.rules.append(SpatialRule(bathroom_rule_condition, bathroom_rule_action, priority=7))
        
        # Rule 4: Ensure connectivity
        def connectivity_condition(g: nx.Graph, node: str):
            return not nx.is_connected(g)
        
        def connectivity_action(g: nx.Graph, node: str):
            components = list(nx.connected_components(g))
            if len(components) > 1:
                # Connect closest components
                comp1 = list(components[0])
                comp2 = list(components[1])
                g.add_edge(comp1[0], comp2[0])
            return g
        
        self.rules.append(SpatialRule(connectivity_condition, connectivity_action, priority=1))
    
    def generate_adjacency(self, room_list: List[str]) -> nx.Graph:
        """
        Generate adjacency graph from room list using grammar rules
        
        Args:
            room_list: List of room names (e.g., ['living', 'kitchen', 'bedroom1'])
        
        Returns:
            NetworkX graph with adjacency edges
        """
        # Create graph with nodes
        g = nx.Graph()
        for room in room_list:
            room_type = self._infer_room_type(room)
            g.add_node(room, type=room_type)
        
        # Apply rules iteratively
        max_iterations = 50
        for _ in range(max_iterations):
            changed = False
            
            # Sort rules by priority
            sorted_rules = sorted(self.rules, key=lambda r: r.priority, reverse=True)
            
            for node in list(g.nodes()):
                for rule in sorted_rules:
                    if rule.condition(g, node):
                        g = rule.action(g, node)
                        changed = True
                        break  # Apply one rule per node per iteration
            
            if not changed:
                break
        
        # Final validation
        self._validate_grammar(g)
        return g
    
    def _infer_room_type(self, room_name: str) -> RoomType:
        """Map room name string to RoomType enum"""
        name_lower = room_name.lower()
        for room_type in RoomType:
            if room_type.value in name_lower:
                return room_type
        return RoomType.LIVING  # Default
    
    def _validate_grammar(self, g: nx.Graph):
        """Check if generated graph satisfies all constraints"""
        # Check no isolated nodes
        isolated = [n for n in g.nodes if g.degree(n) == 0]
        if isolated:
            # Connect isolated nodes
            main_nodes = [n for n in g.nodes if g.degree(n) > 0]
            if main_nodes:
                for iso in isolated:
                    g.add_edge(iso, main_nodes[0])
        
        # Ensure connectivity
        if not nx.is_connected(g):
            components = list(nx.connected_components(g))
            for i in range(len(components)-1):
                node1 = list(components[i])[0]
                node2 = list(components[i+1])[0]
                g.add_edge(node1, node2)
        
        return g

class GrammarOptimizer:
    """Optimize graph grammar using graph algorithms"""
    
    @staticmethod
    def minimize_cycles(g: nx.Graph) -> nx.Graph:
        """Remove unnecessary cycles while preserving connectivity"""
        # Compute spanning tree
        mst = nx.minimum_spanning_tree(g)
        
        # Add back essential edges (e.g., kitchen-dining if directly connected)
        essential_edges = []
        for u, v in g.edges():
            if g.nodes[u].get('type') in [RoomType.KITCHEN, RoomType.DINING]:
                if g.nodes[v].get('type') in [RoomType.KITCHEN, RoomType.DINING]:
                    essential_edges.append((u, v))
        
        mst.add_edges_from(essential_edges)
        return mst
    
    @staticmethod
    def add_circulation(g: nx.Graph) -> nx.Graph:
        """Add hallway nodes for better circulation"""
        # Find nodes with degree > 3
        high_degree = [n for n in g.nodes if g.degree(n) > 3]
        
        for node in high_degree:
            # Insert hallway node
            hallway = f"hallway_{node}"
            neighbors = list(g.neighbors(node))
            
            # Remove original edges
            for neighbor in neighbors:
                g.remove_edge(node, neighbor)
            
            # Add hallway connected to all
            g.add_node(hallway, type=RoomType.HALLWAY)
            g.add_edge(node, hallway)
            for neighbor in neighbors:
                g.add_edge(hallway, neighbor)
        
        return g
