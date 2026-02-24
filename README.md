# flake8-single-tuple

A high-performance, robust Flake8 plugin that detects single-item tuples missing their trailing comma.

## The Problem

In Python, parentheses do not create a tuple—the **comma** does. This often leads to logical bugs where a developer intends to create a container but accidentally creates a simple grouped expression. This is particularly dangerous in membership tests:

```python
# ❌ Logical Bug: This checks if x is a character in the string "foo"
# Returns True if x is "f", "o", or ""
if x in ("foo"):
    ...

# ✅ Correct: This checks if x is exactly the string "foo"
if x in ("foo",):
    ...
```

The bug can appear on **either side** of a membership test:

```python
# ❌ Also a bug — LHS is a grouped string, not a single-item tuple
if ("foo") in x:
    ...

# ✅ Correct
if ("foo",) in x:
    ...
```

## Features

This plugin uses a hybrid approach of **AST Context Analysis** and **Lexical Token Scanning** to ensure high accuracy:

* **Context-Aware:** Only checks areas where a tuple is logically expected: assignments, `in`/`not in` comparisons (both sides), function arguments, `return`, and `yield`.
* **Full Membership Coverage:** Flags redundant parentheses on both the left-hand and right-hand sides of `in` and `not in` expressions.
* **Semantic Intelligence:** Automatically ignores groupings that are common for readability, such as **ternary expressions** (`a if b else c`), **binary operations**, and **generator expressions** when used as bare call arguments.
* **Precise Traversal:** Uses `ast.NodeVisitor` for controlled, non-duplicating tree traversal — no cascading false positives from nested expressions.
* **Format Agnostic:** Robust against comments, multi-line indentation, and varied whitespace.
* **Performance Optimized:** Uses binary search (`bisect`) for $O(\log N)$ token lookups and a memory-efficient generator-based tokenizer.

## Installation

Install via pip:

```bash
pip install git+https://github.com/mozartilize/flake8-single-tuple.git
```

Verify installation:

```bash
flake8 --version  # Should list flake8-single-tuple
```

## Error Codes

| Code | Description |
| --- | --- |
| **STC001** | Redundant parentheses or missing trailing comma; did you mean `(x,)`? |

## Examples

### ❌ Triggers a warning (STC001)

```python
x = ("only_item")          # Assignment — mistaken for tuple
x = (f"hello {name}")      # f-string — missing trailing comma
x = ((1,))                 # Redundant outer wrap around a valid tuple
x = (lambda x: x + 1)     # Redundant grouping around a lambda
x = ((i for i in y))      # Redundant outer wrap around a generator

if x in ("A"):             # Membership — RHS should be a tuple
if ("A") in x:             # Membership — LHS should be a tuple
if ("A") in ("B"):         # Both sides flagged independently

func(("item"))             # Call argument — redundant double-wrap
```

### ✅ Ignored (Valid Code)

```python
# Proper single-item tuples
x = ("a",)
if x in ("foo", "bar"): ...
if ("foo",) in x: ...

# Generator expressions — parens are required, comma is never used
x = (i for i in range(10))
total = sum(i * 2 for i in range(10))  # call's parens serve the generator

# assert — excluded to avoid noise on common guard patterns
assert (x == y)

# Readability groupings
item = (
    parsed["data"][i]
    if i <= len(parsed["data"])
    else {}
)
```

## Technical Implementation

Because Python's AST discards parentheses during the parsing phase, this plugin uses a **two-stage verification process**:

1. **AST Filtering via `NodeVisitor`:** The plugin subclasses `ast.NodeVisitor` and implements explicit `visit_*` methods for each relevant node type (`Assign`, `AnnAssign`, `Return`, `Yield`, `Compare`, `Call`). This provides fine-grained traversal control and prevents cascading duplicate reports from nested expressions. For `Compare` nodes, both `node.left` and each comparator are checked when the operator is `In` or `NotIn`.

2. **Lexical Validation:** Once a candidate node is identified, the plugin performs a binary search on the pre-sorted source token stream to locate the node's span in $O(\log N)$. It then walks backward to detect an immediate `(` wrapper. If found, it scans the span for a top-level comma at `depth=0`. If no comma exists, a violation is raised at the position of the opening parenthesis.

A notable subtlety: `GeneratorExp` nodes in the AST have their `col_offset` pointing *inside* their required surrounding `(`, so a bare `x = (i for i in y)` naturally produces no false positive — the paren the checker finds is the generator's own required paren, and its closing `)` sits at the node boundary rather than beyond it. A double-wrapped `x = ((i for i in y))` is still correctly flagged because the redundant outer pair clears that boundary check.

## License

MIT
