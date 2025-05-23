# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""Data models for MATLAB code analysis.

This module defines the data structures used to represent MATLAB code elements
and their relationships in the graph database.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class MatlabNodeType(str, Enum):
    """Types of nodes in the MATLAB code graph.

    Attributes
    ----------
    SCRIPT : str
        Represents a MATLAB script file.
    FUNCTION : str
        Represents a MATLAB function.
    VARIABLE : str
        Represents a variable in the code.
    CLASS : str
        Represents a MATLAB class.
    METHOD : str
        Represents a method within a class.
    PROPERTY : str
        Represents a class property.
    PACKAGE : str
        Represents a package.
    PARAMETER : str
        Represents a function parameter.
    RETURN_VALUE : str
        Represents a return value.
    """
    
    SCRIPT = "script"
    FUNCTION = "function"
    VARIABLE = "variable"
    CLASS = "class"
    METHOD = "method"
    PROPERTY = "property"
    PACKAGE = "package"
    PARAMETER = "parameter"
    RETURN_VALUE = "return_value"


class Position(BaseModel):
    """Position in source code (line, column)."""

    line: int
    column: int


class CodeRange(BaseModel):
    """Range of code with start and end positions."""

    start: Position
    end: Position


class MatlabNode(BaseModel):
    """A node in the MATLAB code graph."""

    id: str
    name: str
    node_type: MatlabNodeType
    file_path: str
    code: str
    range: CodeRange
    parent_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class RelationshipType(str, Enum):
    """Types of relationships between nodes in the MATLAB code graph."""

    CONTAINS = "contains"  # Parent-child relationship (e.g., script contains function)
    CALLS = "calls"  # Function calls another function
    ASSIGNED_TO = "assigned_to"  # Variable assignment (x = y)
    USED_IN = "used_in"  # Variable used in expression
    PASSED_AS_ARG = "passed_as_arg"  # Variable passed as function argument
    RETURNS_TO = "returns_to"  # Return value assignment
    MODIFIES = "modifies"  # Variable modified by function
    READS = "reads"  # Variable read by function


class MatlabEdge(BaseModel):
    """An edge in the MATLAB code graph representing relationships."""

    source_id: str
    target_id: str
    relationship: RelationshipType
    metadata: dict = Field(default_factory=dict)


class MatlabGraph(BaseModel):
    """A graph representation of MATLAB code."""

    nodes: dict[str, MatlabNode] = Field(default_factory=dict)
    edges: list[MatlabEdge] = Field(default_factory=list)

    def add_node(self, node: MatlabNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relationship: RelationshipType,
        metadata: dict | None = None,
    ) -> None:
        """Add an edge to the graph.

        Parameters
        ----------
        source_id : str
            ID of the source node.
        target_id : str
            ID of the target node.
        relationship : RelationshipType
            Type of relationship between the nodes.
        metadata : dict, optional
            Optional metadata for the edge.

        Raises
        ------
        ValueError
            If source or target node is not found in the graph.
        """
        if source_id not in self.nodes or target_id not in self.nodes:
            error_msg = f"Source or target node not found: {source_id} -> {target_id}"
            raise ValueError(error_msg)
            
        self.edges.append(
            MatlabEdge(
                source_id=source_id,
                target_id=target_id,
                relationship=relationship,
                metadata=metadata or {},
            ),
        )

    def get_node_by_name(
        self,
        name: str,
        node_type: MatlabNodeType | None = None,
    ) -> MatlabNode | None:
        """Find a node by name and optionally type.

        Parameters
        ----------
        name : str
            Name of the node to find.
        node_type : MatlabNodeType, optional
            Optional node type to filter by.


        Returns
        -------
        MatlabNode or None
            The found node or None if not found.
        """
        for node in self.nodes.values():
            if node.name == name and (node_type is None or node.node_type == node_type):
                return node
        return None

    def get_children(self, node_id: str) -> list[MatlabNode]:
        """Get all child nodes of a given node.

        Parameters
        ----------
        node_id : str
            ID of the parent node.


        Returns
        -------
        list[MatlabNode]
            List of child nodes.


        Example
        -------
        >>> graph = MatlabGraph()
        >>> children = graph.get_children("parent_node_id")
        """
        if node_id not in self.nodes:
            return []

        return [
            self.nodes[edge.target_id]
            for edge in self.edges
            if (
                edge.source_id == node_id and
                edge.relationship == RelationshipType.CONTAINS and
                edge.target_id in self.nodes
            )
        ]

    def get_callers(self, function_id: str) -> list[MatlabNode]:
        """Get all nodes that call the specified function.

        Parameters
        ----------
        function_id : str
            ID of the function to find callers for.


        Returns
        -------
        list[MatlabNode]
            List of nodes that call the specified function.


        Example
        -------
        >>> graph = MatlabGraph()
        >>> callers = graph.get_callers("function_id")
        """
        return [
            self.nodes[edge.source_id]
            for edge in self.edges
            if (
                edge.target_id == function_id
                and edge.relationship == RelationshipType.CALLS
                and edge.source_id in self.nodes
            )
        ]

    def get_callees(self, node_id: str) -> list[MatlabNode]:
        """Get all functions called by the specified node.

        Parameters
        ----------
        node_id : str
            ID of the node to find callees for.


        Returns
        -------
        list[MatlabNode]
            List of nodes that are called by the specified node.


        Example
        -------
        >>> graph = MatlabGraph()
        >>> callees = graph.get_callees("function_id")
        """
        return [
            self.nodes[edge.target_id]
            for edge in self.edges
            if (
                edge.source_id == node_id and
                edge.relationship == RelationshipType.CALLS and
                edge.target_id in self.nodes
            )
        ]
