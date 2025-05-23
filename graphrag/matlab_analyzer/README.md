# MATLAB Analyzer for GraphRAG

This module extends GraphRAG to analyze MATLAB code and build a graph representation of its structure. It parses MATLAB code to extract scripts, functions, classes, methods, and variables, and represents their relationships in a graph.

## Features

- Parse MATLAB code files (`.m` files)
- Extract the following code elements as nodes:
  - Scripts
  - Functions
  - Classes
  - Methods
  - Variables
- Represent relationships between code elements as edges:
  - Function calls
  - Containment (e.g., class contains methods)
  - Variable usage
- Preserve code context including file paths and line numbers
- Generate a graph that can be used for code analysis and visualization
- Seamless integration with GraphRAG for advanced code understanding and querying

## Installation

1. Ensure you have Python 3.7+ installed
2. Install the required dependencies:

```bash
pip install pydantic networkx
```

3. (Optional) For better parsing of MATLAB code, you may want to install the MATLAB Engine API for Python:
   - Install MATLAB
   - Run the following command in MATLAB:
     ```matlab
     cd (fullfile(matlabroot,'extern','engines','python'))
     system('python setup.py install')
     ```

## Integration with GraphRAG

The MATLAB Analyzer can be used to generate a graph that can be loaded into GraphRAG for advanced code understanding and querying.

### Loading a MATLAB Graph into GraphRAG

1. First, generate a graph from your MATLAB code:

```python
from graphrag.matlab_analyzer import MATLABGraphBuilder

# Create a graph builder
builder = MATLABGraphBuilder()

# Build a graph from a MATLAB project directory
graph = builder.build_from_directory('path/to/your/matlab/project')

# Save the graph to a file
import json
with open('matlab_graph.json', 'w') as f:
    json.dump(graph, f, indent=2)
```

2. Then, load the graph into GraphRAG:

```python
from graphrag import GraphRAG
from graphrag.matlab_analyzer import MATLABGraphLoader

# Load the graph
loader = MATLABGraphLoader('matlab_graph.json')
graph = loader.load()

# Initialize GraphRAG
rag = GraphRAG()

# Load the MATLAB graph into GraphRAG
rag.load_graph(graph)

# Now you can query the graph
results = rag.query("Find all functions that call function X")
print(results)
```

### Example Script

An example script is provided in `examples/matlab_graphrag.py` that demonstrates:
- Loading a MATLAB graph from a JSON file
- Basic graph analysis
- Integration with GraphRAG

Run the example:
```bash
python examples/matlab_graphrag.py --graph-file path/to/your/graph.json
```

## Usage

### Basic Usage

```python
from graphrag.matlab_analyzer import MATLABGraphBuilder

# Create a graph builder
builder = MATLABGraphBuilder()

# Build a graph from a single MATLAB file
graph = builder.build_from_file('path/to/your/matlab/file.m')

# Or build from a directory containing MATLAB files
graph = builder.build_from_directory('path/to/your/matlab/project')

# Access nodes and edges
print(f"Found {len(graph.nodes)} nodes and {len(graph.edges)} edges")

# Get information about a specific node
node = graph.nodes['function:my_function@/path/to/file.m']
print(f"Node: {node.name}, Type: {node.node_type}")
print(f"Defined in: {node.file_path}")
print(f"Code:\n{node.code}")

# Find all functions that call a specific function
for edge in graph.edges:
    if edge.relationship == 'calls' and edge.target_id == 'function:my_function@/path/to/file.m':
        caller = graph.nodes[edge.source_id]
        print(f"Called by: {caller.name} in {caller.file_path}")
```

### Example: Analyzing the GINav Project

An example script is provided in `examples/matlab_analyzer_example.py` that demonstrates how to analyze the GINav MATLAB codebase.

To run the example:

```bash
python examples/matlab_analyzer_example.py
```

This will:
1. Scan the GINav project directory for MATLAB files
2. Build a graph representation of the code structure
3. Print statistics about the codebase
4. Save the graph to a JSON file for further analysis

## Data Model

The MATLAB analyzer represents code as a graph with the following node types and relationships:

### Node Types

- **Script**: A MATLAB script file (`.m` file)
- **Function**: A MATLAB function
- **Class**: A MATLAB class definition
- **Method**: A method within a class
- **Variable**: A variable within a function or script

### Edge Types

- **calls**: A function/method calls another function/method
- **contains**: A container (e.g., script, class) contains an element (e.g., function, variable)
- **uses**: A function/method uses a variable

## Limitations

1. The current implementation uses a simple regex-based parser which may not handle all MATLAB syntax correctly.
2. Some advanced MATLAB features may not be fully supported.
3. The accuracy of the analysis depends on the complexity of the MATLAB code.

## Extending the Analyzer

To add support for additional MATLAB constructs or to improve the existing implementation, you can extend the following classes:

- `MATLABASTParser`: Handles parsing of MATLAB code into an AST
- `MATLABGraphBuilder`: Builds the graph representation from the AST
- `MatlabNode`/`MatlabEdge`: Define the data model for nodes and edges

## License

This project is licensed under the MIT License - see the LICENSE file for details.
