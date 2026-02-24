import ast
import bisect
import tokenize
from typing import Generator, List, Optional, Tuple


class SingleTupleChecker:
    name = "flake8-single-tuple"
    version = "3.0.0"
    STC001 = "STC001 redundant or misleading parentheses; did you mean `(x,)` for a tuple?"

    def __init__(self, tree: ast.AST, lines: list[str]):
        self.tree = tree
        self.lines = lines

    def run(self) -> Generator[Tuple[int, int, str, type], None, None]:
        line_iter = iter(self.lines)
        try:
            # We still need the full list for lookups and depth scanning
            tokens = list(tokenize.generate_tokens(lambda: next(line_iter)))
        except (tokenize.TokenError, StopIteration):
            return

        # Pre-extract start positions to make them bisectable
        # This is an O(N) pass, but much lighter than a dictionary
        token_starts = [t.start for t in tokens]
        
        for node in ast.walk(self.tree):
            candidates = []

            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                candidates.append((node.value, False))
            elif isinstance(node, ast.Compare):
                for op, comp in zip(node.ops, node.comparators):
                    if isinstance(op, (ast.In, ast.NotIn)):
                        candidates.append((comp, False))
            elif isinstance(node, ast.Call):
                for arg in node.args:
                    candidates.append((arg, True))
            else:
                continue

            for cand, is_call in candidates:
                # 1. SKIP logic groupings that often require/benefit from parentheses
                if not isinstance(cand, ast.expr):
                    continue
                    
                # if isinstance(cand, (ast.GeneratorExp, ast.IfExp, ast.Lambda)):
                #     continue

                if isinstance(cand, (ast.IfExp)):
                    continue
                
                # Optional: If you want to allow math groupings (1 + 2)
                if isinstance(cand, ast.BinOp):
                    continue
                
                # O(log N) lookup instead of O(1) dict but with O(1) memory per token
                start_idx = self._find_token_idx(token_starts, cand.lineno, cand.col_offset)
                if start_idx is None:
                    continue

                # Use the same bisect logic for end boundary resolution
                end_idx = self._find_token_idx(
                    token_starts, 
                    getattr(cand, 'end_lineno', cand.lineno), 
                    getattr(cand, 'end_col_offset', cand.col_offset),
                    exact=False
                )

                violation_idx = self._check_violation(tokens, start_idx, end_idx, is_call)
                if violation_idx is not None:
                    v_tok = tokens[violation_idx]
                    yield (v_tok.start[0], v_tok.start[1], self.STC001, type(self))

    def _find_matching_paren(self, tokens: list, open_idx: int) -> Optional[int]:
        """Anchors to the opening paren and finds the corresponding closing one."""
        depth = 0
        for i in range(open_idx, len(tokens)):
            if tokens[i].string == '(':
                depth += 1
            elif tokens[i].string == ')':
                depth -= 1
                if depth == 0:
                    return i
        return None

    def _find_token_idx(self, starts: List[Tuple[int, int]], line: int, col: int, exact: bool = True) -> Optional[int]:
        """
        Finds the token index using binary search O(log N).
        If exact=False, it finds the first token that starts at or after the coordinate.
        """
        idx = bisect.bisect_left(starts, (line, col))
        if idx < len(starts):
            if exact and starts[idx] != (line, col):
                return None
            return idx
        return None

    def _get_meaningful_token(self, tokens: list, start_idx: int, step: int):
        curr = start_idx + step
        while 0 <= curr < len(tokens):
            tok = tokens[curr]
            if tok.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, 
                                tokenize.DEDENT, tokenize.COMMENT, tokenize.ENCODING):
                return tok, curr
            curr += step
        return None, curr

    def _check_violation(self, tokens: list, start_idx: int, end_idx: int, is_call: bool) -> Optional[int]:
        prev_tok, prev_idx = self._get_meaningful_token(tokens, start_idx, -1)
        if not prev_tok or prev_tok.string != '(':
            return None

        if is_call:
            outer_prev, outer_idx = self._get_meaningful_token(tokens, prev_idx, -1)
            if not outer_prev or outer_prev.string != '(':
                return None
            search_idx = outer_idx
        else:
            search_idx = prev_idx

        closing_idx = self._find_matching_paren(tokens, search_idx)
        # Verify the parens actually wrap the node span
        if not closing_idx or closing_idx < end_idx:
            return None

        if not self._span_has_comma(tokens, search_idx, closing_idx):
            return search_idx
        return None

    def _span_has_comma(self, tokens: list, open_idx: int, close_idx: int) -> bool:
        depth = 0
        for i in range(open_idx + 1, close_idx):
            tok = tokens[i]
            if tok.string == '(':
                depth += 1
            elif tok.string == ')':
                depth -= 1
            elif tok.string == ',' and depth == 0:
                return True
        return False
