import ast
import bisect
import tokenize
from typing import Generator, List, Optional, Tuple


class SingleTupleChecker(ast.NodeVisitor):
    name = "flake8-single-tuple"
    STC001 = "STC001 redundant or misleading parentheses; did you mean `(x,)` for a tuple?"

    def __init__(self, tree: ast.AST, lines: list[str]):
        self.tree = tree
        self.lines = lines
        self.tokens: list = []
        self.token_starts: List[Tuple[int, int]] = []
        self.violations: list[Tuple[int, int, str, type]] = []

    def run(self) -> Generator[Tuple[int, int, str, type], None, None]:
        line_iter = iter(self.lines)
        try:
            self.tokens = list(tokenize.generate_tokens(lambda: next(line_iter)))
        except (tokenize.TokenError, StopIteration):
            return

        self.token_starts = [t.start for t in self.tokens]
        self.visit(self.tree)
        yield from self.violations

    # ------------------------------------------------------------------
    # Visitor methods
    # ------------------------------------------------------------------

    def visit_Assign(self, node: ast.Assign) -> None:
        # Only flag bare string literal assignments: x = ("foo") or x = (f"...")
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            self._check_candidate(node.value, in_membership=False)
        elif isinstance(node.value, ast.JoinedStr):  # f-string
            self._check_candidate(node.value, in_membership=False)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is None:
            self.generic_visit(node)
            return
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            self._check_candidate(node.value, in_membership=False)
        elif isinstance(node.value, ast.JoinedStr):
            self._check_candidate(node.value, in_membership=False)
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        has_membership = any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops)

        if has_membership:
            self._check_candidate(node.left, in_membership=True)

        for op, comp in zip(node.ops, node.comparators):
            if isinstance(op, (ast.In, ast.NotIn)):
                self._check_candidate(comp, in_membership=True)

        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Core check
    # ------------------------------------------------------------------

    def _check_candidate(self, node: ast.expr, in_membership: bool) -> None:
        if not isinstance(node, ast.expr):
            return

        if isinstance(node, ast.IfExp):
            return

        # BoolOp (and/or): type checkers already flag `x in (a and b)` as a
        # type error (bool isn't iterable). No need to double-warn.
        if isinstance(node, ast.BoolOp):
            return

        # BinOp: excluded in assignment context (legitimate grouping), but
        # flagged in membership — `x in (a + b)` looks like a missed comma.
        if isinstance(node, ast.BinOp) and not in_membership:
            return

        # For BinOp nodes the paren span will naturally contain operators at
        # depth 0 (the +, -, etc. that are part of the expression). We must
        # skip the single-expression span check in that case — the AST already
        # tells us this is one node, so we trust end_idx rather than rescanning.
        skip_span_check = isinstance(node, ast.BinOp)

        start_idx = self._find_token_idx(node.lineno, node.col_offset, exact=True)
        if start_idx is None:
            return

        end_lineno = getattr(node, "end_lineno", node.lineno)
        end_col = getattr(node, "end_col_offset", node.col_offset)
        after_end_idx = self._find_token_idx(end_lineno, end_col, exact=False)
        end_idx = len(self.tokens) - 1 if after_end_idx is None else after_end_idx - 1

        violation_idx = self._check_violation(start_idx, end_idx, skip_span_check)
        if violation_idx is not None:
            v_tok = self.tokens[violation_idx]
            self.violations.append((v_tok.start[0], v_tok.start[1], self.STC001, type(self)))

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    def _find_token_idx(self, line: int, col: int, exact: bool = True) -> Optional[int]:
        idx = bisect.bisect_left(self.token_starts, (line, col))
        if idx >= len(self.token_starts):
            return None
        if exact and self.token_starts[idx] != (line, col):
            return None
        return idx

    def _next_meaningful(self, start_idx: int, step: int) -> Tuple[Optional[object], Optional[int]]:
        curr = start_idx + step
        while 0 <= curr < len(self.tokens):
            tok = self.tokens[curr]
            if tok.type not in (
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.COMMENT,
                tokenize.ENCODING,
            ):
                return tok, curr
            curr += step
        return None, None

    def _find_matching_paren(self, open_idx: int) -> Optional[int]:
        depth = 0
        for i in range(open_idx, len(self.tokens)):
            s = self.tokens[i].string
            if s == "(":
                depth += 1
            elif s == ")":
                depth -= 1
                if depth == 0:
                    return i
        return None

    def _span_has_comma(self, open_idx: int, close_idx: int) -> bool:
        depth = 0
        for i in range(open_idx + 1, close_idx):
            s = self.tokens[i].string
            if s == "(":
                depth += 1
            elif s == ")":
                depth -= 1
            elif s == "," and depth == 0:
                return True
        return False

    def _span_has_implicit_string_join(self, open_idx: int, close_idx: int) -> bool:
        """
        Return True if the span contains more than one string token at depth 0,
        indicating an implicit string concatenation that needs the parens.
        """
        depth = 0
        string_count = 0
        for i in range(open_idx + 1, close_idx):
            tok = self.tokens[i]
            if tok.string == "(":
                depth += 1
            elif tok.string == ")":
                depth -= 1
            elif tok.type == tokenize.STRING and depth == 0:
                string_count += 1
                if string_count > 1:
                    return True
        return False

    def _span_is_single_expression(self, open_idx: int, close_idx: int) -> bool:
        """
        Return True if the paren span contains exactly one logical item at depth 0.
        Any operator or keyword alongside the candidate means the parens are grouping
        multiple things — not wrapping a single value.

        Catches: (x in items and y in items)
        where `x` is a valid Compare LHS but the outer parens belong to a
        compound boolean, not a single-item tuple context.

        Not applied to BinOp candidates — their spans naturally contain operators
        that are part of the single expression itself.
        """
        _KEYWORD_OPERATORS = frozenset({
            "and", "or", "not", "in", "is", "if", "else", "for", "lambda",
        })
        _SYMBOL_OPERATORS = frozenset({
            "+", "-", "*", "/", "//", "%", "**", "@",
            "&", "|", "^", "~", "<<", ">>",
            "<", ">", "<=", ">=", "==", "!=",
            "->",
        })
        depth = 0
        for i in range(open_idx + 1, close_idx):
            tok = self.tokens[i]
            if tok.string == "(":
                depth += 1
            elif tok.string == ")":
                depth -= 1
            elif depth == 0:
                if tok.type == tokenize.NAME and tok.string in _KEYWORD_OPERATORS:
                    return False
                if tok.type == tokenize.OP and tok.string in _SYMBOL_OPERATORS:
                    return False
        return True

    def _check_violation(self, start_idx: int, end_idx: int, skip_span_check: bool = False) -> Optional[int]:
        prev_tok, prev_idx = self._next_meaningful(start_idx, -1)
        if prev_tok is None or prev_tok.string != "(":
            return None

        search_idx = prev_idx
        closing_idx = self._find_matching_paren(search_idx)
        if closing_idx is None:
            return None

        if closing_idx <= end_idx:
            return None

        if self._span_has_comma(search_idx, closing_idx):
            return None

        if self._span_has_implicit_string_join(search_idx, closing_idx):
            return None

        # BinOp candidates skip the span check — their own operators are part
        # of the single expression and would incorrectly trip the guard.
        if not skip_span_check and not self._span_is_single_expression(search_idx, closing_idx):
            return None

        return search_idx
