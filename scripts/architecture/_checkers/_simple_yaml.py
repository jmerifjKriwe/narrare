"""Minimal YAML parser for architecture manifests (stdlib only).

Handles the subset of YAML used by ``prompt-surface-manifest.yaml``:

- Top-level ``key: value`` pairs
- Quoted and unquoted scalars
- Inline lists ``[a, b, c]``
- Block lists with ``- `` items
- Nested dicts via indentation
- ``null`` / ``~`` as None

Does NOT handle anchors, aliases, multiline strings, or flow collections
beyond inline lists syntax.
"""

from __future__ import annotations

from typing import Any

__all__ = ["parse_simple_yaml"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse a simple YAML document into a dict."""
    lines = text.splitlines()
    return _parse_yaml_block(lines, 0, 0)[0]


# ---------------------------------------------------------------------------
# Scalar conversion
# ---------------------------------------------------------------------------


def _parse_inline_list(text: str) -> list[str] | None:
    """Parse ``[a, b, c]`` inline YAML list notation.

    Returns a list of stripped strings, or None if not an inline list.
    """
    stripped = text.strip()
    if not stripped.startswith("[") or not stripped.endswith("]"):
        return None
    inner = stripped[1:-1].strip()
    if not inner:
        return []
    return [item.strip().strip("\"'") for item in inner.split(",")]


def _yaml_value(raw: str) -> Any:
    """Convert a YAML scalar string to a Python value."""
    stripped = raw.strip()
    if stripped in ("null", "~", ""):
        return None
    # Inline list: [a, b, c]
    inline = _parse_inline_list(stripped)
    if inline is not None:
        return inline
    if stripped.startswith('"') and stripped.endswith('"'):
        return stripped[1:-1]
    if stripped.startswith("'") and stripped.endswith("'"):
        return stripped[1:-1]
    if stripped.lower() in ("true", "yes"):
        return True
    if stripped.lower() in ("false", "no"):
        return False
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        pass
    return stripped


# ---------------------------------------------------------------------------
# Indentation
# ---------------------------------------------------------------------------


def _indent_of(line: str) -> int:
    """Return the number of leading spaces."""
    return len(line) - len(line.lstrip())


# ---------------------------------------------------------------------------
# Block parsing
# ---------------------------------------------------------------------------


def _parse_yaml_block(
    lines: list[str],
    start: int,
    base_indent: int,
) -> tuple[dict[str, Any], int]:
    """Parse a YAML block starting at *start* with indentation *base_indent*.

    Returns (parsed_dict, next_line_index).
    """
    result: dict[str, Any] = {}
    i = start

    while i < len(lines):
        line = lines[i]

        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue

        indent = _indent_of(line)
        if indent < base_indent:
            break

        stripped = line.strip()

        if stripped.startswith("- ") and indent == base_indent:
            break

        if ":" in stripped:
            colon_pos = stripped.index(":")
            key = stripped[:colon_pos].strip()
            value_part = stripped[colon_pos + 1 :].strip()

            if value_part:
                result[key] = _yaml_value(value_part)
                i += 1
            else:
                i += 1
                while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith("#")):
                    i += 1

                if i < len(lines):
                    next_indent = _indent_of(lines[i])
                    if next_indent > indent:
                        next_stripped = lines[i].strip()
                        if next_stripped.startswith("- "):
                            result[key], i = _parse_yaml_list(lines, i, next_indent)
                        else:
                            result[key], i = _parse_yaml_block(lines, i, next_indent)
                    else:
                        result[key] = None
                else:
                    result[key] = None
        else:
            i += 1

    return result, i


def _parse_yaml_list(
    lines: list[str],
    start: int,
    base_indent: int,
) -> tuple[list[Any], int]:
    """Parse a YAML list (sequence of ``- `` items).

    Returns (parsed_list, next_line_index).
    """
    result: list[Any] = []
    i = start

    while i < len(lines):
        line = lines[i]

        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue

        indent = _indent_of(line)
        if indent < base_indent:
            break

        stripped = line.strip()
        if not stripped.startswith("- "):
            break

        item_text = stripped[2:].strip()

        if ":" in item_text:
            item_dict: dict[str, Any] = {}
            item_indent = indent + 2

            colon_pos = item_text.index(":")
            first_key = item_text[:colon_pos].strip()
            first_val = item_text[colon_pos + 1 :].strip()
            if first_val:
                item_dict[first_key] = _yaml_value(first_val)
            i += 1

            while i < len(lines):
                sub_line = lines[i]
                if not sub_line.strip() or sub_line.strip().startswith("#"):
                    i += 1
                    continue

                sub_indent = _indent_of(sub_line)
                if sub_indent < item_indent:
                    break

                sub_stripped = sub_line.strip()
                if sub_stripped.startswith("- "):
                    break

                if ":" in sub_stripped:
                    sc = sub_stripped.index(":")
                    sk = sub_stripped[:sc].strip()
                    sv = sub_stripped[sc + 1 :].strip()

                    if sv:
                        item_dict[sk] = _yaml_value(sv)
                        i += 1
                    else:
                        i += 1
                        while i < len(lines) and (
                            not lines[i].strip() or lines[i].strip().startswith("#")
                        ):
                            i += 1
                        if i < len(lines):
                            ni = _indent_of(lines[i])
                            if ni > sub_indent:
                                ns = lines[i].strip()
                                if ns.startswith("- "):
                                    item_dict[sk], i = _parse_yaml_list(lines, i, ni)
                                else:
                                    item_dict[sk], i = _parse_yaml_block(lines, i, ni)
                            else:
                                item_dict[sk] = None
                        else:
                            item_dict[sk] = None
                else:
                    break

            result.append(item_dict)
        else:
            result.append(_yaml_value(item_text))
            i += 1

    return result, i
