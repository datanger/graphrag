import json
import logging
import re
import os
import traceback
from typing import Any, Dict, List, Tuple, Set
from collections import defaultdict

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
    "start", "if", "for", "while", "loop", "iter", "count", "index", "idx", "step", "endfor", "endif"
    # Removed common iterators like i,j,k,x,y,z to allow them as variables
}

class MATLABASTParser:
    def __init__(self, text: str, path: str):
        self.text = text
        self.path = path
        self.lines = text.splitlines()
        self.nodes: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, Any]] = []
        self.variable_occurrences: Dict[str, List[Tuple[int, str]]] = defaultdict(list)
        self.function_parameters: Dict[str, List[str]] = defaultdict(list)
        self.known_function_names: Set[str] = set()  # Store script and function names
        self.variable_dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.script_level_vars: Set[str] = set()

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
        if not var_name or not (var_name[0].isalpha() or var_name[0] == '_'):
            return False  # Must start with a letter or underscore
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", var_name):
            return False  # Invalid characters
        if var_name in MATLAB_KEYWORDS or var_name in MATLAB_BUILTINS or var_name.lower() in COMMON_WORDS_TO_IGNORE:
            return False
        if var_name in self.known_function_names:  # Check against known script/function names
            return False
        # Filter out multi-level names and function calls
        if '.' in var_name or '(' in var_name or ')' in var_name:
            return False
        return True

    def _extract_variables_from_line(self, line_content: str, line_num: int):
        # Remove string literals first to avoid matching words inside them
        line_no_strings = re.sub(r"'.*?'", "''", line_content)  # Replace string literals with empty strings
        line_no_comments = line_no_strings.split('%')[0].strip()
        
        if not line_no_comments:
            return

        # --- Dependency Extraction from Assignments ---
        # Single LHS: var = ...
        assignment_match_single = re.match(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.*)", line_no_comments)
        # Multiple LHS: [var1, var2] = ...
        assignment_match_multi = re.match(r"^\s*\[\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\s*,\s*[a-zA-Z_][a-zA-Z0-9_]*)*)\s*\]\s*=\s*(.*)", line_no_comments)

        lhs_vars_on_line = []
        rhs_expression_str = ""

        if assignment_match_single:
            lhs_var = assignment_match_single.group(1)
            if self._is_valid_variable(lhs_var): # Check if LHS is a valid var name
                lhs_vars_on_line.append(lhs_var)
            rhs_expression_str = assignment_match_single.group(2)
        elif assignment_match_multi:
            lhs_vars_str = assignment_match_multi.group(1)
            temp_lhs_list = [v.strip() for v in lhs_vars_str.split(',')]
            for v_lhs in temp_lhs_list:
                if self._is_valid_variable(v_lhs):
                    lhs_vars_on_line.append(v_lhs)
            rhs_expression_str = assignment_match_multi.group(2)
        
        if rhs_expression_str and lhs_vars_on_line:
            # Extract potential variables from RHS
            potential_rhs_vars = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', rhs_expression_str)
            actual_rhs_vars = set()
            for p_rhs_var in potential_rhs_vars:
                if self._is_valid_variable(p_rhs_var) and p_rhs_var not in lhs_vars_on_line: # Avoid self-dependency like a=a+1 here
                    actual_rhs_vars.add(p_rhs_var)
            
            for lhs_v in lhs_vars_on_line:
                self.variable_dependencies[lhs_v].update(actual_rhs_vars)
        # --- End Dependency Extraction ---

        # Find all potential variables (words that could be variables) for occurrence tracking
        potential_vars = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', line_no_comments)
        
        # Find all function calls (words followed by '(' that aren't keywords)
        function_calls = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', line_no_comments)
        for func in function_calls:
            if func not in self.known_function_names and func not in MATLAB_BUILTINS and func not in MATLAB_KEYWORDS:
                # Add function calls to known functions to prevent them from being treated as variables
                self.known_function_names.add(func)

        for var_name in potential_vars:
            if self._is_valid_variable(var_name):
                if var_name not in self.variable_occurrences:
                    self.variable_occurrences[var_name] = []
                self.variable_occurrences[var_name].append((line_num, line_no_comments))

    def parse(self):
        script_name = os.path.splitext(os.path.basename(self.path))[0]
        self.known_function_names.add(script_name) # Add script name to prevent it being a var

        # Pass 1: Pre-scan for all function definitions to populate known_function_names
        # This helps _is_valid_variable correctly identify function calls on RHS of assignments
        for line_content_pass1 in self.lines:
            stripped_line_pass1 = line_content_pass1.strip()
            # Regex to capture function name: function [outputs] = funcName(inputs)
            func_match_pass1 = re.match(r"^\s*function(?:\s+\[?([\w\s,]+)\]?)?\s*=\s*(\w+)\s*\(([^)]*)\)", stripped_line_pass1)
            if func_match_pass1:
                # group(2) is the function name based on the regex structure
                _, func_name_from_match_pass1, _ = func_match_pass1.groups()
                if func_name_from_match_pass1:
                     self.known_function_names.add(func_name_from_match_pass1)
        
        script_node_name = f"SCRIPT_{script_name.upper()}"
        script_line_range = f"1-{len(self.lines)}"
        script_content_preview = "\n".join(self.lines[:20])
        script_description = {
            "script_name": script_name,
            "file_path": self.path,
            "occurrences": [{
                "line_range": script_line_range,
                "content": script_content_preview
            }],
            "dependencies": [], # Script node itself doesn't have dependencies in this context
            "generates": [] 
        }
        self.nodes.append({
            "id": script_node_name,
            "type": "script",
            "description": json.dumps(script_description)
        })

        # Pass 2: Extract variables and dependencies now that all function names are known
        for i, line in enumerate(self.lines):
            self._extract_variables_from_line(line, i + 1)

        # Pass 3: Function structure parsing, node/edge creation for functions
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
                    func_line_range = f"{current_function_start_line}-{line_num-1}"
                    func_content = "\n".join(current_function_content)
                    func_desc = {
                        "function_name": current_function_name,
                        "file_path": self.path,
                        "occurrences": [{
                            "line_range": func_line_range,
                            "content": func_content
                        }],
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
                
                # Register function parameters
                if current_func_params_str:
                    params_list = [p.strip() for p in current_func_params_str.split(',') if p.strip()]
                    self.function_parameters[current_function_name] = params_list
                    
                    for param in params_list:
                        # Add edge from function to parameter
                        param_id = f"VARIABLE_{param.upper()}"
                        self.edges.append({
                            "source": f"FUNCTION_{current_function_name.upper()}",
                            "target": param_id,
                            "label": "has_parameter",
                            "weight": 1.0
                        })
                        
                        # Initialize variable occurrence if not exists
                        if param not in self.variable_occurrences:
                            self.variable_occurrences[param] = []
                        # Add the parameter declaration as an occurrence
                        self.variable_occurrences[param].append((line_num, f"function {current_function_name} parameter: {param}"))
                
                current_function_content = [line_content]
                current_function_start_line = line_num
            elif current_function_name:
                current_function_content.append(line_content)
                if re.match(r"^\s*end\s*(?:%.*)?$", stripped_line):
                    func_line_range = f"{current_function_start_line}-{line_num}"
                    func_content = "\n".join(current_function_content)
                    func_desc = {
                        "function_name": current_function_name,
                        "file_path": self.path,
                        "occurrences": [{
                            "line_range": func_line_range,
                            "content": func_content
                        }],
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
        
        if current_function_name: # Process the last function if file ends mid-function
            func_line_range = f"{current_function_start_line}-{len(self.lines)}"
            func_content = "\n".join(current_function_content)
            func_desc = {
                "function_name": current_function_name,
                "file_path": self.path,
                "occurrences": [{
                    "line_range": func_line_range,
                    "content": func_content
                }],
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

        # Determine script-level variables for 'declares_variable' edge
        for var_name_scope, occurrences_list_scope in self.variable_occurrences.items():
            is_script_level_var = False
            for occ_line_num, _ in occurrences_list_scope:
                is_in_any_function = False
                for func_info_scope in parsed_functions:
                    if func_info_scope["start_line"] <= occ_line_num <= func_info_scope["end_line"]:
                        is_in_any_function = True
                        break
                if not is_in_any_function:
                    is_script_level_var = True
                    break
            if is_script_level_var:
                self.script_level_vars.add(var_name_scope)

        # Create variable nodes and script->variable edges
        for var_name, occurrences_list in self.variable_occurrences.items():
            if not occurrences_list: continue
            var_desc = {
                "variable_name": var_name,
                "file_path": self.path,
                "occurrences": [{"line_range": f"L{loc[0]}", "content": loc[1]} for loc in occurrences_list],
                "dependencies": sorted(list(self.variable_dependencies.get(var_name, set())))
            }
            var_node_name = f"VARIABLE_{var_name.upper()}"
            self.nodes.append({
                "id": var_node_name,
                "type": "variable",
                "description": json.dumps(var_desc)
            })
            # Rudimentary edge: variable used in script (general existence)
            if var_name in self.script_level_vars: # Only add if it's a script-level variable
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
                            var_desc_simple = {
                                "variable_name": param_name, 
                                "file_path": self.path, 
                                "occurrences": [{
                                    "line_range": f"L{func_start}", 
                                    "content": "parameter declaration"
                                }]
                            }
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
                            var_desc_simple = {
                                "variable_name": output_name, 
                                "file_path": self.path, 
                                "occurrences": [{
                                    "line_range": f"L{func_start}", 
                                    "content": "output declaration"
                                }]
                            }
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
