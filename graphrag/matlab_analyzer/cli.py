# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""MATLAB Analyzer CLI.

This module provides a command-line interface for analyzing MATLAB codebases
and generating graph representations of the code structure.
"""

import argparse
import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from .graph_builder import MATLABGraphBuilder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def analyze_matlab_project(
    project_path: str,
    output_file: Optional[str] = None,
    verbose: bool = False
) -> dict:
    """Analyze a MATLAB project and return the graph structure.
    
    Args:
        project_path: Path to the MATLAB project directory
        output_file: Optional path to save the graph as JSON
        verbose: Whether to enable verbose logging
        
    Returns:
        Dictionary containing the graph representation
    """
    # Set log level
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger().setLevel(log_level)
    
    # Validate project path
    project_dir = Path(project_path).resolve()
    if not project_dir.exists() or not project_dir.is_dir():
        logger.error("Project directory not found or is not a directory: %s", project_dir)
        sys.exit(1)
        
    logger.info("Analyzing MATLAB code in: %s", project_dir)
    
    try:
        # Create graph builder and build the graph
        builder = MATLABGraphBuilder()
        graph = builder.build_from_directory(str(project_path))
        
        # Generate statistics
        stats = generate_graph_statistics(graph)
        log_statistics(stats)
        
        # Prepare graph data
        graph_data = {
            "metadata": {
                "project_path": str(project_path),
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            },
            "statistics": stats,
            "graph": {
                "nodes": [node.dict() for node in graph.nodes.values()],
                "edges": [edge.dict() for edge in graph.edges]
            }
        }
        
        # Save to file if requested
        if output_file:
            save_graph(output_file, graph_data)
            
        return graph_data  # noqa: TRY300
        
    except Exception:
        logger.exception("Error analyzing MATLAB project")
        sys.exit(1)


def generate_graph_statistics(graph: Any) -> dict[str, Any]:
    """Generate statistics about the graph."""
    # Count nodes by type
    node_types = {}
    for node in graph.nodes.values():
        node_type = node.node_type.value
        node_types[node_type] = node_types.get(node_type, 0) + 1
    
    # Count edges by relationship
    edge_types = {}
    for edge in graph.edges:
        rel = edge.relationship.value
        edge_types[rel] = edge_types.get(rel, 0) + 1
    
    # Find most called functions
    call_counts = {}
    for edge in graph.edges:
        if edge.relationship.value == "calls":
            call_counts[edge.target_id] = call_counts.get(edge.target_id, 0) + 1
    
    # Get top 5 most called functions
    top_calls = sorted(call_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_functions = []
    for node_id, count in top_calls:
        node = graph.nodes.get(node_id)
        if node:
            top_functions.append({
                "name": node.name,
                "call_count": count,
                "file": getattr(node, "file_path", "")
            })
    
    return {
        "node_counts": node_types,
        "edge_counts": edge_types,
        "top_called_functions": top_functions,
        "total_nodes": len(graph.nodes),
        "total_edges": len(graph.edges)
    }


def log_statistics(stats: dict[str, Any]) -> None:
    """Log graph statistics."""
    logger.info("\n=== Graph Statistics ===")
    logger.info("Total nodes: %d", stats["total_nodes"])
    logger.info("Total edges: %d", stats["total_edges"])
    
    logger.info("\nNodes by type:")
    for node_type, count in sorted(stats["node_counts"].items(), 
                                 key=lambda x: x[1], reverse=True):
        logger.info("- %s: %d", node_type, count)
    
    logger.info("\nEdges by relationship:")
    for rel, count in sorted(stats["edge_counts"].items(),
                           key=lambda x: x[1], reverse=True):
        logger.info("- %s: %d", rel, count)
    
    logger.info("\nTop 5 most called functions:")
    for func in stats["top_called_functions"]:
        logger.info("- %s (called %d times) [%s]", 
                   func["name"], func["call_count"], func["file"])


def save_graph(output_file: str | Path, graph_data: dict[str, Any]) -> None:
    """Save the graph data to a JSON file."""
    try:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(graph_data, f, indent=2, ensure_ascii=False)
            
        logger.info("\nGraph saved to: %s", str(output_path))
    except Exception as e:
        logger.exception("Error saving graph: %s", str(e))  # noqa: TRY401
        raise


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Analyze MATLAB code and generate a graph representation.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "project_path",
        type=str,
        help="Path to the MATLAB project directory"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Output file path",
        default="matlab_graph.json"
    )
    parser.add_argument(
        "-v", "--verbose",
        help="Enable verbose output (DEBUG level logging)",
        action="store_true"
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point for the MATLAB analyzer CLI."""  # noqa: D401
    args = parse_arguments()
    try:
        analyze_matlab_project(
            project_path=args.project_path,
            output_file=args.output,
            verbose=args.verbose
        )
    except KeyboardInterrupt:
        logger.warning("Operation cancelled by user")
        sys.exit(1)
    except Exception:
        logger.exception("An error occurred")
        sys.exit(1)


if __name__ == "__main__":
    main()