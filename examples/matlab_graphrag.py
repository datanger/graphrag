"""Example of using MATLAB analyzer graph with GraphRAG."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import networkx as nx
import numpy as np
from tqdm import tqdm

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from graphrag.matlab_analyzer.graph_loader import MATLABGraphLoader
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import networkx as nx
from graphrag.matlab_analyzer.graph_loader import MATLABGraphLoader


def setup_logging(verbose: bool = False) -> None:
    """Configure logging.
    
    Args:
        verbose: If True, set log level to DEBUG
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()]
    )

def chunk_graph(
    graph: nx.DiGraph,
    max_nodes_per_chunk: int = 50,
    overlap: int = 5
) -> list[nx.DiGraph]:
    """
    Chunk a MATLAB analyzer graph into smaller subgraphs.
    
    Args:
        graph: Input directed graph from MATLAB analyzer
        max_nodes_per_chunk: Maximum number of nodes per chunk
        overlap: Number of overlapping nodes between consecutive chunks
        
    Returns:
        List of chunked subgraphs
    """
    if not isinstance(graph, nx.DiGraph):
        raise ValueError("Input must be a NetworkX DiGraph")
        
    if max_nodes_per_chunk <= 0:
        raise ValueError("max_nodes_per_chunk must be positive")
        
    if overlap < 0 or overlap >= max_nodes_per_chunk:
        raise ValueError("overlap must be non-negative and less than max_nodes_per_chunk")
    
    # Convert to undirected graph for community detection
    undirected = graph.to_undirected()
    chunks = []
    
    # Process each connected component separately
    for component in nx.connected_components(undirected):
        component_nodes = list(component)
        
        # If component is small enough, add as is
        if len(component_nodes) <= max_nodes_per_chunk:
            chunks.append(graph.subgraph(component_nodes).copy())
            continue
            
        # Otherwise, split into chunks with overlap
        step = max(1, max_nodes_per_chunk - overlap)
        for i in range(0, len(component_nodes), step):
            end = min(i + max_nodes_per_chunk, len(component_nodes))
            chunk_nodes = component_nodes[i:end]
            chunks.append(graph.subgraph(chunk_nodes).copy())
            
    return chunks

def main():
    """Main function to demonstrate loading MATLAB graph."""
    parser = argparse.ArgumentParser(description="Load MATLAB graph into GraphRAG")
    parser.add_argument(
        "--graph-file",
        type=str,
        default="output/graph.json",
        help="Path to the graph.json file from MATLAB analyzer"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    
    logger = logging.getLogger(__name__)
    
    try:
        # Load the MATLAB graph
        logger.info("Loading MATLAB graph from %s", args.graph_file)
        loader = MATLABGraphLoader(args.graph_file)
        graph = loader.load()
        
        # Basic graph information
        logger.info("Graph loaded successfully")
        logger.info("Number of nodes: %d", len(graph.nodes))
        logger.info("Number of edges: %d", len(graph.edges))
    
    # Calculate basic graph metrics
    in_degrees = dict(graph.in_degree())
    out_degrees = dict(graph.out_degree())
    
    # Find key nodes (functions with most callers/callees)
    top_callers = sorted(in_degrees.items(), key=lambda x: x[1], reverse=True)[:5]
    top_callees = sorted(out_degrees.items(), key=lambda x: x[1], reverse=True)[:5]
    
    logger.info("\nKey nodes analysis:")
    logger.info("Top 5 most called functions:")
    for node, degree in top_callers:
        logger.info(f"  - {node}: called {degree} times")
        
    logger.info("\nTop 5 functions with most calls:")
    for node, degree in top_callees:
        logger.info(f"  - {node}: makes {degree} calls")
        for i, (node_id, node_data) in enumerate(graph.nodes(data=True)):
            if i >= 3:  # Show first 3 nodes
                break
            logger.info("  Node %s: %s", node_id, node_data)
        
        logger.info("\nSample edges:")
        for i, (source, target, data) in enumerate(graph.edges(data=True)):
            if i >= 3:  # Show first 3 edges
                break
            logger.info("  Edge %s -> %s: %s", source, target, data)
        
        # Chunk the graph into manageable pieces
        logger.info("Chunking graph...")
        chunks = chunk_graph(graph, max_nodes_per_chunk=30, overlap=3)
        logger.info(f"Split graph into {len(chunks)} chunks")
        
        # Enhanced chunk analysis
        chunk_metrics = []
        
        for i, chunk in enumerate(tqdm(chunks, desc="Analyzing chunks")):
            try:
                # Get nodes and edges
                nodes = list(chunk.nodes(data=True))
                edges = list(chunk.edges(data=True))
                num_nodes = len(nodes)
                num_edges = len(edges)
                
                # Calculate chunk metrics
                chunk_info = {
                    'chunk_id': i + 1,
                    'num_nodes': num_nodes,
                    'num_edges': num_edges,
                    'node_types': defaultdict(int),
                    'relationships': defaultdict(int),
                    'node_list': [],
                    'edge_list': []
                }
                
                # Analyze node types
                for node, data in nodes:
                    node_type = data.get('node_type', 'unknown')
                    chunk_info['node_types'][node_type] += 1
                    chunk_info['node_list'].append({
                        'id': node,
                        'type': node_type,
                        'name': data.get('name', '')
                    })
                
                # Analyze relationships
                for src, tgt, data in edges:
                    rel_type = data.get('relationship', 'unknown')
                    chunk_info['relationships'][rel_type] += 1
                    chunk_info['edge_list'].append({
                        'source': src,
                        'target': tgt,
                        'type': rel_type
                    })
                
                # Calculate density (for connected components)
                if num_nodes > 1:
                    density = (2 * num_edges) / (num_nodes * (num_nodes - 1))
                else:
                    density = 0.0
                chunk_info['density'] = density
                
                chunk_metrics.append(chunk_info)
                
                # Log chunk summary
                if i < 5:  # Only show details for first 5 chunks
                    logger.info(f"\nChunk {i+1}:")
                    logger.info(f"  - Nodes: {num_nodes}")
                    logger.info(f"  - Edges: {num_edges}")
                    logger.info(f"  - Density: {density:.4f}")
                    
                    # Show node type distribution
                    logger.info("  - Node types:")
                    for node_type, count in chunk_info['node_types'].items():
                        logger.info(f"    - {node_type}: {count} ({(count/num_nodes)*100:.1f}%)")
                    
                    # Show relationship distribution
                    logger.info("  - Relationships:")
                    for rel, count in chunk_info['relationships'].items():
                        logger.info(f"    - {rel}: {count} ({(count/num_edges*100 if num_edges > 0 else 0):.1f}%)")
            except Exception as e:
                logger.error(f"Error analyzing chunk {i+1}: {str(e)}")
                
                # Save chunk analysis results
                output_dir = Path("output/analysis")
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # Save chunk metadata
                with open(output_dir / "chunk_metrics.json", "w") as f:
                    json.dump(chunk_metrics, f, indent=2)
                
                # Save individual chunks for RAG
                for chunk_info in chunk_metrics:
                    chunk_id = chunk_info['chunk_id']
                    chunk_dir = output_dir / f"chunk_{chunk_id}"
                    chunk_dir.mkdir(exist_ok=True)
                    
                    # Save nodes and edges separately
                    with open(chunk_dir / "nodes.json", "w") as f:
                        json.dump(chunk_info['node_list'], f, indent=2)
                    
                    with open(chunk_dir / "edges.json", "w") as f:
                        json.dump(chunk_info['edge_list'], f, indent=2)
                    
                    # Create a summary markdown file
                    with open(chunk_dir / "summary.md", "w") as f:
                        f.write(f"# Chunk {chunk_id} Summary\n\n")
                        f.write(f"- **Nodes**: {chunk_info['num_nodes']}\n")
                        f.write(f"- **Edges**: {chunk_info['num_edges']}\n")
                        f.write(f"- **Density**: {chunk_info['density']:.4f}\n\n")
                        
                        f.write("## Node Types\n")
                        for node_type, count in chunk_info['node_types'].items():
                            f.write(f"- {node_type}: {count} ({(count/chunk_info['num_nodes']*100):.1f}%)\n")
                        
                        f.write("\n## Relationships\n")
                        for rel, count in chunk_info['relationships'].items():
                            f.write(f"- {rel}: {count} ({(count/chunk_info['num_edges']*100 if chunk_info['num_edges'] > 0 else 0):.1f}%)\n")
                
                logger.info(f"\nAnalysis complete. Results saved to {output_dir}")
                
            except Exception as e:
                logger.error(f"Error in post-processing: {str(e)}")
                raise
                
        # Node type distribution
        node_types = {}
        for node, data in chunk.nodes(data=True):
                    node_type = data.get('node_type', 'unknown')
                    node_types[node_type] = node_types.get(node_type, 0) + 1
                
                logger.info("  - Node types:")
                for node_type, count in node_types.items():
                    logger.info(f"    - {node_type}: {count} ({count/num_nodes:.1%})")
                
                # Edge relationship types
                edge_relationships = {}
                for _, _, data in chunk.edges(data=True):
                    rel_type = data.get('relationship', 'unknown')
                    edge_relationships[rel_type] = edge_relationships.get(rel_type, 0) + 1
                
                logger.info("  - Edge relationships:")
                for rel_type, count in edge_relationships.items():
                    logger.info(f"    - {rel_type}: {count} ({count/num_edges:.1%})")
                
                # Example: Find high-degree nodes
                if num_nodes > 0:
                    degrees = dict(chunk.degree())
                    max_degree_node = max(degrees.items(), key=lambda x: x[1])
                    logger.info(f"  - Node with highest degree: {max_degree_node[0]} (degree: {max_degree_node[1]})")
                
            except Exception as e:
                logger.error(f"Error analyzing chunk {i+1}: {e}")
                continue
        
    except Exception as e:
        logger.exception("Error: %s", e, exc_info=args.verbose)  # noqa: TRY401
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
