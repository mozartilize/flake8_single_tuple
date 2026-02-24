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

## Features

This plugin uses a hybrid approach of **AST Context Analysis** and **Lexical Token Scanning** to ensure high accuracy:

* **Context-Aware:** Only checks areas where a tuple is logically expected (Assignments, `in` comparisons, and Function arguments).
* **Semantic Intelligence:** Automatically ignores groupings that are common for readability, such as **Lambdas**, **Ternary expressions** (`a if b else c`), and **Generator expressions**.
* **Format Agnostic:** Robust against comments, multi-line indentation, and varied whitespace.
* **Performance Optimized:** Uses binary search (`bisect`) for $O(\log N)$ token lookups and a memory-efficient generator-based tokenizer.

## Installation

1. Install via pip:
```bash
pip install git+https://github.com/mozartilize/flake8-single-tuple.git

```


2. Verify installation:
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
x = ("only_item")       # Mistaken for tuple
if x in ("A"):          # Membership bug
func(("item"))          # Redundant double-wrap
x = ((1,))              # Redundant outer wrap around a valid tuple
x = (lambda x: x + 1)   # Redundant grouping around a lambda

```

### ✅ Ignored (Valid Code)

```python
# Proper Single-Item Tuples
x = ("a",)
if x in ("foo", "bar"):
    ...

# Required Parentheses (Generators)
# These never use commas but require parens
x = (i for i in range(10))

# Standard Contexts (Ignored to avoid noise)
assert (x == y)
return (value)

# Readability Groupings (Ignored)
item = (
    parsed["data"][i]
    if i <= len(parsed["data"])
    else {}
)

```

## Technical Implementation

Because Python's AST discards parentheses during the parsing phase, this plugin utilizes a **two-stage verification process**:

1. **AST Filtering:** The plugin walks the AST to find "suspect" contexts (Assignments, `Compare` nodes with `In` ops, and `Call` arguments).
2. **Lexical Validation:** Once a suspect node is found, the plugin performs a binary search on the source token stream. It locates the specific span of the node and checks for an immediate `(` wrapper. If a wrapper is found, it scans for a top-level comma at `depth=0`. If no comma exists, a violation is raised.

## License

MIT
