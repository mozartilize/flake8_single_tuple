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

    ## --- NEW STRICT CASES ---

    def test_redundant_tuple_nesting(self):
        """Should catch double-wrapped valid tuples: ((1,))"""
        code = 'x = ((1,))'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1, "Should flag redundant parens around a valid tuple")
        self.assertIn("STC001", errors[0][2])

    def test_parenthesized_lambda(self):
        """Should catch parenthesized lambdas in assignment: (lambda x: x+1)"""
        code = 'x = (lambda x: x+1)'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1, "Should flag redundant parens around a lambda")

    ## --- REGRESSION CASES ---

    def test_assignment_violation(self):
        code = 'x = ("only_item")'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1)

    def test_membership_violation(self):
        code = 'if x in ("A"): pass'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1)
        # 0-indexed: 'i' is 0, 'f' is 1, ' ' is 2, 'x' is 3 ... '(' is 8
        self.assertEqual(errors[0][1], 8)

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

    def test_valid_single_item_tuple(self):
        """x = ("item",) is correct."""
        code = 'x = ("item",)'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0)

    def test_multiline_logic(self):
        code = 'x = (\n    "item"\n)'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1)

    def test_ignored_contexts(self):
        """Control flow grouping like 'assert' or 'if' should stay untouched."""
        code = 'assert (x == y)'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0)

    def test_fstring_violation(self):
        """f-strings in parens without comma should be caught."""
        code = 'x = (f"hello {name}")'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1, "Should flag f-string missing comma")

    def test_generator_expression_ignored(self):
        """Generator expressions require parens and shouldn't have commas."""
        code = 'x = (i for i in range(10))'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0, "Generators should be ignored")

    def test_fstring_with_comma_valid(self):
        """f-strings with a comma are valid single-item tuples."""
        code = 'x = (f"id_{id}",)'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0)

    def test_nested_generator_violation(self):
        """
        If a generator is double-wrapped, the OUTER set is redundant.
        ((i for i in y))
        """
        code = 'x = ((i for i in y))'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1, "Should flag redundant wrap around generator")

if __name__ == "__main__":
    unittest.main()