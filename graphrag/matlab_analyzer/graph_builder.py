"""
MATLAB Graph Builder for GraphRAG

This module builds a graph representation of MATLAB code structure.
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .models import (
    MatlabGraph,
    MatlabNode,
    MatlabNodeType,
    Position,
    CodeRange,
    RelationshipType
)
from .ast_parser import MATLABASTParser, MATLABParserError


class MATLABGraphBuilder:
    """
    Builds a graph representation of MATLAB code structure.
    
    This class takes parsed MATLAB code and constructs a graph where:
    - Nodes represent code elements (scripts, functions, variables, etc.)
    - Edges represent relationships between these elements
    """
    
    def __init__(self):
        """Initialize the graph builder."""
        self.graph = MatlabGraph()
        self._node_cache: Dict[Tuple[str, str], str] = {}  # (name, type) -> node_id
        self._current_file: Optional[str] = None
    
    def _generate_node_id(self, name: str, node_type: MatlabNodeType) -> str:
        """Generate a unique node ID."""
        return f"{node_type.value}:{name}@{self._current_file or 'global'}"
    
    def _add_node(
        self,
        name: str,
        node_type: MatlabNodeType,
        file_path: str,
        code: str,
        start_line: int,
        end_line: int,
        start_col: int = 0,
        end_col: int = 0,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Add a node to the graph.
        
        Args:
            name: Name of the node (function name, variable name, etc.)
            node_type: Type of the node
            file_path: Path to the source file
            code: The source code of the node
            start_line: Starting line number
            end_line: Ending line number
            start_col: Starting column (default: 0)
            end_col: Ending column (default: 0)
            parent_id: ID of the parent node (for nested elements)
            metadata: Additional metadata for the node
            
        Returns:
            The ID of the created node
        """
        node_id = self._generate_node_id(name, node_type)
        
        # If node already exists, return its ID
        if node_id in self.graph.nodes:
            return node_id
        
        # Create position and range objects
        start_pos = Position(line=start_line, column=start_col)
        end_pos = Position(line=end_line, column=end_col)
        code_range = CodeRange(start=start_pos, end=end_pos)
        
        # Create and add the node
        node = MatlabNode(
            id=node_id,
            name=name,
            node_type=node_type,
            file_path=file_path,
            code=code,
            range=code_range,
            parent_id=parent_id,
            metadata=metadata or {}
        )
        
        self.graph.add_node(node)
        self._node_cache[(name, node_type.value)] = node_id
        
        # If this is a nested element, add a 'contains' edge from parent
        if parent_id and parent_id in self.graph.nodes:
            self.graph.add_edge(parent_id, node_id, RelationshipType.CONTAINS)
        
        return node_id
    
    def _extract_function_signature(self, code: str) -> dict:
        """Extract function signature information from function code."""
        # This is a simplified implementation
        # In a real implementation, you'd want to parse the full signature
        signature = {
            'name': 'unknown',
            'input_args': [],
            'output_args': []
        }
        
        # Simple regex to match function signatures
        func_match = re.match(
            r'^\s*function\s+(?:\[\s*([^\]]*?)\s*\]\s*=\s*)?([a-zA-Z_]\w*)\s*\(([^)]*)\)',
            code
        )
        
        if func_match:
            output_args = func_match.group(1) or ''
            signature['name'] = func_match.group(2)
            signature['input_args'] = [arg.strip() for arg in func_match.group(3).split(',') if arg.strip()]
            signature['output_args'] = [arg.strip() for arg in output_args.split(',') if arg.strip()]
        
        return signature
    
    def _process_file(self, file_path: str) -> None:
        """Process a single MATLAB file and add its elements to the graph."""
        try:
            parser = MATLABASTParser(file_path)
            self._current_file = file_path
            
            # Add the file as a script node
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
            except UnicodeDecodeError:
                # Try with different encodings if UTF-8 fails
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        file_content = f.read()
                except Exception as e:
                    print(f"Failed to read file {file_path}: {str(e)}")
                    return
            
            file_name = Path(file_path).name
            file_node_id = self._add_node(
                name=file_name,
                node_type=MatlabNodeType.SCRIPT,
                file_path=file_path,
                code=file_content,
                start_line=1,
                end_line=len(file_content.splitlines()) or 1,
                metadata={'file_path': file_path}
            )
            
            try:
                # Process functions
                functions = parser.get_functions()
                for func in functions:
                    self._process_function(func, file_path, file_node_id)
                
                # Process classes
                classes = parser.get_classes()
                for cls in classes:
                    self._process_class(cls, file_path, file_node_id)
                
                # Process global variables
                variables = parser.get_variables()
                for var in variables:
                    self._process_variable(var, file_path, file_node_id)
                    
            except Exception as e:
                print(f"Error processing file {file_path}: {str(e)}")
                import traceback
                traceback.print_exc()
            
        except Exception as e:
            print(f"Error initializing parser for {file_path}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _process_function(
        self,
        func: Dict,
        file_path: str,
        parent_id: str
    ) -> None:
        """Process a function definition and add it to the graph."""
        func_name = func.get('name', 'anonymous')
        start_line = func['location']['start']['line']
        end_line = func['location']['end']['line']
        
        # Get function code
        func_code = '\n'.join(self._get_code_lines(file_path, start_line, end_line))
        
        # Add function node
        func_node_id = self._add_node(
            name=func_name,
            node_type=MatlabNodeType.FUNCTION,
            file_path=file_path,
            code=func_code,
            start_line=start_line,
            end_line=end_line,
            parent_id=parent_id,
            metadata={
                'signature': self._extract_function_signature(func_code)
            }
        )
        
        # Process function calls within this function
        self._process_function_calls(func_code, func_node_id, file_path, start_line)
    
    def _process_class(
        self,
        cls: Dict,
        file_path: str,
        parent_id: str
    ) -> None:
        """Process a class definition and add it to the graph."""
        class_name = cls.get('name', 'AnonymousClass')
        start_line = cls['location']['start']['line']
        end_line = cls['location']['end']['line']
        
        # Get class code
        class_code = '\n'.join(self._get_code_lines(file_path, start_line, end_line))
        
        # Add class node
        class_node_id = self._add_node(
            name=class_name,
            node_type=MatlabNodeType.CLASS,
            file_path=file_path,
            code=class_code,
            start_line=start_line,
            end_line=end_line,
            parent_id=parent_id
        )
        
        # In a real implementation, you would process methods and properties here
        # and add them as child nodes with appropriate relationships
    
    def _process_variable(
        self,
        var: Dict,
        file_path: str,
        parent_id: str
    ) -> None:
        """Process a variable declaration and add it to the graph.
        
        Args:
            var: Dictionary containing variable information
            file_path: Path to the source file
            parent_id: ID of the parent node
        """
        var_name = var.get('name', 'unnamed_var')
        start_line = var['location']['start']['line']
        end_line = var['location']['end']['line']
        
        # Get all occurrences of this variable in the file
        all_occurrences = []
        # Use a large number instead of float('inf') for end_line
        lines = self._get_code_lines(file_path, 1, 1000000)  # 1 million lines should be enough
        for i, line in enumerate(lines, 1):
            # Find all occurrences of the variable in this line
            for match in re.finditer(r'\b' + re.escape(var_name) + r'\b', line):
                all_occurrences.append({
                    'line': i,
                    'col': match.start() + 1,
                    'code': line.strip()
                })
        
        # If no occurrences found, use the original location
        if not all_occurrences:
            all_occurrences = [{
                'line': start_line,
                'col': var['location']['start']['column'],
                'code': '\n'.join(self._get_code_lines(file_path, start_line, start_line)).strip()
            }]
        
        # Create a list of all line numbers where this variable appears
        line_numbers = [occ['line'] for occ in all_occurrences]
        
        # Add variable node with all occurrences
        self._add_node(
            name=var_name,
            node_type=MatlabNodeType.VARIABLE,
            file_path=file_path,
            code='\n'.join(occ['code'] for occ in all_occurrences[:5]),  # Include first 5 occurrences in code
            start_line=min(line_numbers) if line_numbers else start_line,
            end_line=max(line_numbers) if line_numbers else end_line,
            parent_id=parent_id,
            metadata={
                'all_occurrences': all_occurrences,
                'total_occurrences': len(all_occurrences)
            }
        )
    
    def _process_function_calls(
        self,
        code: str,
        caller_id: str,
        file_path: str,
        offset_line: int = 0
    ) -> None:
        """
        Process function calls within a block of code and add call edges to the graph.
        
        Args:
            code: The source code to analyze for function calls
            caller_id: ID of the node that contains this code
            file_path: Path to the source file (for error reporting)
            offset_line: Line number offset for the start of the code block
        """
        # This is a simplified implementation
        # In a real implementation, you'd want to use a proper parser
        
        # Pattern to match function calls: functionName(...)
        pattern = re.compile(r'([a-zA-Z_]\w*)\s*\(')
        
        for line_num, line in enumerate(code.splitlines(), 1 + offset_line):
            for match in pattern.finditer(line):
                callee_name = match.group(1)
                
                # Skip keywords that look like function calls
                if callee_name.lower() in ['if', 'for', 'while', 'switch', 'try', 'catch', 'function', 'classdef', 'end']:
                    continue
                
                # Try to find the callee node
                callee_id = None
                
                # First, check if we've seen a function with this name
                if (callee_name, 'function') in self._node_cache:
                    callee_id = self._node_cache[(callee_name, 'function')]
                # Then check for methods
                elif (callee_name, 'method') in self._node_cache:
                    callee_id = self._node_cache[(callee_name, 'method')]
                # Then check for built-in MATLAB functions
                else:
                    # In a real implementation, you'd check against a list of MATLAB built-ins
                    # For now, we'll create a placeholder node for the callee
                    callee_id = self._add_node(
                        name=callee_name,
                        node_type=MatlabNodeType.FUNCTION,  # Assume it's a function
                        file_path='builtin',
                        code=f'% Built-in function: {callee_name}',
                        start_line=0,
                        end_line=0
                    )
                
                # Add call edge
                if callee_id:
                    self.graph.add_edge(caller_id, callee_id, RelationshipType.CALLS, {
                        'location': f"{file_path}:{line_num}"
                    })
    
    def _get_code_lines(self, file_path: str, start_line: int, end_line: int) -> List[str]:
        """Get lines of code from a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return [line.strip('\n') for line in f.readlines()[start_line-1:end_line]]
        except Exception as e:
            print(f"Error reading lines from {file_path}: {str(e)}")
            return []
    
    def build_from_file(self, file_path: str) -> MatlabGraph:
        """
        Build a graph from a MATLAB file.
        
        Args:
            file_path: Path to the MATLAB file
            
        Returns:
            A MatlabGraph representing the code structure
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        self._process_file(file_path)
        return self.graph
    
    def build_from_directory(self, dir_path: str, pattern: str = '*.m') -> MatlabGraph:
        """
        Build a graph from all MATLAB files in a directory.
        
        Args:
            dir_path: Path to the directory containing MATLAB files
            pattern: File pattern to match (default: '*.m')
            
        Returns:
            A MatlabGraph representing the code structure
        """
        if not os.path.isdir(dir_path):
            raise NotADirectoryError(f"Directory not found: {dir_path}")
        
        # Process all .m files in the directory
        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.endswith('.m'):
                    file_path = os.path.join(root, file)
                    try:
                        self._process_file(file_path)
                    except Exception as e:
                        print(f"Error processing {file_path}: {str(e)}")
        
        return self.graph
