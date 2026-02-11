import ast
from dataclasses import dataclass
from .rust_tuple_scanner import Scanner

@dataclass
class NodeCoords:
    id: int
    lineno: int
    col_offset: int
    end_lineno: int
    end_col_offset: int
    is_call_arg: bool
    is_comp_or_assign: bool

class SingleTupleChecker:
    name = "flake8-single-tuple"
    version = "2.2.0"
    STC001 = "STC001 single-item tuple missing trailing comma; did you mean `(x,)`?"

    def __init__(self, tree, lines):
        self.tree = tree
        self.source = "".join(lines)
        self.scanner = Scanner(self.source)
        self.parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}

    def run(self):
        candidates = []
        nodes_map = {}

        for i, node in enumerate(ast.walk(self.tree)):
            if not isinstance(node, (ast.Constant, ast.Name, ast.Attribute, ast.Subscript, ast.Call)):
                continue
                
            parent = self.parents.get(node)
            if isinstance(parent, (ast.If, ast.While, ast.Assert, ast.Return, ast.Yield, 
                                   ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.With)):
                continue

            try:
                # Store in a dataclass so Rust can access attributes (.id, .lineno, etc)
                candidates.append(NodeCoords(
                    id=i,
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    end_lineno=getattr(node, 'end_lineno', node.lineno),
                    end_col_offset=getattr(node, 'end_col_offset', node.col_offset),
                    is_call_arg=isinstance(parent, ast.Call) and node in parent.args,
                    is_comp_or_assign=(isinstance(parent, (ast.Assign, ast.AnnAssign)) and node == parent.value) or \
                                      (isinstance(parent, ast.Compare) and any(node == c for c in parent.comparators))
                ))
                nodes_map[i] = node
            except (AttributeError, IndexError):
                continue

        # Single batch call to Rust for maximum speed
        violation_ids = self.scanner.check_nodes(candidates)

        for v_id in violation_ids:
            node = nodes_map[v_id]
            yield (node.lineno, node.col_offset, self.STC001, type(self))