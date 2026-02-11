# flake8-single-tuple

A Flake8 plugin that warns when a developer writes what appears to be a single-item tuple but omits the required trailing comma.

## The Problem

In Python, parentheses do not create a tuple—the **comma** does. This leads to common logical bugs, especially in membership tests where a string is mistaken for a container:

```python
# ❌ Logical Bug: This checks if x is a character in the string "foo"
# This is TRUE if x is "", "f", or "fo"
if x in ("foo"): 
    ...

# ✅ Correct: This checks if x is exactly the string "foo"
if x in ("foo",):
    ...

```

## Features

This plugin detects "pseudo-tuples" across various contexts while strictly avoiding false positives from legitimate groupings:

* **Membership Tests:** Detects `if x in ("a")`.
* **Assignments:** Detects `x = ("a")`.
* **Double-wrapped Arguments:** Detects `func(("a"))`.
* **Multi-line Support:** Handles expressions spanning multiple lines with varied indentation.
* **Nested Parentheses:** Detects redundant layers like `x = (("a"))`.

## Installation

1. pip install git+https://github.com/mozartilize/flake8-single-tuple.git


2. Verify installation:
```bash
flake8 --version  # Should list flake8-single-tuple

```


## Error Codes

| Code | Description |
| --- | --- |
| **STC001** | Single-item tuple missing trailing comma; did you mean `(x,)`? |

## Examples

### ❌ Triggers a warning (STC001)

```python
x = ("a")
y = (item)
foo(("bar"))
if x in ("jam"):
    ...
elif y in (
    "jar"
):
    ...

```

### ✅ Ignored (Valid Code)

```python
# Proper Tuples
x = ("a",)
if x in ("foo", "bar"):
    ...

# Legitimate Grouping (Arithmetic/Return)
result = (a + b) * c
return (value)

# Control Flow
if (condition):
    ...

# Standard Function Calls (Mandatory Syntax)
s.get("foo").upper()
len(x)

```

## Technical Implementation

Because Python's Abstract Syntax Tree (AST) discards parentheses during parsing, this plugin uses **source-code pointer walking**. It identifies specific nodes in the AST (Constants, Names, Attributes) and then inspects the raw source text boundaries to see if redundant parentheses wrap the node without a comma being present in that span.

## License

MIT
