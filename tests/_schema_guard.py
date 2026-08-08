"""Schema-mutation guard — detects tests that mutate the shared test-DB schema.

Used by the ``pytest_collection_modifyitems`` hook in ``tests/conftest.py`` to
enforce that schema-mutating integration tests carry
``@pytest.mark.schema_mutating`` (they run serially in test phase 2 — see the
justfile ``test`` recipe and ``docs/development/testing-standards.md``).

Detection is AST-based: it inspects attribute accesses (``.downgrade``,
``.create_all``, ``.drop_all``) and string literals (SQL DDL like
``CREATE TABLE``, ``DROP INDEX``), excluding comments (absent from the AST) and
docstrings (identified and skipped). This avoids false positives from prose
describing what a test does. The function operates at MODULE granularity — if
any code in the module (fixture, helper, test body) mutates schema, every test
in that module must carry the marker.

This is a mitigation layer, not the root-cause fix: the true root cause is
that schema-mutating tests share a single test database. Per-test-DB isolation
(``CREATE DATABASE … TEMPLATE …``) is tracked as Q-018. Until then, this guard
ensures the two-phase serial mitigation cannot silently lapse.
"""

from __future__ import annotations

import ast
import re

# High-signal patterns matched against AST-extracted signals. Case-insensitive
# to catch both ``CREATE TABLE`` and ``create table`` SQL. ``\bdowngrade\b``
# catches both the attribute (``command.downgrade``) and the alembic CLI
# argument (``_run_alembic("downgrade", …)``) — both surface as either an
# attribute name or a string literal in the AST.
_SCHEMA_MUTATION_RE = re.compile(
    r"(?:"
    r"\bdowngrade\b"
    r"|\bcreate_all\b"
    r"|\bdrop_all\b"
    r"|create\s+table"
    r"|drop\s+table"
    r"|alter\s+table"
    r"|create\s+index"
    r"|drop\s+index"
    r"|create\s+schema"
    r"|drop\s+schema"
    r")",
    re.IGNORECASE,
)


def _docstring_node_ids(tree: ast.AST) -> set[int]:
    """Return ``id()`` of AST ``Constant`` nodes that are docstrings.

    A docstring is the first statement of a ``Module``, ``FunctionDef``,
    ``AsyncFunctionDef``, or ``ClassDef`` body, when that statement is a bare
    string expression. These are excluded from scanning so prose like "this
    test downgrades and re-upgrades" does not false-positive.
    """
    ids: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not (isinstance(body, list) and body):
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            ids.add(id(first.value))
    return ids


def scan_for_schema_mutation(source: str) -> list[str]:
    """Return schema-mutating patterns found in *source* (empty = clean).

    Inspects attribute names (``ast.Attribute.attr``) and non-docstring string
    literals (``ast.Constant`` with ``str`` value) via the AST. Comments are
    inherently absent from the AST. Returns the matched substrings so callers
    can build actionable error messages.

    A ``SyntaxError`` (e.g. source from a different Python version) yields an
    empty list — the guard is best-effort and must never block collection on a
    parse failure.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    skip = _docstring_node_ids(tree)
    signals: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            signals.append(node.attr)
        elif (
            isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip
        ):
            signals.append(node.value)

    return _SCHEMA_MUTATION_RE.findall(" ".join(signals))
