# Filter Expression Syntax

Certain helper functions—most notably `Memory.search_similarity_threshold`,
`Memory.delete_documents_by_query`, and `VectorDB.search_by_metadata`—accept a
**filter expression** string that is evaluated against the metadata of each
document.

Beginning with version 0.9.x the evaluation is **sandboxed**: expressions are
parsed into an AST and must consist exclusively of a limited set of node types.
This eliminates the security risk of arbitrary code‐execution while still
allowing concise, readable filters.

## Allowed grammar (summary)

* Boolean operators: `and`, `or`, `not`
* Comparison operators: `==`, `!=`, `<`, `<=`, `>`, `>=`
* Membership operators: `in`, `not in`  (against strings or lists)
* Parentheses for grouping
* Identifiers that correspond to **metadata keys** (e.g. `area`, `score`)
* Literals: strings (`'...'` / `"..."`), integers, floats, booleans, `None`

Anything else—function calls, attribute access, comprehensions, f‐strings,
imports, etc.—is rejected with `ValueError`.

## Examples

```python
# Only memories from the main or fragments area
"area == 'MAIN' or area == 'FRAGMENTS'"

# Score threshold combined with area
"score > 0.6 and area == 'SOLUTIONS'"

# Documents for a specific URI
f"document_uri == '{uri}'"

# Case-insensitive tag comparison
"tag.lower() == 'todo'"        # ❌ rejected (function call)
"tag == 'TODO' or tag == 'todo'"  # ✔ accepted
```

## Common pitfalls

1. **No built-ins** – names like `len`, `abs`, or `datetime` are unavailable.
2. **No attribute access** – `meta.area` will fail; use plain identifiers.
3. **Undefined names** – If a key is missing in the metadata the comparison
   evaluates to `False`.

## Extending the grammar

The whitelist is defined in `python/helpers/memory.py::_get_comparator` and
`python/helpers/vector_db.py::get_comparator`.  Changes here require:

1. Updating the whitelist in both helpers.
2. Adding/adjusting unit tests in `tests/test_comparator.py`.
3. Updating this document.

Pull-requests that modify the filter language are welcome but must justify the
security implications and maintain backward compatibility.
