import json
import logging
import re
import os
import traceback
from typing import Any, Dict, List, Tuple, Set

log = logging.getLogger(__name__)

# Constants for output formatting, matching graph_extractor
DEFAULT_TUPLE_DELIMITER = "<|>"
DEFAULT_RECORD_DELIMITER = ">>"

# Basic MATLAB keywords and built-in functions to ignore as variables
MATLAB_KEYWORDS = {
    "if", "else", "elseif", "end", "for", "while", "switch", "case", "otherwise",
    "try", "catch", "function", "return", "global", "persistent", "classdef",
    "properties", "methods", "events", "parfor", "spmd"
}
MATLAB_BUILTINS = {
    "disp", "plot", "figure", "zeros", "ones", "eye", "rand", "randn", "size", "length",
    "xlabel", "ylabel", "title", "legend", "hold", "grid", "subplot", "imread", "imwrite",
    "fopen", "fclose", "fprintf", "fscanf", "textscan", "input", "error", "warning",
    "clear", "clc", "whos", "save", "load", "exist", "nargin", "nargout", "varargin", "varargout",
    "sum", "mean", "std", "min", "max", "abs", "sqrt", "exp", "log", "log10", "sin", "cos", "tan",
    "asin", "acos", "atan", "atan2", "round", "floor", "ceil", "fix", "mod", "rem"
}

# Common English words that might be picked up by regex but are not usually variables
COMMON_WORDS_TO_IGNORE = {
    "assign", "assigns", "define", "defines", "use", "uses", "variable", "variables", 
    "parameter", "parameters", "input", "inputs", "output", "outputs", "script", 
    # "function", # function is a keyword, already handled by MATLAB_KEYWORDS
    "local", "global", "calculation", "value", "result", "test", "file",
    "path", "content", "line", "range", "preview", "dependencies", "generates", "description",
    "type", "id", "source", "target", "label", "node", "edge", "graph", "element", "elements",
    # Words often found in comments or as contextual keywords that aren't standalone variables
    "start", "if", "for", "while", "loop", "iter", "count", "index", "idx", "step", "endfor", "endif",
    # Common loop iterators (often single letters)
    "i", "j", "k", "m", "n", "x", "y", "z" # Add more if needed, but be cautious with single letters
}

class MATLABASTParser:
    def __init__(self, text: str, path: str):
        self.text = text
        self.path = path
        self.lines = text.splitlines()
        self.nodes: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, Any]] = []
        self.variable_occurrences: Dict[str, List[Tuple[int, str]]] = {}
        self.known_function_names: Set[str] = set() # Store script and function names

    def _find_line_range(self, content_snippet: str) -> str:
        """Finds the line range of a snippet within the full text."""
        try:
            start_index = self.text.index(content_snippet)
            end_index = start_index + len(content_snippet)
            start_line = self.text.count('\n', 0, start_index) + 1
            end_line = self.text.count('\n', 0, end_index) + 1
            return f"{start_line}-{end_line}"
        except ValueError:
            return "unknown"

    def _is_valid_variable(self, var_name: str) -> bool:
        if not var_name or not var_name[0].isalpha() and var_name[0] != '_':
            return False # Must start with a letter or underscore
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", var_name):
            return False # Invalid characters
        if var_name in MATLAB_KEYWORDS or var_name in MATLAB_BUILTINS or var_name.lower() in COMMON_WORDS_TO_IGNORE:
            return False
        if var_name in self.known_function_names: # Check against known script/function names
            return False
        # Filter out multi-level names like 's.field', keep only 's'
        # Also filter out function calls like 'myFunc(arg)' being mistaken for variables.
        if '.' in var_name or '(' in var_name or ')' in var_name:
            return False
        return True

    def _extract_variables_from_line(self, line_content: str, line_num: int):
        # Regex to find potential variable assignments (LHS) and usages (RHS)
        potential_vars = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', line_content)
        
        line_no_comments = line_content.split('%')[0].strip()
        if not line_no_comments:
            return

        for var_name in potential_vars:
            if self._is_valid_variable(var_name):
                if var_name not in self.variable_occurrences:
                    self.variable_occurrences[var_name] = []
                self.variable_occurrences[var_name].append((line_num, line_no_comments))

    def parse(self):
        script_name = os.path.splitext(os.path.basename(self.path))[0]
        self.known_function_names.add(script_name) # Add script name to prevent it being a var
        
        script_node_name = f"SCRIPT_{script_name.upper()}"
        script_description = {
            "script_name": script_name,
            "file_path": self.path,
            "line_range": f"1-{len(self.lines)}",
            "content_preview": "\n".join(self.lines[:20]),
            "dependencies": [], 
            "generates": [] 
        }
        self.nodes.append({
            "id": script_node_name,
            "type": "script",
            "description": json.dumps(script_description)
        })

        for i, line in enumerate(self.lines):
            self._extract_variables_from_line(line, i + 1)

        current_function_name = None
        current_function_content: List[str] = []
        current_function_start_line = -1
        current_func_params_str = ""
        current_func_outputs_str = ""
        
        # Store function details to process variable links later
        parsed_functions: List[Dict[str, Any]] = []

        for i, line_content in enumerate(self.lines):
            line_num = i + 1
            stripped_line = line_content.strip()

            func_match = re.match(r"^\s*function(?:\s+\[?([\w\s,]+)\]?)?\s*=\s*(\w+)\s*\(([^)]*)\)", stripped_line)
            if func_match:
                if current_function_name: 
                    func_desc = {
                        "function_name": current_function_name,
                        "file_path": self.path,
                        "line_range": f"{current_function_start_line}-{line_num-1}",
                        "content": "\n".join(current_function_content),
                        "parameters": current_func_params_str, 
                        "outputs": current_func_outputs_str 
                    }
                    self.nodes.append({"id": f"FUNCTION_{current_function_name.upper()}", "type": "function", "description": json.dumps(func_desc)})
                    self.edges.append({"source": script_node_name, "target": f"FUNCTION_{current_function_name.upper()}", "label": "defines_function"})
                    parsed_functions.append({
                        "name": current_function_name,
                        "id": f"FUNCTION_{current_function_name.upper()}",
                        "start_line": current_function_start_line,
                        "end_line": line_num,
                        "params": current_func_params_str.split(',') if current_func_params_str else [],
                        "outputs": current_func_outputs_str.split(',') if current_func_outputs_str else []
                    })
                    current_function_name = None 
                    current_function_content = []
                    current_function_start_line = -1
        
                outputs, func_name_from_match, params = func_match.groups()
                current_function_name = func_name_from_match 
                self.known_function_names.add(current_function_name) # Add to known function names
                current_func_outputs_str = outputs.strip() if outputs else ""
                current_func_params_str = params.strip() if params else ""
                current_function_content = [line_content]
                current_function_start_line = line_num
            elif current_function_name:
                current_function_content.append(line_content)
                if re.match(r"^\s*end\s*(?:%.*)?$", stripped_line):
                    func_desc = {
                        "function_name": current_function_name,
                        "file_path": self.path,
                        "line_range": f"{current_function_start_line}-{line_num}",
                        "content": "\n".join(current_function_content),
                        "parameters": current_func_params_str,
                        "outputs": current_func_outputs_str
                    }
                    self.nodes.append({"id": f"FUNCTION_{current_function_name.upper()}", "type": "function", "description": json.dumps(func_desc)})
                    self.edges.append({"source": script_node_name, "target": f"FUNCTION_{current_function_name.upper()}", "label": "defines_function"})
                    parsed_functions.append({
                        "name": current_function_name,
                        "id": f"FUNCTION_{current_function_name.upper()}",
                        "start_line": current_function_start_line,
                        "end_line": line_num,
                        "params": current_func_params_str.split(',') if current_func_params_str else [],
                        "outputs": current_func_outputs_str.split(',') if current_func_outputs_str else []
                    })
                    current_function_name = None 
                    current_function_content = []
                    current_function_start_line = -1
        
        if current_function_name:
            func_desc = {
                "function_name": current_function_name,
                "file_path": self.path,
                "line_range": f"{current_function_start_line}-{len(self.lines)}",
                "content": "\n".join(current_function_content),
                "parameters": current_func_params_str,
                "outputs": current_func_outputs_str
            }
            self.nodes.append({"id": f"FUNCTION_{current_function_name.upper()}", "type": "function", "description": json.dumps(func_desc)})
            self.edges.append({"source": script_node_name, "target": f"FUNCTION_{current_function_name.upper()}", "label": "defines_function"})
            parsed_functions.append({
                "name": current_function_name,
                "id": f"FUNCTION_{current_function_name.upper()}",
                "start_line": current_function_start_line,
                "end_line": len(self.lines),
                "params": current_func_params_str.split(',') if current_func_params_str else [],
                "outputs": current_func_outputs_str.split(',') if current_func_outputs_str else []
            })

        # Create variable nodes and script->variable edges
        for var_name, occurrences in self.variable_occurrences.items():
            if not occurrences: continue
            var_desc = {
                "variable_name": var_name,
                "file_path": self.path,
                "occurrences": [(f"L{loc[0]}", loc[1]) for loc in occurrences],
                "dependencies": [] 
            }
            var_node_name = f"VARIABLE_{var_name.upper()}"
            self.nodes.append({
                "id": var_node_name,
                "type": "variable",
                "description": json.dumps(var_desc)
            })
            # Rudimentary edge: variable used in script (general existence)
            self.edges.append({"source": script_node_name, "target": var_node_name, "label": "declares_variable", "weight": 1.0})

        # Create function->variable edges
        for func_info in parsed_functions:
            func_node_id = func_info["id"]
            func_start = func_info["start_line"]
            func_end = func_info["end_line"]
            
            # Include function parameters and output variables as used by the function
            func_param_names = {p.strip() for p in func_info["params"] if p.strip()}
            func_output_names = {o.strip() for o in func_info["outputs"] if o.strip()}
            
            # Add edges for parameters
            for param_name in func_param_names:
                if self._is_valid_variable(param_name): # Check if it's a valid var name (not keyword etc)
                    var_node_name = f"VARIABLE_{param_name.upper()}"
                    # Ensure variable node exists (it should if _extract_variables_from_line worked)
                    if any(n['id'] == var_node_name for n in self.nodes):
                         self.edges.append({"source": func_node_id, "target": var_node_name, "label": "uses_parameter", "weight": 1.0})
                    else: # Create if somehow missed (e.g. only in signature)
                        # Only add if it's not a function name itself (edge case)
                        if param_name not in self.known_function_names:
                            var_desc_simple = {"variable_name": param_name, "file_path": self.path, "occurrences": [(f"L{func_start}", "parameter declaration")]}
                            self.nodes.append({"id": var_node_name, "type": "variable", "description": json.dumps(var_desc_simple)})
                            self.edges.append({"source": func_node_id, "target": var_node_name, "label": "uses_parameter", "weight": 1.0})

            # Add edges for output variables
            for output_name in func_output_names:
                if self._is_valid_variable(output_name):
                    var_node_name = f"VARIABLE_{output_name.upper()}"
                    if any(n['id'] == var_node_name for n in self.nodes):
                        self.edges.append({"source": func_node_id, "target": var_node_name, "label": "assigns_output", "weight": 1.0})
                    else: # Create if somehow missed
                        if output_name not in self.known_function_names:
                            var_desc_simple = {"variable_name": output_name, "file_path": self.path, "occurrences": [(f"L{func_start}", "output declaration")]}
                            self.nodes.append({"id": var_node_name, "type": "variable", "description": json.dumps(var_desc_simple)})
                            self.edges.append({"source": func_node_id, "target": var_node_name, "label": "assigns_output", "weight": 1.0})

            # Add edges for variables used within the function body
            for var_name, occurrences in self.variable_occurrences.items():
                # Skip if it's a parameter or output var, already handled
                if var_name in func_param_names or var_name in func_output_names:
                    continue

                var_node_name = f"VARIABLE_{var_name.upper()}"
                for occ_line, _ in occurrences:
                    if func_start <= occ_line <= func_end:
                        # Ensure variable node exists
                        if any(n['id'] == var_node_name for n in self.nodes):
                            # Avoid duplicate edges to the same variable from the same function
                            if not any(e['source'] == func_node_id and e['target'] == var_node_name and e['label'] == "uses_variable" for e in self.edges):
                                self.edges.append({"source": func_node_id, "target": var_node_name, "label": "uses_variable", "weight": 1.0})
                            break # Found an occurrence in this function, no need to check other occurrences for this var-func pair

    def format_output(self) -> str:
        output_parts = []
        for node in self.nodes:
            output_parts.append(f'"entity"{DEFAULT_TUPLE_DELIMITER}{node["id"]}{DEFAULT_TUPLE_DELIMITER}{node["type"]}{DEFAULT_TUPLE_DELIMITER}{node["description"]}{DEFAULT_TUPLE_DELIMITER}{DEFAULT_TUPLE_DELIMITER}0.0')
        
        for edge in self.edges:
            edge_desc_str = edge.get("description", json.dumps({"label": edge.get("label", "related_to")}))
            if not isinstance(edge_desc_str, str):
                 edge_desc_str = json.dumps(edge_desc_str)
            output_parts.append(f'"relationship"{DEFAULT_TUPLE_DELIMITER}{edge["source"]}{DEFAULT_TUPLE_DELIMITER}{edge["target"]}{DEFAULT_TUPLE_DELIMITER}{edge_desc_str}{DEFAULT_TUPLE_DELIMITER}{DEFAULT_TUPLE_DELIMITER}{edge.get("weight", 1.0)}')
        
        return DEFAULT_RECORD_DELIMITER.join(output_parts)

def analyze_matlab_code(text: str, path: str) -> str:
    """
    Analyzes MATLAB code from text and path, extracts graph elements (nodes, edges),
    and returns them in a string format compatible with GraphExtractor._process_document output.
    """
    try:
        log.info(f"Starting MATLAB AST parsing for: {path}")
        parser = MATLABASTParser(text, path)
        parser.parse()
        output_string = parser.format_output()
        log.info(f"Finished MATLAB AST parsing for: {path}. Found {len(parser.nodes)} nodes, {len(parser.edges)} edges.")
        return output_string
    except Exception as e:
        log.error(f"Error during MATLAB code analysis for {path}: {e}\n{traceback.format_exc()}")
        return "" 

def _parse_output_to_graph_elements(output_string: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parses the string output from analyze_matlab_code into lists of nodes and edges."""
    nodes = []
    edges = []
    if not output_string:
        return nodes, edges

    records = [r.strip() for r in output_string.split(DEFAULT_RECORD_DELIMITER)]

    for record in records:
        if not record: # Skip empty records that might result from trailing delimiters
            continue
        # No need to re.sub(r"^\(|\)$", "", record.strip()) as in graph_extractor, 
        # because our format_output doesn't add these parentheses.
        record_attributes = record.split(DEFAULT_TUPLE_DELIMITER)

        record_type = record_attributes[0].strip('"') # Remove quotes from "entity" or "relationship"

        if record_type == 'entity' and len(record_attributes) >= 4:
            node_id = record_attributes[1]
            node_type = record_attributes[2]
            node_description_str = record_attributes[3]
            try:
                node_description = json.loads(node_description_str)
            except json.JSONDecodeError:
                node_description = {"raw_description": node_description_str} # Fallback
            
            nodes.append({
                "id": node_id,
                "type": node_type,
                "description": node_description
                # "source_doc_id": record_attributes[4] if len(record_attributes) > 4 else None, # We don't use this here
                # "score": float(record_attributes[5]) if len(record_attributes) > 5 else 0.0 # We don't use this here
            })
        elif record_type == 'relationship' and len(record_attributes) >= 6: # Expect 6 parts for relationship with weight
            source_id = record_attributes[1]
            target_id = record_attributes[2]
            edge_description_str = record_attributes[3]
            # record_attributes[4] is the empty string placeholder for source_doc_id
            edge_weight = float(record_attributes[5])
            try:
                edge_description = json.loads(edge_description_str)
            except json.JSONDecodeError:
                edge_description = {"raw_label": edge_description_str} # Fallback

            edges.append({
                "source": source_id,
                "target": target_id,
                "description": edge_description,
                "weight": edge_weight
            })
        else:
            log.warning(f"Skipping malformed record: {record}")
            
    return nodes, edges

if __name__ == '__main__':
    dummy_m_content = """
    % This is a test script
    a = 10; % assign a
    b = a + 5; % assign b
    disp(b); % uses b

    function y = myFunction(x) % defines myFunction
        % This is a test function
        y = x * 2; % calculation, uses x, assigns y
        disp(y); % uses y
        c = 30; % local variable, assigns c
        if y > 10 % start if, uses y
            disp('Big Y');
        end % end if
    end % end function myFunction

    function [out1, out2] = anotherFunc(in1, in2, in3) % defines anotherFunc
        % This is another function
        out1 = in1 + in2; % uses in1, in2, assigns out1
        out2 = in3 * 5; % uses in3, assigns out2
        if out1 > 10 % start if, uses out1
            for k = 1:out1 % start for, uses out1, assigns k
                out2 += k; % uses k
            end % end for
        end % end if
    end % end function anotherFunc

    myFunction(b); % call function, uses b, myFunction
    anotherFunc(1,2,3); % call function, uses anotherFunc
    d = 40; % assigns d
    % Test script level end
    % end 
    """
    dummy_m_path = "test_script.m"
    
    with open(dummy_m_path, "w") as f:
        f.write(dummy_m_content)

    print(f"--- Testing analyze_matlab_code with {dummy_m_path} ---")
    result_string = analyze_matlab_code(dummy_m_content, dummy_m_path)
    print("--- Raw Output String ---")
    print(result_string)
    print("--- Parsed Graph Elements ---")
    nodes, edges = _parse_output_to_graph_elements(result_string)
    
    print("\n--- NODES ---")
    printed_node_ids = set()
    for node in nodes:
        if node['id'] not in printed_node_ids:
            print(f"  ID: {node['id']}")
            print(f"    Type: {node['type']}")
            print(f"    Description: {json.dumps(node['description'], indent=2)}")
            print("")
            printed_node_ids.add(node['id'])

    print("\n--- EDGES ---")
    for edge in edges:
        print(f"  Source: {edge['source']}")
        print(f"    Target: {edge['target']}")
        print(f"    Description: {json.dumps(edge['description'], indent=2)}")
        print(f"    Weight: {edge['weight']:.1f}")
        print("")

    print("--- End of Test ---")

    print(printed_node_ids)

    if os.path.exists(dummy_m_path):
        os.remove(dummy_m_path)
