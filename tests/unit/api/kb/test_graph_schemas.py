"""Graph schema tests — split across two files for RULE-04 compliance.

Tests are now in:
  - test_graph_schemas_nodes.py      (GraphNode + GraphEdge)
  - test_graph_schemas_responses.py  (GraphStats + GraphFilter + responses)

This file exists only for backwards compatibility. pytest discovers
all test classes via the filename pattern test_*.py.
"""
