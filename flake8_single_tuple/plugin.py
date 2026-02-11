import ast


class SingleTupleChecker:
    name = "flake8-single-tuple"
    version = "1.1.0"
    STC001 = "STC001 single-item tuple missing trailing comma; did you mean `(x,)`?"

    def __init__(self, tree, filename):
        self.tree = tree
        self.filename = filename
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                self.source = f.read()
        except Exception:
            self.source = ""
        
        # Pre-calculate line offsets to convert (line, col) to absolute index
        self.line_offsets = [0]
        for line in self.source.splitlines(keepends=True):
            self.line_offsets.append(self.line_offsets[-1] + len(line))

        self.parents = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                self.parents[child] = parent

    def _get_offset(self, lineno, col_offset):
        return self.line_offsets[lineno - 1] + col_offset

    def run(self):
        for node in ast.walk(self.tree):
            # Only check "leaf" nodes that are likely intended to be tuple elements
            if isinstance(node, (ast.Constant, ast.Name, ast.Attribute, ast.Subscript, ast.Call)):
                if self._check_node(node):
                    yield (node.lineno, node.col_offset, self.STC001, type(self))

    def _check_node(self, node):
        parent = self.parents.get(node)
        
        # Ignore control flow / arithmetic / return groupings (Non-goals)
        if isinstance(parent, (ast.If, ast.While, ast.Assert, ast.Return, ast.Yield, 
                               ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.With)):
            return False

        try:
            start = self._get_offset(node.lineno, node.col_offset)
            end = self._get_offset(node.end_lineno, node.end_col_offset)

            # Move pointers outward to find parentheses, skipping whitespace/newlines
            left = start - 1
            while left >= 0 and self.source[left] in " \t\n\r":
                left -= 1
            
            right = end
            while right < len(self.source) and self.source[right] in " \t\n\r":
                right += 1

            # Check if wrapped in parentheses
            if left >= 0 and right < len(self.source) and self.source[left] == '(' and self.source[right] == ')':
                
                # Context 1: Function call argument -> func((x))
                # The first pair of () belongs to the function call itself.
                # We only warn if there is a SECOND pair of parens without a comma.
                if isinstance(parent, ast.Call) and node in parent.args:
                    # Look one step further out
                    outer_left = left - 1
                    while outer_left >= 0 and self.source[outer_left] in " \t\n\r":
                        outer_left -= 1
                    outer_right = right + 1
                    while outer_right < len(self.source) and self.source[outer_right] in " \t\n\r":
                        outer_right += 1
                    
                    if (outer_left >= 0 and outer_right < len(self.source) and 
                        self.source[outer_left] == '(' and self.source[outer_right] == ')'):
                        # It's double wrapped. Check for comma in the inner span.
                        return not self._has_comma_in_span(left, right + 1)
                    return False

                # Context 2: Assignment or Membership test -> x = (x) or x in (x)
                if (isinstance(parent, ast.Assign) and node == parent.value) or \
                   (isinstance(parent, ast.Compare) and any(node == c for c in parent.comparators)):
                    return not self._has_comma_in_span(left, right + 1)

        except (AttributeError, IndexError):
            pass
        return False

    def _has_comma_in_span(self, start, end):
        """Checks if a comma exists within the specified character range."""
        span = self.source[start:end]
        # We look for a comma that isn't inside another set of parens 
        # (though for "simple" nodes, this is rarely an issue)
        return ',' in span
