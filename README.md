# flake8-single-tuple

A focused Flake8 plugin that catches a specific class of silent runtime bug: single expressions wrapped in parentheses where a tuple was intended, in contexts where the mistake causes incorrect behavior at runtime.

## The Bug

In Python, the comma makes a tuple — not the parentheses. This is well-known. What's less appreciated is that in certain contexts the mistake is **silent and semantically wrong**, not just stylistically off:

```python
# ❌ Silent bug: iterates the string, not a membership check
if x in ("foo"):
    ...

# "b" in ("bar") → True  (checks characters of "bar")
# "bar" in ("bar") → True  (checks characters, happens to work)
# "baz" in ("bar") → False (wrong reason)

# ✅ Correct: checks membership in a single-item tuple
if x in ("foo",):
    ...
```

The bug can appear on either side of a membership test:

```python
# ❌ LHS form — equally wrong
if ("foo") in x:
    ...

# ✅ Correct
if ("foo",) in x:
    ...
```

This is not a style issue. The program runs, produces no error, and silently returns wrong results on certain inputs.

## Scope

This plugin is intentionally narrow. It only flags cases where the missing comma produces a **demonstrable runtime bug**, not cases where parentheses are merely redundant or stylistically questionable.

### What is flagged

**Membership tests** — both sides of `in` and `not in`:

```python
if x in ("foo"):          # ❌ iterates "foo"
if ("foo") in x:          # ❌ same bug, LHS form
if x not in ("bar"):      # ❌ same
if x in (a + b):          # ❌ a+b could be a container — looks like missed comma
```

**Bare string literal assignments:**

```python
x = ("foo")               # ❌ almost certainly a missed comma
x = (f"hello {name}")     # ❌ same
```

### What is not flagged

```python
# Correct tuples
if x in ("foo",): ...
if x in ("foo", "bar"): ...
x = ("foo",)

# Legitimate grouping — not our concern
x = (a + b)
x = (a or b)
x = (some_func())
x = (very_long_expression)

# Compound boolean grouping — parens are load-bearing
if (a in items and b in items): ...

# Type checkers already cover this (bool isn't iterable)
if x in (a and b): ...

# Implicit string join — parens are required
x = (
    "long string part one"
    "long string part two"
)

# Out of scope — ambiguous intent
return ("foo")
func(("item"))
assert (x == y)
```

## Installation

```bash
pip install git+https://github.com/mozartilize/flake8-single-tuple.git
```

Verify:

```bash
flake8 --version  # Should list flake8-single-tuple
```

## Error Codes

| Code | Description |
| --- | --- |
| **STC001** | Redundant parentheses in tuple-intended context; did you mean `(x,)`? |

## Technical Implementation

Python's AST discards parentheses, so detection requires a two-stage approach:

1. **AST filtering via `NodeVisitor`:** Explicit `visit_*` methods for `Compare` (membership ops only), `Assign`, and `AnnAssign` (string literals only). Controlled traversal prevents cascading duplicate reports from nested expressions.

2. **Lexical validation:** Binary search (`bisect`) locates the candidate node's token span in O(log N). The plugin then checks for an immediate `(` wrapper, verifies no trailing comma, and confirms the span contains exactly one logical expression at depth 0 — rejecting compound groupings like `(a in x and b in x)` where the parens are genuinely load-bearing.

A notable subtlety: `BinOp` candidates (e.g. `x in (a + b)`) skip the single-expression span check since their own operators appear at depth 0 inside the span. The AST boundary (`end_col_offset`) is sufficient to confirm they're a single node.

## License

MIT