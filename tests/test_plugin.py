import ast
import unittest
from flake8_single_tuple.plugin import SingleTupleChecker


class TestSingleTupleChecker(unittest.TestCase):
    def run_checker(self, code):
        """Helper to simulate Flake8 execution on a code string."""
        tree = ast.parse(code)
        lines = code.splitlines(keepends=True)
        checker = SingleTupleChecker(tree, lines)
        return [(line, col, msg) for line, col, msg, _ in checker.run()]

    # ------------------------------------------------------------------
    # MEMBERSHIP TESTS — the core dangerous bug
    # ------------------------------------------------------------------

    def test_membership_rhs_violation(self):
        """x in ("foo") iterates string characters — silent bug."""
        errors = self.run_checker('if x in ("foo"): pass')
        self.assertEqual(len(errors), 1)
        self.assertIn("STC001", errors[0][2])

    def test_membership_lhs_violation(self):
        """("foo") in x — same bug on the LHS."""
        errors = self.run_checker('if ("foo") in x: pass')
        self.assertEqual(len(errors), 1)
        self.assertIn("STC001", errors[0][2])

    def test_membership_not_in_violation(self):
        """not in is equally dangerous."""
        errors = self.run_checker('if x not in ("foo"): pass')
        self.assertEqual(len(errors), 1)

    def test_membership_both_sides_flagged(self):
        """("A") in ("B") — both sides flagged independently."""
        errors = self.run_checker('if ("A") in ("B"): pass')
        self.assertEqual(len(errors), 2)

    def test_membership_valid_tuple_rhs(self):
        """x in ("foo",) is correct — trailing comma present."""
        errors = self.run_checker('if x in ("foo",): pass')
        self.assertEqual(len(errors), 0)

    def test_membership_valid_multi_item(self):
        """x in ("foo", "bar") is a real tuple — no flag."""
        errors = self.run_checker('if x in ("foo", "bar"): pass')
        self.assertEqual(len(errors), 0)

    def test_membership_list_not_flagged(self):
        """x in ["foo"] uses a list literal — not our concern."""
        errors = self.run_checker('if x in ["foo"]: pass')
        self.assertEqual(len(errors), 0)

    def test_membership_binop_rhs_flagged(self):
        """`x in (a + b)` — a+b could be a container, looks like missed comma."""
        errors = self.run_checker('if x in (a + b): pass')
        self.assertEqual(len(errors), 1)

    def test_membership_boolop_not_flagged(self):
        """`x in (a and b)` — type checkers catch this as a type error already."""
        errors = self.run_checker('if x in (a and b): pass')
        self.assertEqual(len(errors), 0)

    def test_membership_or_not_flagged(self):
        errors = self.run_checker('if x in (a or b): pass')
        self.assertEqual(len(errors), 0)

    def test_non_membership_compare_not_flagged(self):
        """("foo") == x — only in/not in trigger the LHS check."""
        errors = self.run_checker('if ("foo") == x: pass')
        self.assertEqual(len(errors), 0)

    # ------------------------------------------------------------------
    # COMPOUND BOOLEAN GROUPING — must not flag
    # ------------------------------------------------------------------

    def test_compound_boolean_with_in(self):
        """Parens grouping a compound boolean expression that contains `in`."""
        code = 'if x == y or (x in items and y in items): pass'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0)

    def test_and_expression_with_in(self):
        errors = self.run_checker('if (a in x and b in x): pass')
        self.assertEqual(len(errors), 0)

    def test_or_expression_with_in(self):
        errors = self.run_checker('if (a in x or b in x): pass')
        self.assertEqual(len(errors), 0)

    # ------------------------------------------------------------------
    # ASSIGNMENT — bare string literals only
    # ------------------------------------------------------------------

    def test_assignment_string_violation(self):
        """x = ("foo") — almost certainly a missed comma."""
        errors = self.run_checker('x = ("foo")')
        self.assertEqual(len(errors), 1)
        self.assertIn("STC001", errors[0][2])

    def test_assignment_fstring_violation(self):
        """f-strings are string literals too."""
        errors = self.run_checker('x = (f"hello {name}")')
        self.assertEqual(len(errors), 1)

    def test_assignment_valid_tuple(self):
        """x = ("foo",) is correct."""
        errors = self.run_checker('x = ("foo",)')
        self.assertEqual(len(errors), 0)

    def test_assignment_non_string_not_flagged(self):
        """x = (42) — non-string literals are out of scope."""
        errors = self.run_checker('x = (42)')
        self.assertEqual(len(errors), 0)

    def test_assignment_call_not_flagged(self):
        """x = (some_func()) — too ambiguous, not flagged."""
        errors = self.run_checker('x = (some_func())')
        self.assertEqual(len(errors), 0)

    def test_assignment_binop_not_flagged(self):
        """x = (a + b) — legitimate grouping in assignment."""
        errors = self.run_checker('x = (a + b)')
        self.assertEqual(len(errors), 0)

    def test_assignment_boolop_not_flagged(self):
        """x = (a or b) — legitimate grouping."""
        errors = self.run_checker('x = (a or b)')
        self.assertEqual(len(errors), 0)

    # ------------------------------------------------------------------
    # IMPLICIT STRING JOIN — must never be flagged
    # ------------------------------------------------------------------

    def test_implicit_join_with_plus(self):
        """Multiline BinOp string join — parens are load-bearing."""
        code = 'x = (\n    "foo"\n    + "bar"\n)'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0)

    def test_implicit_join_bare(self):
        """Adjacent string literals — parens are load-bearing."""
        code = 'x = (\n    "foo"\n    "bar"\n)'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0)

    # ------------------------------------------------------------------
    # OUT OF SCOPE — contexts intentionally excluded
    # ------------------------------------------------------------------

    def test_return_not_flagged(self):
        """return ("foo") is out of scope."""
        errors = self.run_checker('def f():\n    return ("foo")')
        self.assertEqual(len(errors), 0)

    def test_double_wrapped_call_not_flagged(self):
        """func(("item")) is out of scope."""
        errors = self.run_checker('func(("item"))')
        self.assertEqual(len(errors), 0)

    def test_assert_not_flagged(self):
        errors = self.run_checker('assert (x == y)')
        self.assertEqual(len(errors), 0)

    def test_lambda_not_flagged(self):
        errors = self.run_checker('x = (lambda x: x+1)')
        self.assertEqual(len(errors), 0)

    def test_double_wrapped_genexp_not_flagged(self):
        errors = self.run_checker('x = ((i for i in y))')
        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
