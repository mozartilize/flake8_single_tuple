import ast
import unittest
from flake8_single_tuple.plugin import SingleTupleChecker

class TestSingleTupleChecker(unittest.TestCase):
    def run_checker(self, code):
        """Helper to simulate Flake8 execution on a code string."""
        tree = ast.parse(code)
        # Splitlines(True) preserves the \n characters, mimicking Flake8 input
        lines = code.splitlines(keepends=True)
        checker = SingleTupleChecker(tree, lines)
        return [(line, col, msg) for line, col, msg, _ in checker.run()]

    def test_assignment_violation(self):
        code = 'x = ("only_item")'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1)
        self.assertIn("STC001", errors[0][2])

    def test_membership_violation(self):
        code = 'if x in ("A"): pass'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][1], 9)  # Column offset for ("A")

    def test_standard_function_call_ignored(self):
        """
        Critical fix: Ensure containers.append(c) is NOT flagged.
        The parens belong to the Call, not a tuple.
        """
        code = 'containers.append(c)'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0, "Should not flag standard function calls")

    def test_double_wrapped_call_violation(self):
        """Should flag when an argument is explicitly double-wrapped without a comma."""
        code = 'func(("item"))'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1)
        self.assertIn("STC001", errors[0][2])

    def test_valid_single_item_tuple(self):
        code = 'x = ("item",)'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0)

    def test_multiline_logic(self):
        """Verify _seek logic handles line breaks correctly."""
        code = 'x = (\n    "item"\n)'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 1)

    def test_comparison_with_correct_tuple(self):
        code = 'if x in ("A", "B"): pass'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0)

    def test_ignored_contexts(self):
        """Ensure control flow groupings aren't touched."""
        code = 'assert (x == y)'
        errors = self.run_checker(code)
        self.assertEqual(len(errors), 0)

if __name__ == "__main__":
    unittest.main()