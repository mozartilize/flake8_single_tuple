import ast

class SingleTupleChecker:
    name = "flake8-single-tuple"
    version = "1.3.2"
    STC001 = "STC001 single-item tuple missing trailing comma; did you mean `(x,)`?"

    def __init__(self, tree, lines):
        self.tree = tree
        self.lines = lines

    def run(self):
        parents = {child: parent for parent in ast.walk(self.tree) for child in ast.iter_child_nodes(parent)}

        for node in ast.walk(self.tree):
            if not isinstance(node, (ast.Constant, ast.Name, ast.Attribute, ast.Subscript, ast.Call)):
                continue

            parent = parents.get(node)
            if isinstance(parent, (ast.If, ast.While, ast.Assert, ast.Return, ast.Yield, 
                                   ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.With)):
                continue

            if self._is_violation(node, parent):
                yield (node.lineno, node.col_offset, self.STC001, type(self))

    def _get_char_at(self, lineno, col):
        try:
            if 1 <= lineno <= len(self.lines):
                line = self.lines[lineno - 1]
                if 0 <= col < len(line):
                    return line[col]
        except Exception:
            pass
        return None

    def _seek(self, lineno, col, direction):
        """Moves through self.lines skipping whitespace to find the next char."""
        curr_l, curr_c = lineno, col
        while 1 <= curr_l <= len(self.lines):
            char = self._get_char_at(curr_l, curr_c)
            
            if char is None: # We hit end of line or start of line
                if direction > 0:
                    curr_l += 1
                    curr_c = 0
                else:
                    curr_l -= 1
                    if curr_l >= 1:
                        curr_c = len(self.lines[curr_l - 1]) - 1
                continue
            
            if char in " \t\n\r":
                curr_c += direction
                continue
            
            return char, curr_l, curr_c
        return None, curr_l, curr_c

    def _is_violation(self, node, parent):
        # 1. Look for immediate inner parentheses (x)
        char_l, l_line, l_col = self._seek(node.lineno, node.col_offset - 1, -1)
        
        end_lineno = getattr(node, "end_lineno", node.lineno)
        end_col = getattr(node, "end_col_offset", node.col_offset)
        char_r, r_line, r_col = self._seek(end_lineno, end_col, 1)

        if char_l != '(' or char_r != ')':
            return False

        # 2. Context Logic
        is_call_arg = isinstance(parent, ast.Call) and node in parent.args
        is_comp_assign = (isinstance(parent, (ast.Assign, ast.AnnAssign)) and node == parent.value) or \
                         (isinstance(parent, ast.Compare) and any(node == c for c in parent.comparators))

        # For function calls: func((x)) -> we need to find a SECOND set of parens
        if is_call_arg:
            outer_l, _, _ = self._seek(l_line, l_col - 1, -1)
            outer_r, _, _ = self._seek(r_line, r_col + 1, 1)
            if outer_l == '(' and outer_r == ')':
                return not self._span_has_comma(l_line, l_col, r_line, r_col)
            return False

        # For assignments/comparisons: x = (y) or x in (y)
        if is_comp_assign:
            return not self._span_has_comma(l_line, l_col, r_line, r_col)

        return False

    def _span_has_comma(self, s_line, s_col, e_line, e_col):
        """Checks for a comma between two points in self.lines."""
        for idx in range(s_line - 1, e_line):
            line = self.lines[idx]
            start = s_col if idx == s_line - 1 else 0
            end = e_col if idx == e_line - 1 else len(line)
            if ',' in line[start:end]:
                return True
        return False
