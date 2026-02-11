import ast


class SingleTupleChecker:
    name = "flake8-single-tuple"
    version = "1.2.0"
    
    # STC001 is the error code
    STC001 = "STC001 single-item tuple missing trailing comma; did you mean `(x,)`?"

    def __init__(self, tree, lines):
        """
        Flake8 provides the AST tree and the source lines automatically.
        """
        self.tree = tree
        self.lines = lines
        self.source = "".join(lines)
        
        # Calculate offsets to map (line, col) to a flat character index
        self.line_offsets = [0]
        for line in lines:
            self.line_offsets.append(self.line_offsets[-1] + len(line))

        # Build parent map for context awareness
        self.parents = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                self.parents[child] = parent

    def _get_offset(self, lineno, col_offset):
        # Convert 1-based lineno and 0-based col_offset to absolute source index
        return self.line_offsets[lineno - 1] + col_offset

    def run(self):
        for node in ast.walk(self.tree):
            # Target 'simple' expression units
            if isinstance(node, (ast.Constant, ast.Name, ast.Attribute, ast.Subscript, ast.Call)):
                if self._check_node(node):
                    # Flake8 expectation: (lineno, col, message, class_type)
                    yield (node.lineno, node.col_offset, self.STC001, type(self))

    def _check_node(self, node):
        parent = self.parents.get(node)
        
        # Non-goals: Control flow and basic groupings
        if isinstance(parent, (ast.If, ast.While, ast.Assert, ast.Return, ast.Yield, 
                               ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.With)):
            return False

        try:
            start = self._get_offset(node.lineno, node.col_offset)
            # handle nodes without end markers safely
            end_lineno = getattr(node, 'end_lineno', node.lineno)
            end_col = getattr(node, 'end_col_offset', node.col_offset)
            end = self._get_offset(end_lineno, end_col)

            # Look outward for parentheses, skipping whitespace/newlines
            left = start - 1
            while left >= 0 and self.source[left] in " \t\n\r":
                left -= 1
            
            right = end
            while right < len(self.source) and self.source[right] in " \t\n\r":
                right += 1

            if left >= 0 and right < len(self.source) and self.source[left] == '(' and self.source[right] == ')':
                
                # Context A: Membership or Assignment
                if (isinstance(parent, (ast.Assign, ast.AnnAssign)) and node == parent.value) or \
                   (isinstance(parent, ast.Compare) and any(node == c for c in parent.comparators)):
                    return not self._has_comma_in_span(left, right + 1)

                # Context B: Function call argument -> func((x))
                if isinstance(parent, ast.Call) and node in parent.args:
                    outer_left = left - 1
                    while outer_left >= 0 and self.source[outer_left] in " \t\n\r":
                        outer_left -= 1
                    outer_right = right + 1
                    while outer_right < len(self.source) and self.source[outer_right] in " \t\n\r":
                        outer_right += 1
                    
                    if (outer_left >= 0 and outer_right < len(self.source) and 
                        self.source[outer_left] == '(' and self.source[outer_right] == ')'):
                        return not self._has_comma_in_span(left, right + 1)
        except Exception:
            pass
        return False

    def _has_comma_in_span(self, start, end):
        return ',' in self.source[start:end]
