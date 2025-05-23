# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""MATLAB AST Parser for GraphRAG.

This module provides functionality to parse MATLAB code and generate an Abstract Syntax Tree (AST).
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Any, Optional, TypeAlias, TypeVar

from .models import MatlabGraph

# Type aliases for better type hints
Node: TypeAlias = dict[str, Any]
ScopeType = TypeVar("ScopeType", bound="Scope")


class NodeType(Enum):
    """Enumeration of node types in the AST."""
    
    PROGRAM = "Program"
    FUNCTION = "Function"
    CLASS = "Class"
    VARIABLE = "Variable"
    CALL = "Call"


class MATLABParserError(Exception):
    """Base exception for MATLAB parser errors."""

    pass


class MATLABSyntaxError(MATLABParserError):
    """Exception raised for syntax errors in MATLAB code."""

    def __init__(self, message: str, line: Optional[int] = None, col: Optional[int] = None) -> None:
        """Initialize syntax error with message and location.
        
        Args:
            message: Error message describing the syntax error.
            line: Line number where the error occurred (optional).
            col: Column number where the error occurred (optional).
        """
        if line is not None and col is not None:
            message = f"{message} at line {line}, column {col}"
        elif line is not None:
            message = f"{message} at line {line}"
        super().__init__(message)
        self.line = line
        self.col = col


class VariableUsage:
    """Tracks how a variable is used within a scope.
    
    Attributes:
        name: Name of the variable.
        node_type: Type of usage (e.g., 'assignment', 'reference', 'parameter').
        line: Line number where the variable is used.
        col: Column number where the variable is used.
        assigned_value: The value assigned to the variable, if any.
        references: List of references to this variable.
        parent_scope: The parent scope of this variable.
    """

    def __init__(self, name: str, node_type: str, line: int, col: int) -> None:
        """Initialize variable usage.
        
        Args:
            name: Name of the variable.
            node_type: Type of usage (e.g., 'assignment', 'reference', 'parameter').
            line: Line number where the variable is used.
            col: Column number where the variable is used.
        """
        self.name = name
        self.node_type = node_type
        self.line = line
        self.col = col
        self.assigned_value: Any = None
        self.references: list[dict[str, Any]] = []
        self.parent_scope: Optional['Scope'] = None

    def __repr__(self) -> str:
        """Return string representation of the variable usage.
        
        Returns:
            String representation of the variable usage.
        """
        return f'<VariableUsage {self.node_type} "{self.name}" at {self.line}:{self.col}>'


class Scope:
    """Represents a lexical scope in MATLAB code.
    
    Attributes:
        name: Name of the scope (function name, script name, etc.).
        scope_type: Type of scope ('function', 'script', 'class', etc.).
        parent: Parent scope, if any.
        variables: Dictionary mapping variable names to VariableUsage objects.
        children: List of child scopes.
        returns: List of return statements in this scope.
    """
    
    def __init__(self, name: str, scope_type: str, parent: Optional["Scope"] = None) -> None:
        """Initialize a new scope.
        
        Args:
            name: Name of the scope (function name, script name, etc.).
            scope_type: Type of scope ('function', 'script', 'class', etc.).
            parent: Parent scope, if any.
        """
        self.name = name
        self.scope_type = scope_type
        self.parent = parent
        self.variables: dict[str, VariableUsage] = {}  # name -> VariableUsage
        self.children: list['Scope'] = []
        self.returns: list[dict[str, Any]] = []
        
        if parent:
            parent.add_child(self)
    
    def add_child(self, child_scope: 'Scope') -> None:
        """Add a child scope.
        
        Args:
            child_scope: The child scope to add.
        """
        self.children.append(child_scope)
    
    def add_variable(self, var_name: str, usage_type: str, line: int, col: int) -> VariableUsage:
        """Add a variable usage to this scope.
        
        Args:
            var_name: Name of the variable.
            usage_type: Type of usage ('assignment', 'reference', 'parameter', etc.).
            line: Line number where the variable is used.
            col: Column number where the variable is used.
            
        Returns:
            The created or updated VariableUsage object.
        """
        if var_name not in self.variables:
            self.variables[var_name] = VariableUsage(var_name, usage_type, line, col)
        return self.variables[var_name]
    
    def find_variable(self, var_name: str) -> Optional[VariableUsage]:
        """Find a variable in this scope or any parent scope.
        
        Args:
            var_name: Name of the variable to find.
            
        Returns
        -------
            The VariableUsage object if found, None otherwise.
        """
        if var_name in self.variables:
            return self.variables[var_name]
        if self.parent:
            return self.parent.find_variable(var_name)
        return None


class MATLABASTParser:
    """Parser for MATLAB code that builds an Abstract Syntax Tree (AST).
    
    This parser handles:
    - Function definitions
    - Script files
    - Class definitions
    - Method definitions
    
    Attributes:
        file_path: Path to the MATLAB file to parse.
        code: Contents of the MATLAB file.
        tree: The parsed AST tree.
        graph: The graph representation of the code.
        current_scope: Current scope being processed.
        variables: Dictionary of variables in the current scope.
        functions: Dictionary of function definitions.
        classes: Dictionary of class definitions.
    """

    def __init__(self, file_path: str | Path) -> None:
        """Initialize the parser with a file path.
        
        Args:
            file_path: Path to the MATLAB file to parse.
            
        Raises:
            FileNotFoundError: If the specified file does not exist.
            MATLABParserError: If there is an error reading the file.
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            msg = f"File not found: {self.file_path}"
            raise FileNotFoundError(msg)
            
        self.code = self._read_file()
        self.lines = self.code.splitlines()
        self.graph = MatlabGraph()
        self.current_scope: Scope | None = None  # Current scope
        self.scope_stack: list[Scope] = []  # Stack of scopes
        self.variables: dict[str, VariableUsage] = {}  # Track variable usage
        self.functions: dict[str, dict] = {}  # Track function definitions
        self.classes: dict[str, dict] = {}  # Track class definitions
        self.ast = {"type": "Program", "body": []}  # Root AST node
        self.tokens: list[dict] = []  # Tokenized MATLAB code

    def _read_file(self) -> str:
        """Read the contents of the MATLAB file, trying multiple encodings.
        
        Returns
        -------
            The contents of the file as a string.
            
        Raises
        ------
            MATLABParserError: If the file cannot be read with any of the attempted encodings.
        """
        # List of encodings to try, in order of preference
        encodings = ['utf-8', 'gbk', 'shift-jis', 'windows-1252', 'gb2312', 'cp1252']
        
        for encoding in encodings:
            try:
                return self.file_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
            except OSError as e:
                # If it's not a decoding error but some other I/O error, raise it
                error_msg = f"Failed to read file {self.file_path}: {e}"
                raise MATLABParserError(error_msg) from e
        
        # If we've tried all encodings and failed
        raise MATLABParserError(
            f"Failed to read file {self.file_path} with any of the supported encodings: "
            f"{', '.join(encodings)}. The file may be using an unsupported encoding."
        )
    
    def _parse(self) -> None:
        """Process the MATLAB code and build the syntax tree."""
        self.tokens = self._tokenize()
        # Skip Python AST parsing for MATLAB code
        self.tree = None
    
    def _tokenize(self) -> list[dict]:
        """Tokenize the MATLAB code.
        
        Returns
        -------
            List of token dictionaries with 'type' and 'value' keys.
        """
        tokens = []
        
        for i, line in enumerate(self.lines, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith("%"):
                tokens.append({
                    "type": "comment" if line.startswith("%") else "empty",
                    "value": line,
                    "line": i,
                    "col": 0
                })
                continue
                
            # Detect function definition
            if line.startswith("function"):
                tokens.append({
                    'type': 'keyword',
                    'value': 'function',
                    'line': i,
                    'col': line.index('function') + 1
                })
                
                # Handle the rest of the function declaration
                func_decl = line[8:].strip()
                
                # Check for output arguments
                if func_decl.startswith('['):
                    end_bracket = func_decl.find(']')
                    if end_bracket != -1:
                        outputs = [o.strip() for o in func_decl[1:end_bracket].split(",")]
                        func_decl = func_decl[end_bracket+1:].strip()
                        
                        # Add output arguments as tokens
                        for output in outputs:
                            if output:  # Skip empty outputs
                                tokens.append({
                                    'type': 'identifier',
                                    'value': output,
                                    'line': i,
                                    'col': line.find(output) + 1
                                })
                
                # Check for function name
                func_name_match = re.match(r'^([a-zA-Z_]\w*)', func_decl)
                if func_name_match:
                    func_name = func_name_match.group(1)
                    tokens.append({
                        'type': 'function',
                        'value': func_name,
                        'line': i,
                        'col': line.find(func_name) + 1
                    })
                    
                    # Handle input arguments
                    input_args = re.search(r'\((.*?)\)', func_decl)
                    if input_args:
                        inputs = [i.strip() for i in input_args.group(1).split(",") if i.strip()]
                        for arg in inputs:
                            tokens.append({
                                'type': 'parameter',
                                'value': arg,
                                'line': i,
                                'col': line.find(arg) + 1
                            })
                            
                    # Add function scope
                    if self.current_scope:
                        func_scope = Scope(func_name, "function", self.current_scope)
                        self.scope_stack.append(func_scope)
                        self.current_scope = func_scope
            
            # Handle other MATLAB code (simplified)
            else:
                # Split line into tokens (simplified tokenization)
                # This is a basic implementation - a real MATLAB tokenizer would be more sophisticated
                for match in re.finditer(r'([a-zA-Z_]\w*|"[^"]*"|\d+\.?\d*|\S)', line):
                    value = match.group(1)
                    token_type = 'identifier'
                    
                    if value.isdigit() or (value.replace('.', '', 1).isdigit() and value.count('.') <= 1):
                        token_type = 'number'
                    elif value.startswith('"') and value.endswith('"'):
                        token_type = 'string'
                    elif value in ['+', '-', '*', '/', '^', '=', '==', '~=', '<', '>', '<=', '>=']:
                        token_type = 'operator'
                    
                    tokens.append({
                        'type': token_type,
                        'value': value,
                        'line': i,
                        'col': match.start() + 1
                    })
                    
                    # Track variable usage in current scope
                    if self.current_scope and token_type == "identifier" and value not in self.current_scope.variables:  # noqa: S105
                        self.current_scope.add_variable(value, "reference", i, match.start() + 1)
        
        return tokens
    
    def parse_file(self) -> dict:
        """Parse the MATLAB file and build the AST.
        
        Returns:
            dict: The root node of the AST.
        """
        ast = {"type": "Program", "body": []}
        current_class = None
        
        # Initialize scope stack if not exists
        if not hasattr(self, 'scope_stack'):
            self.scope_stack = []
            self.current_scope = None
        
        for i, line in enumerate(self.lines, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith("%"):
                continue
                
            # Detect function definition
            if line.startswith("function"):
                # Handle the rest of the function declaration
                func_decl = line[8:].strip()
                outputs = []
                
                # Check for output arguments
                if func_decl.startswith('['):
                    end_bracket = func_decl.find(']')
                    if end_bracket != -1:
                        outputs = [o.strip() for o in func_decl[1:end_bracket].split(",") if o.strip()]
                        func_decl = func_decl[end_bracket+1:].strip()
                
                # Check for function name
                func_name_match = re.match(r"^([a-zA-Z_]\w*)", func_decl)
                if func_name_match:
                    func_name = func_name_match.group(1)
                    
                    # Handle input arguments
                    input_args = re.search(r"\s*\((.*?)\)", func_decl)
                    inputs = []
                    if input_args:
                        inputs = [i.strip() for i in input_args.group(1).split(",") if i.strip()]
                    
                    # Create function node
                    func_node = {
                        "type": "Function",
                        "name": func_name,
                        "params": inputs,
                        "outputs": outputs,
                        "body": [],
                        "location": {
                            "start": {"line": i, "column": 0},
                            "end": {"line": i, "column": len(line)}
                        }
                    }
                    ast['body'].append(func_node)
                    
                    # Push function scope
                    if self.current_scope:
                        func_scope = Scope(func_name, "function", self.current_scope)
                        self.scope_stack.append(func_scope)
                        self.current_scope = func_scope
            
            # Detect class definition
            elif line.startswith("classdef"):
                current_class = line[8:].strip()
                # Push class scope
                if self.current_scope:
                    class_scope = Scope(current_class, "class", self.current_scope)
                    self.scope_stack.append(class_scope)
                    self.current_scope = class_scope
            
            # Detect end of function
            if line == "end" and i > 1 and self.lines[i-2].strip().startswith("function"):  # noqa: SIM102
                if self.scope_stack:
                    self.scope_stack.pop()
                    self.current_scope = self.scope_stack[-1] if self.scope_stack else None
        
        return ast
    
    def get_classes(self) -> list[dict]:
        """Extract class definitions from the code.
        
        Returns:
            List of class definitions with their metadata.
        """
        ast_tree = self.parse_file()
        return [node for node in ast_tree['body'] if node['type'] == 'Class']
    
    def get_functions(self) -> list[dict]:
        """Extract function definitions from the code.
        
        Returns:
            List of function definitions with their metadata.
            
        Note:
            This parses the entire file to extract function definitions.
        """
        ast_tree = self.parse_file()
        return [node for node in ast_tree['body'] if node['type'] == 'Function']

    def get_variables(self) -> list[dict]:
        """Extract all variable occurrences from the code, including declarations and references.
        
        Returns:
            List of variable occurrences with their metadata, including all positions
            where each variable appears in the code.
            
        Note:
            This implementation identifies both variable declarations and references
            throughout the code, including those in expressions and assignments.
        """
        # Pattern for variable assignments (declarations or reassignments)
        assignment_pattern = re.compile(r'^\s*([a-zA-Z_]\w*)\s*=')
        # Pattern for variable references (not in strings or comments)
        reference_pattern = re.compile(r'\b([a-zA-Z_]\w*)\b(?!=<|>|==|~=)')
        
        # Track all variable occurrences
        variables = {}
        
        for i, line in enumerate(self.lines, 1):
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('%'):
                continue
                
            # Skip function/class definition lines
            if any(line.startswith(keyword) for keyword in 
                  ('function', 'classdef', 'methods', 'properties')):
                continue
                
            # Check for variable assignments
            assign_match = assignment_pattern.match(line)
            if assign_match:
                var_name = assign_match.group(1)
                if var_name not in variables:
                    variables[var_name] = []
                variables[var_name].append({
                    'line': i,
                    'col': assign_match.start(1) + 1,  # 1-based column
                    'type': 'assignment',
                    'code': line
                })
            
            # Find all variable references in the line
            for ref_match in reference_pattern.finditer(line):
                var_name = ref_match.group(1)
                # Skip MATLAB keywords and built-ins
                if var_name in {'if', 'else', 'for', 'while', 'end', 'function', 
                               'return', 'break', 'continue', 'classdef', 'properties',
                               'methods', 'true', 'false', 'inf', 'nan', 'pi', 'i', 'j'}:
                    continue
                    
                # Skip if this is part of a string or comment
                if any(c in line[:ref_match.start()] for c in '\'"%'):
                    continue
                    
                if var_name not in variables:
                    variables[var_name] = []
                    
                # Only add if not already added for this position (to avoid duplicates)
                if not any(occ['line'] == i and occ['col'] == ref_match.start(1) + 1 
                          for occ in variables[var_name]):
                    variables[var_name].append({
                        'line': i,
                        'col': ref_match.start(1) + 1,  # 1-based column
                        'type': 'reference',
                        'code': line
                    })
        
        # Convert to the expected format
        result = []
        for var_name, occurrences in variables.items():
            if not occurrences:
                continue
                
            # Sort occurrences by line number
            sorted_occurrences = sorted(occurrences, key=lambda x: x['line'])
            
            # Create a single variable entry with all its occurrences
            var_entry = {
                'type': 'Variable',
                'name': var_name,
                'location': {
                    'start': {
                        'line': sorted_occurrences[0]['line'],
                        'column': sorted_occurrences[0]['col']
                    },
                    'end': {
                        'line': sorted_occurrences[-1]['line'],
                        'column': sorted_occurrences[-1]['col'] + len(var_name) - 1
                    }
                },
                'occurrences': sorted_occurrences
            }
            result.append(var_entry)
        
        return result
