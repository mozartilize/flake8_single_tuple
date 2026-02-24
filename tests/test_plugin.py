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

    # --- ASSIGNMENT ---

    def test_assignment_violation(self):
        code = 'x = ("only_item")'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1)
        self.assertIn("STC001", errors[0][2])

    def test_valid_single_item_tuple(self):
        """x = ("item",) is correct."""
        code = 'x = ("item",)'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0)

    def test_multiline_logic(self):
        code = 'x = (\n    "item"\n)'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1)

    def test_redundant_tuple_nesting(self):
        """Should catch double-wrapped valid tuples: ((1,))"""
        code = 'x = ((1,))'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1, "Should flag redundant parens around a valid tuple")
        self.assertIn("STC001", errors[0][2])

    def test_fstring_violation(self):
        """f-strings in parens without comma should be caught."""
        code = 'x = (f"hello {name}")'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1, "Should flag f-string missing comma")

    def test_fstring_with_comma_valid(self):
        """f-strings with a comma are valid single-item tuples."""
        code = 'x = (f"id_{id}",)'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0)

    def test_parenthesized_lambda(self):
        """Should catch parenthesized lambdas in assignment: (lambda x: x+1)"""
        code = 'x = (lambda x: x+1)'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1, "Should flag redundant parens around a lambda")

    # --- MEMBERSHIP (RHS) ---

    def test_membership_violation_rhs(self):
        """x in ("A") — RHS is flagged."""
        code = 'if x in ("A"): pass'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][1], 8)

    def test_membership_valid_rhs(self):
        """x in ("A",) — valid tuple, no flag."""
        code = 'if x in ("A",): pass'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0)

    # --- MEMBERSHIP (LHS) ---

    def test_membership_violation_lhs(self):
        """("A") in x — LHS is flagged."""
        code = 'if ("A") in x: pass'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1, "Should flag redundant parens on LHS of 'in'")
        self.assertIn("STC001", errors[0][2])

    def test_membership_valid_lhs(self):
        """("A",) in x — valid tuple on LHS, no flag."""
        code = 'if ("A",) in x: pass'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0)

    def test_membership_both_sides_flagged(self):
        """("A") in ("B") — both sides are redundant, two violations."""
        code = 'if ("A") in ("B"): pass'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 2, "Should flag both LHS and RHS")

    def test_membership_lhs_non_membership_op_ignored(self):
        """("A") == x — only membership ops trigger the LHS check."""
        code = 'if ("A") == x: pass'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0, "Non-membership ops should not flag LHS")

    # --- CALL ARGUMENTS ---

    def test_standard_function_call_ignored(self):
        """Ensure normal calls are NOT flagged."""
        code = 'containers.append(c)'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0)

    def test_double_wrapped_call_violation(self):
        """Flag: func((item))"""
        code = 'func(("item"))'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1)

    # --- GENERATOR EXPRESSIONS ---

    def test_generator_expression_ignored(self):
        """Bare generator expressions require parens and shouldn't be flagged."""
        code = 'x = (i for i in range(10))'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0, "Generators should be ignored")

    def test_generator_in_call_ignored(self):
        """Generator in a call uses the call's own parens — no flag."""
        code = 'list(i for i in range(10))'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0)

    def test_nested_generator_violation(self):
        """((i for i in y)) — outer pair is redundant, should flag."""
        code = 'x = ((i for i in y))'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1, "Should flag redundant wrap around generator")

    # --- IGNORED CONTEXTS ---

    def test_ignored_contexts(self):
        """assert should stay untouched."""
        code = 'assert (x == y)'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
