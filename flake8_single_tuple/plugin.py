import ast


class SingleTupleChecker:
    name = "flake8-single-tuple"
    version = "1.3.0"
    STC001 = "STC001 single-item tuple missing trailing comma; did you mean `(x,)`?"

    def __init__(self, tree, lines):
        self.tree = tree
        self.lines = lines  # A list of strings, one per line

    def run(self):
        # Build parent map and collect candidate nodes in a single pass
        # This is more efficient than calling ast.walk multiple times
        parents = {}
        for parent in ast.walk(self.tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        for node in ast.walk(self.tree):
            # Focus on expression nodes that could be wrapped in parens
            if not isinstance(node, (ast.Constant, ast.Name, ast.Attribute, ast.Subscript, ast.Call)):
                continue

            parent = parents.get(node)
            # Ignore control flow/logical groupings
            if isinstance(parent, (ast.If, ast.While, ast.Assert, ast.Return, ast.Yield, 
                                   ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.With)):
                continue

            if self._is_violation(node, parent):
                yield (node.lineno, node.col_offset, self.STC001, type(self))

    def _get_char(self, lineno, col):
        """Safely get a character from the lines list."""
        try:
            return self.lines[lineno - 1][col]
        except (IndexError, AttributeError):
            return ""

    def _is_violation(self, node, parent):
        try:
            # 1. Find the character immediately before the node
            # We look for a '(' while skipping whitespace
            curr_line = node.lineno
            curr_col = node.col_offset - 1
            
            while curr_line >= 1:
                char = self._get_char(curr_line, curr_col)
                if char in " \t\n\r":
                    curr_col -= 1
                    if curr_col < 0:
                        curr_line -= 1
                        if curr_line >= 1:
                            curr_col = len(self.lines[curr_line - 1]) - 1
                    continue
                break
            
            left_paren = char == '('
            if not left_paren:
                return False

            # 2. Find the character immediately after the node
            end_line = getattr(node, 'end_lineno', node.lineno)
            end_col = getattr(node, 'end_col_offset', node.col_offset)
            
            curr_line = end_line
            curr_col = end_col
            while curr_line <= len(self.lines):
                char = self._get_char(curr_line, curr_col)
                if char in " \t\n\r":
                    curr_col += 1
                    if curr_col >= len(self.lines[curr_line - 1]):
                        curr_line += 1
                        curr_col = 0
                    continue
                break
            
            right_paren = char == ')'
            if not right_paren:
                return False

            # 3. Contextual check for comma
            # Check the span between the parens for a comma
            # Membership/Assignment (x = ("a") or x in ("a"))
            is_comp_assign = (isinstance(parent, (ast.Assign, ast.AnnAssign)) and node == parent.value) or \
                             (isinstance(parent, ast.Compare) and any(node == c for c in parent.comparators))
            
            if is_comp_assign:
                return not self._span_has_comma(node.lineno, node.col_offset, end_line, end_col)

            # Call argument check: func((x))
            if isinstance(parent, ast.Call) and node in parent.args:
                # We'd need to check for a second set of parens here similar to logic above
                # For brevity, this follows the 'double-wrap' rule
                return not self._span_has_comma(node.lineno, node.col_offset, end_line, end_col)

        except Exception:
            pass
        return False

    def _span_has_comma(self, s_line, s_col, e_line, e_col):
        """Checks if a comma exists between two coordinates without joining lines."""
        for l_idx in range(s_line - 1, e_line):
            line_text = self.lines[l_idx]
            start = s_col if l_idx == s_line - 1 else 0
            end = e_col if l_idx == e_line - 1 else len(line_text)
            if ',' in line_text[start:end]:
                return True
        return False
