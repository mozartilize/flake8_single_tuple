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
    # Visitor methods — using NodeVisitor gives us proper traversal
    # control and avoids cascading/duplicate reports.
    # ------------------------------------------------------------------

    def visit_Assign(self, node: ast.Assign) -> None:
        if node.value is not None:
            self._check_candidate(node.value, is_call=False)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self._check_candidate(node.value, is_call=False)
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is not None:
            self._check_candidate(node.value, is_call=False)
        self.generic_visit(node)

    def visit_Yield(self, node: ast.Yield) -> None:
        if node.value is not None:
            self._check_candidate(node.value, is_call=False)
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        # node.test is the asserted expression; node.msg is the optional message.
        # Flagging these would be noisy and often wrong, so we only visit children.
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        # Check the left-hand side: ("A") in x
        if any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
            self._check_candidate(node.left, is_call=False)

        # Check the right-hand side: x in ("A")
        for op, comp in zip(node.ops, node.comparators):
            if isinstance(op, (ast.In, ast.NotIn)):
                self._check_candidate(comp, is_call=False)

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        for arg in node.args:
            # GeneratorExp inside a call like sum(x for x in y) is intentional;
            # the outer parens belong to the call itself, not a grouping.
            if isinstance(arg, ast.GeneratorExp):
                continue
            self._check_candidate(arg, is_call=True)
        # Do NOT call self.generic_visit here with a blanket check; instead let
        # the visitor descend naturally so nested calls are visited individually.
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Core check
    # ------------------------------------------------------------------

    def _check_candidate(self, node: ast.expr, is_call: bool) -> None:
        if not isinstance(node, ast.expr):
            return

        # Allow ternary expressions — parens often aid readability.
        if isinstance(node, ast.IfExp):
            return

        # Allow binary operations — parens may express intentional grouping.
        if isinstance(node, ast.BinOp):
            return

        # GeneratorExp and Lambda are intentionally NOT excluded here.
        #
        # GeneratorExp: Python's AST sets col_offset to point *inside* the implicit
        # surrounding paren, so `x = (i for i in y)` naturally passes through
        # _check_violation without a false positive — the token before `i` is `(`,
        # but it's the genexp's own required paren and _check_violation won't find
        # a comma-free outer pair wrapping it. However `x = ((i for i in y))`
        # correctly flags the redundant outer pair.
        #
        # Lambda: `x = (lambda x: x+1)` is a genuine redundant grouping and should
        # be flagged just like any other single-expression parenthesisation.
        #
        # The one real GeneratorExp exception is inside a *call* — `sum(x for x in y)`
        # — where the call's own parens serve as the genexp's parens. That is handled
        # by skipping GeneratorExp nodes in visit_Call before reaching this method.

        start_idx = self._find_token_idx(node.lineno, node.col_offset, exact=True)
        if start_idx is None:
            return

        # Resolve the true end boundary: find the last token that belongs to
        # this node by searching for the first token *after* the node's end
        # position, then stepping back one.
        end_lineno = getattr(node, "end_lineno", node.lineno)
        end_col = getattr(node, "end_col_offset", node.col_offset)
        after_end_idx = self._find_token_idx(end_lineno, end_col, exact=False)
        # The last token of the node is the one just before after_end_idx.
        # If exact=False returned the index of a token exactly at (end_lineno, end_col),
        # that token is the first one *outside* the node span, so step back by 1.
        if after_end_idx is None:
            end_idx = len(self.tokens) - 1
        else:
            end_idx = after_end_idx - 1

        violation_idx = self._check_violation(start_idx, end_idx, is_call)
        if violation_idx is not None:
            v_tok = self.tokens[violation_idx]
            self.violations.append((v_tok.start[0], v_tok.start[1], self.STC001, type(self)))

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    def _find_token_idx(self, line: int, col: int, exact: bool = True) -> Optional[int]:
        """
        Binary-search the pre-sorted token start list.

        exact=True  → returns the index only if a token starts exactly at (line, col).
        exact=False → returns the index of the first token at or after (line, col),
                      which lets callers resolve node-end boundaries without an O(N) scan.
        """
        idx = bisect.bisect_left(self.token_starts, (line, col))
        if idx >= len(self.token_starts):
            return None
        if exact and self.token_starts[idx] != (line, col):
            return None
        return idx

    def _next_meaningful(self, start_idx: int, step: int) -> Tuple[Optional[object], Optional[int]]:
        """Walk forward (step=+1) or backward (step=-1) skipping whitespace/comments."""
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
        """Return the index of the closing ')' that matches tokens[open_idx]."""
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
        """Return True if there is a top-level comma between open_idx and close_idx."""
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

    def _check_violation(self, start_idx: int, end_idx: int, is_call: bool) -> Optional[int]:
        """
        Return the token index of the opening '(' that wraps the node if it is a
        redundant single-element grouping, or None otherwise.

        For call arguments (is_call=True) the node is already inside the call's
        own parens, so we need to find a *second* wrapping pair:
            func((x))   ← the outer '(' belongs to the call, inner '(' is the issue
        """
        # The token immediately before the node should be '('
        prev_tok, prev_idx = self._next_meaningful(start_idx, -1)
        if prev_tok is None or prev_tok.string != "(":
            return None

        if is_call:
            # For call args, prev_idx is the call's own opening paren.
            # There must be yet another '(' before that for a real violation.
            outer_tok, outer_idx = self._next_meaningful(prev_idx, -1)
            if outer_tok is None or outer_tok.string != "(":
                return None
            search_idx = outer_idx
        else:
            search_idx = prev_idx

        closing_idx = self._find_matching_paren(search_idx)
        if closing_idx is None:
            return None

        # The closing paren must come *after* the last token of the node.
        # Previously the code used `closing_idx < end_idx` which was an
        # off-by-one: end_idx is the last token *inside* the node, so the
        # closing paren must be strictly greater than end_idx.
        if closing_idx <= end_idx:
            return None

        if not self._span_has_comma(search_idx, closing_idx):
            return search_idx

        return None
