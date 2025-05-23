# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""MATLAB Analyzer Example.

This example demonstrates how to use the MATLAB analyzer to build a graph representation
of MATLAB code structure from the GINav project.
"""

import json
import logging
from pathlib import Path
import sys
from typing import Any

# Add the parent directory to the path so we can import graphrag
sys.path.append(str(Path(__file__).parent.parent))

from graphrag.matlab_analyzer import MATLABGraphBuilder

# Configure logging
logger = logging.getLogger(__name__)


def analyze_ginav() -> None:
    """Analyze the GINav MATLAB code and print the graph structure."""
    # Path to the GINav MATLAB code
    ginav_path = Path("workspace") / "GINav"
    
    if not ginav_path.exists():
        logger.error("GINav directory not found at %s", ginav_path)
        logger.info("Please update the path in the script to point to your GINav repository.")
        return
    
    logger.info("Analyzing MATLAB code in: %s", ginav_path)
    
    # Create a graph builder
    builder = MATLABGraphBuilder()
    
    # Build the graph from the GINav directory
    graph = builder.build_from_directory(str(ginav_path))
    
    # Print some statistics
    logger.info("\nGraph Statistics:")
    logger.info("- Total nodes: %d", len(graph.nodes))
    logger.info("- Total edges: %d", len(graph.edges))
    
    # Count nodes by type
    node_types: dict[str, int] = {}
    for node in graph.nodes.values():
        node_type = node.node_type.value
        node_types[node_type] = node_types.get(node_type, 0) + 1
    
    logger.info("\nNodes by type:")
    for node_type, count in sorted(node_types.items(), key=lambda x: x[1], reverse=True):
        logger.info("- %s: %d", node_type, count)
    
    # Count edges by relationship
    edge_types: dict[str, int] = {}
    for edge in graph.edges:
        rel = edge.relationship.value
        edge_types[rel] = edge_types.get(rel, 0) + 1
    
    logger.info("\nEdges by relationship:")
    for rel, count in sorted(edge_types.items(), key=lambda x: x[1], reverse=True):
        logger.info("- %s: %d", rel, count)
    
    # Find all functions
    functions = [n for n in graph.nodes.values() if n.node_type.value == "function"]
    logger.info("Found %d functions", len(functions))
    
    # Find all files
    files: dict[str, list[Any]] = {}
    for node in graph.nodes.values():
        if hasattr(node, "file_path") and node.file_path:
            files.setdefault(node.file_path, []).append(node)
    
    logger.info("Found %d files", len(files))
    
    # Find and print the top 5 most called functions
    call_counts: dict[str, int] = {}
    for edge in graph.edges:
        if edge.relationship.value == "calls":
            call_counts[edge.target_id] = call_counts.get(edge.target_id, 0) + 1
    
    logger.info("\nTop 5 most called functions:")
    top_calls = sorted(call_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    for node_id, count in top_calls:
        node = graph.nodes.get(node_id)
        if node:
            logger.info("- %s (called %d times)", node.name, count)
    
    # Save the graph to a JSON file for further analysis
    output_file = Path("ginav_graph.json")
    with output_file.open("w", encoding="utf-8") as f:
        graph_dict = {
            "nodes": [node.dict() for node in graph.nodes.values()],
            "edges": [edge.dict() for edge in graph.edges]
        }
        json.dump(graph_dict, f, indent=2)
    
    logging.info("\nGraph saved to %s", output_file)


def main() -> None:
    """Run the MATLAB analyzer example."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )
    analyze_ginav()


if __name__ == "__main__":
    main()
