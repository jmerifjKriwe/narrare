#!/usr/bin/env python3
"""Intent-surface planner for the feature scaffolder (RULE-04 split).

``plan_intent()`` returns every text edit for the eight intent declaration
surfaces, cloning the route shape of the first routed sibling in a model
category. The prompt-route category comes from that sibling: model category and
prompt category are different facts, and inventing a prompt family would be
green in the parity gate but wrong elsewhere.

The bundled prompt surface is cloned from the routed sibling's own
``system.md``: its frontmatter keys, section headings and variable placeholders
are the structure a prompt must have, so re-deriving them here would be a second
source that drifts the moment ``check_prompt_structure.py`` changes. Only the
scope sentence and the two elements the structure gate mandates (a JSON example
in a structured ``Output Format`` section, four generic ``Do NOT`` items) are
generated.

This module holds no orchestration and writes nothing; ``scaffold_feature.py``
plans the feature artifacts, calls :func:`plan_intent`, and performs the atomic
write. Refusals raise ``SystemExit`` exactly as before the split.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import NoReturn

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts import _intent_surface_reader as surfaces  # noqa: E402

EXISTING_ID_EXIT = 1
GATE_FAILURE_EXIT = 2

LOCALES: tuple[str, ...] = ("en", "de", "fr")

_INTENT_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_MODE_RE = re.compile(r"^[a-z][a-z0-9_]*(?:/[a-z0-9_]+)*$")

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_VARIABLE_RE = re.compile(r"\{\{(\w+)\}\}")
_WRAPPED_VARIABLE_RE = re.compile(r"<([A-Za-z][\w:-]*)(?:\s[^<>]*)?>\s*(\{\{\w+\}\})\s*</\1>")
_SYSTEM_TITLE_RE = re.compile(r"system prompt", re.IGNORECASE)
_OUTPUT_TITLE_RE = re.compile(r"output format|ausgabeformat|format de sortie", re.IGNORECASE)
_DO_NOT_TITLE_RE = re.compile(r"do\s+not|nicht|ne\s+pas", re.IGNORECASE)

# Frontmatter values are derived from the scaffold arguments, never copied:
# a cloned ``prompt_language: en`` would be wrong in the ``de`` and ``fr`` files.
_FRONTMATTER_VERSION = '"0.1.0"'

# The structure gate requires at least four Do-NOT items. They are deliberately
# intent-agnostic: a sibling's own prohibitions describe the sibling's job.
_DO_NOT_ITEMS: tuple[str, ...] = (
    "Do NOT invent facts that are not present in the provided context.",
    "Do NOT ignore the author's preferences or avoidance patterns.",
    "Do NOT contradict the curated knowledge base or the current context.",
    "Do NOT return free-form prose where the structured output is required.",
)

_CORE = Path("packages/core/narrare_core")
_ENUMS = _CORE / "llm" / "intents" / "_enums.py"
_CATEGORIES = _CORE / "llm" / "intent_categories.py"
_PROFILES = _CORE / "llm" / "intent_profiles.py"
_ROUTE_TABLE = _CORE / "prompts" / "route_table.py"
_ROUTE_INTENTS = _CORE / "prompts" / "route_table_intents.py"
_BUNDLED = _CORE / "prompts" / "_bundled"
_MANIFEST = Path("scripts/architecture/prompt-surface-manifest.yaml")
_REGISTRY = Path("scripts/architecture/adoption-registry.yaml")

_ENUM_ANCHOR = (
    "    # ------------------------------------------------------------------\n"
    "    # Embeddings (handled separately via embeddings.py)\n"
)

_PROMPT_SENTENCES: dict[str, str] = {
    "en": (
        "You perform the {name} intent in the {category} category: "
        "produce focused, category-appropriate output for the {mode} mode."
    ),
    "de": (
        "Du bearbeitest die Absicht {name} in der Kategorie {category}: "
        "erzeuge fokussierte, kategoriegerechte Ausgaben für den Modus {mode}."
    ),
    "fr": (
        "Tu traites l'intention {name} dans la catégorie {category} : "
        "produis une sortie ciblée et adaptée à la catégorie pour le mode {mode}."
    ),
}


def fail(message: str) -> NoReturn:
    """Report a refusal on stderr and exit with the gate-failure code."""
    print(f"scaffold_feature: {message}", file=sys.stderr)
    raise SystemExit(GATE_FAILURE_EXIT)


def _read(root: Path, relative: Path) -> str:
    """Read one declaration surface, refusing loudly when it is unreadable."""
    try:
        return (root / relative).read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read declaration surface {relative}: {exc}")
        raise AssertionError("unreachable") from exc


def _tree(root: Path, relative: Path) -> ast.Module:
    """Parse a Python declaration surface with the shared reader."""
    try:
        return surfaces.parse_module(root / relative)
    except RuntimeError as exc:
        fail(str(exc))
        raise AssertionError("unreachable") from exc


def _yaml(root: Path, relative: Path) -> dict[str, object]:
    """Load a governance YAML declaration surface with the shared reader."""
    try:
        return surfaces.load_yaml(root / relative)
    except RuntimeError as exc:
        fail(str(exc))
        raise AssertionError("unreachable") from exc


def _entries(tree: ast.Module, source: str, name: str) -> dict[str, tuple[int, ast.expr, str]]:
    """Return ``{INTENT: (end_line, node, source_segment)}`` for a dict literal."""
    values = surfaces.attribute_dict(surfaces.module_assignments(tree).get(name))
    return {
        intent: (node.end_lineno or 0, node, ast.get_source_segment(source, node) or "")
        for intent, node in values.items()
    }


def _insert_after(text: str, line: int, block: str) -> str:
    """Insert *block* after 1-based *line* of *text*."""
    lines = text.splitlines(keepends=True)
    lines.insert(line, block)
    return "".join(lines)


def _insert_before(text: str, marker: str, block: str, label: str) -> str:
    """Insert *block* before the unique *marker*; refuse when it is not unique."""
    if text.count(marker) != 1:
        fail(f"cannot locate the insertion anchor in {label}")
    return text.replace(marker, block + marker, 1)


def _keyword(call: ast.expr, name: str, source: str) -> str | None:
    """Return the source text of a call keyword, or ``None``."""
    if isinstance(call, ast.Call):
        for keyword in call.keywords:
            if keyword.arg == name:
                return ast.get_source_segment(source, keyword.value)
    return None


def _call(head: str, arguments: list[str]) -> str:
    """Render one dict entry as ``head(...)``, wrapping at the project line limit."""
    one_line = f"    {head}({', '.join(arguments)}),\n"
    # Matches [tool.ruff] line-length; generated Python must survive `ruff format`.
    if len(one_line.rstrip("\n")) <= 100:
        return one_line
    body = "".join(f"        {argument},\n" for argument in arguments)
    return f"    {head}(\n{body}    ),\n"


def _validate_intent(name: str, category: str | None, mode: str | None) -> tuple[str, str, str]:
    """Return ``(ENUM_NAME, slug, mode)`` or exit 2 naming what is missing."""
    if category is None or mode is None:
        fail("--with-intent requires both --category and --mode")
    if not _INTENT_NAME_RE.fullmatch(name):
        fail(f"invalid intent name '{name}' — use a snake_case identifier such as parity_probe")
    if not _MODE_RE.fullmatch(mode):
        fail(f"invalid mode '{mode}' — use a snake_case path such as parity_mode")
    return name.upper(), name.lower(), mode


def _sibling(
    category: str,
    category_entries: dict[str, tuple[int, ast.expr, str]],
    route_configs: dict[str, tuple[int, ast.expr, str]],
    non_routeable: set[str],
    members: dict[str, str],
) -> tuple[str, str]:
    """Return ``(sibling, prompt_category)`` for the first routed sibling."""
    for intent, (_, node, _) in category_entries.items():
        if not isinstance(node, ast.Attribute) or members.get(node.attr) != category:
            continue
        if intent in non_routeable or intent not in route_configs:
            continue
        prompt_category, prompt_mode = surfaces.route_config(route_configs[intent][1])
        if prompt_category is not None and prompt_mode is not None:
            return intent, prompt_category
    fail(f"no routed sibling in category '{category}' — nothing written")
    raise AssertionError("unreachable")


def _manifest_fields(block: list[str], key: str, default: str) -> str:
    """Return the first ``key: value`` line of a manifest block, after strip."""
    return next(
        (line.split(":", 1)[1].strip() for line in block if line.startswith(f"{key}:")),
        default,
    )


def _manifest_span(lines: list[str], sibling: str) -> tuple[int, int]:
    """Return the ``[start, end)`` line span of the sibling's manifest block."""
    try:
        start = lines.index(f"  - intent: {sibling}")
    except ValueError:
        fail(f"{_MANIFEST} has no block for sibling '{sibling}'")
        raise AssertionError("unreachable") from None
    end = start + 1
    while end < len(lines) and not lines[end].startswith(("  - intent: ", "  #")):
        end += 1
    return start, end


def _manifest_block(
    lines: list[str], sibling: str, name: str, category: str, mode: str, template: str
) -> str:
    """Clone the sibling's manifest block with the new identity, mode and template."""
    start, end = _manifest_span(lines, sibling)
    block = [line.strip() for line in lines[start:end] if line.strip()]
    values = {
        key: _manifest_fields(block, key, default)
        for key, default in (
            ("content_type", "customizable_feature_prompt"),
            ("output_language_variable", "null"),
            ("required_variables", "[]"),
            ("optional_variables", "[]"),
            ("xml_required", "[]"),
            ("generated_suggestions_must_be_labelled", "[]"),
            ("fallback_policy", "fail_loudly_if_bundled_missing"),
        )
    }
    return "\n".join(
        (
            f"  - intent: {name}",
            "    routeable: true",
            f"    category: {category}",
            f"    mode: {mode}",
            f"    template: {template}",
            f"    content_type: {values['content_type']}",
            f"    output_language_variable: {values['output_language_variable']}",
            f"    required_variables: {values['required_variables']}",
            f"    optional_variables: {values['optional_variables']}",
            "    security:",
            f"      xml_required: {values['xml_required']}",
            (
                "      generated_suggestions_must_be_labelled: "
                f"{values['generated_suggestions_must_be_labelled']}"
            ),
            f"    fallback_policy: {values['fallback_policy']}",
        )
    )


def _insert_manifest(text: str, sibling: str, block: str) -> str:
    """Insert *block* after the sibling's manifest block, keeping comments intact."""
    lines = text.splitlines()
    start, end = _manifest_span(lines, sibling)
    last = max(index for index in range(start, end) if lines[index].strip())
    lines[last + 1 : last + 1] = ["", *block.splitlines()]
    return "\n".join(lines) + "\n"


def _insert_registry(text: str, sibling_key: str, key: str) -> str:
    """Insert ``key: true`` after the sibling's compliance entry."""
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith(f"  {sibling_key}:"):
            lines.insert(index + 1, f"  {key}: true\n")
            return "".join(lines)
    fail(f"{_REGISTRY} has no prompt_path_compliance entry '{sibling_key}'")
    raise AssertionError("unreachable")


def _prompt_path(category: str, locale: str, mode: str) -> Path:
    """Return the bundled prompt path for one intent locale."""
    return _BUNDLED / category / locale / mode / "system.md"


def _prompt_source(root: Path, category: str, mode: str) -> str:
    """Read the routed sibling's bundled EN prompt — the structure being cloned."""
    relative = _prompt_path(category, "en", mode)
    try:
        return (root / relative).read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read the sibling prompt template {relative}: {exc}")
        raise AssertionError("unreachable") from exc


def _frontmatter_block(template: str, *, category: str, locale: str) -> str:
    """Copy the sibling's frontmatter keys in order, deriving every value."""
    match = _FRONTMATTER_RE.match(template)
    if match is None:
        fail("the sibling prompt has no YAML frontmatter to clone")
    values = {
        "prompt_type": category,
        "prompt_language": locale,
        "prompt_version": _FRONTMATTER_VERSION,
    }
    lines = ["---"]
    for line in match.group(1).splitlines():
        key, separator, _ = line.partition(":")
        if not separator:
            continue
        key = key.strip()
        if key not in values:
            fail(
                f"sibling frontmatter key '{key}' has no derivable value — "
                "teach scripts/scaffold_intent.py how to generate it"
            )
        lines.append(f"{key}: {values[key]}")
    if len(lines) == 1:
        fail("the sibling prompt's frontmatter declares no usable keys")
    lines.append("---")
    return "\n".join(lines)


def _sections(text: str) -> list[tuple[str, list[str]]]:
    """Split a prompt into ``(heading, body lines)`` pairs after the frontmatter."""
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        fail("the sibling prompt has no YAML frontmatter to clone")
    sections: list[tuple[str, list[str]]] = []
    in_fence = False
    for line in text[match.end() :].splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and _HEADING_RE.match(line):
            sections.append((line.rstrip(), []))
        elif sections:
            sections[-1][1].append(line)
    if not sections:
        fail("the sibling prompt has no section headings to clone")
    return sections


def _heading_title(heading: str) -> str:
    """Return a heading's text without its hashes."""
    match = _HEADING_RE.match(heading)
    return match.group(2) if match is not None else heading


def _variable_expressions(lines: list[str]) -> list[str]:
    """Return the placeholders of one section in order, XML wrappers included."""
    body = "\n".join(lines)
    wrapped = [(m.start(), m.end(), m.group(0)) for m in _WRAPPED_VARIABLE_RE.finditer(body)]
    expressions: list[str] = []
    for match in _VARIABLE_RE.finditer(body):
        expression = match.group(0)
        for start, end, wrapped_text in wrapped:
            if start <= match.start() and match.end() <= end:
                expression = wrapped_text
                break
        if expression not in expressions:
            expressions.append(expression)
    return expressions


def _has_json_block(lines: list[str]) -> bool:
    """True when a section body holds the fenced JSON example the gate asks for."""
    in_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_block = not in_block
        elif in_block and stripped.startswith(("{", "[")):
            return True
    return False


def _json_example(slug: str) -> str:
    """Render the minimal JSON example a structured output section must show."""
    return "\n".join(
        (
            "```json",
            "{",
            f'  "intent": "{slug}",',
            '  "result": "<replace with the intent\'s output contract>",',
            '  "notes": []',
            "}",
            "```",
        )
    )


def _section_body(heading: str, body: list[str], *, scope: str, slug: str) -> list[str]:
    """Rebuild one section: placeholders stay, the sibling's prose becomes *scope*."""
    title = _heading_title(heading)
    placeholders = [f"- {expression}" for expression in _variable_expressions(body)]
    if _DO_NOT_TITLE_RE.search(title):
        return [*(f"- {item}" for item in _DO_NOT_ITEMS), *placeholders]
    if _OUTPUT_TITLE_RE.search(title):
        example = [_json_example(slug)] if _has_json_block(body) else []
        return [*example, *placeholders]
    if _SYSTEM_TITLE_RE.search(title):
        return [scope, *placeholders]
    return placeholders


def _prompt_text(
    *, template: str, sibling: str, slug: str, category: str, mode: str, locale: str
) -> str:
    """Clone the sibling's structure and fill it with the new intent's scope.

    Frontmatter keys, section headings and variable placeholders come from the
    sibling, so a prompt this scaffolder writes cannot drift from
    ``check_prompt_structure.py``. Generated are the scope sentence, the four
    generic ``Do NOT`` items, and — when the sibling's output section carries a
    JSON example — a minimal example of our own. A section with neither prose
    nor placeholders keeps its heading and stays empty for the author to fill.
    """
    scope = _PROMPT_SENTENCES[locale].format(name=slug, category=category, mode=mode)
    blocks = [
        _frontmatter_block(template, category=category, locale=locale),
        "<!-- Generated by scripts/scaffold_feature.py (--with-intent). -->",
        f"<!-- Structure cloned from the sibling prompt {sibling}. -->",
    ]
    for heading, body in _sections(template):
        lines = _section_body(heading, body, scope=scope, slug=slug)
        blocks.append("\n".join((heading, "", *lines)) if lines else heading)
    return "\n\n".join(blocks) + "\n"


def plan_intent(name: str, category: str | None, mode: str | None, root: Path) -> dict[Path, str]:
    """Return every text edit for the eight intent surfaces, or exit 1/2."""
    enum_name, slug, mode = _validate_intent(name, category, mode)
    assert category is not None
    decl_paths = (
        _ENUMS,
        _CATEGORIES,
        _PROFILES,
        _ROUTE_TABLE,
        _ROUTE_INTENTS,
        _MANIFEST,
        _REGISTRY,
    )
    source = {path: _read(root, path) for path in decl_paths}
    tree = {path: _tree(root, path) for path in decl_paths[:5]}
    enums = surfaces.class_members(tree[_ENUMS], "LLMIntent")
    members = surfaces.class_members(tree[_CATEGORIES], "IntentCategory")
    member = next((key for key, value in members.items() if value == category), None)
    if member is None:
        fail(f"unknown category '{category}' — choose from {', '.join(sorted(members.values()))}")
    cat = _entries(tree[_CATEGORIES], source[_CATEGORIES], "INTENT_CATEGORY_MAP")
    prof = _entries(tree[_PROFILES], source[_PROFILES], "INTENT_PROFILES")
    cfg = _entries(tree[_ROUTE_TABLE], source[_ROUTE_TABLE], "ROUTE_CONFIGS")
    blocked = set(_entries(tree[_ROUTE_TABLE], source[_ROUTE_TABLE], "NON_ROUTEABLE_INTENTS"))
    rcat = _entries(tree[_ROUTE_INTENTS], source[_ROUTE_INTENTS], "INTENT_TO_CATEGORY")
    rmode = _entries(tree[_ROUTE_INTENTS], source[_ROUTE_INTENTS], "INTENT_TO_MODE")
    sibling, prompt_category = _sibling(category, cat, cfg, blocked, members)
    sibling_mode = surfaces.route_config(cfg[sibling][1])[1] or ""
    key = f"{prompt_category}/{mode}"
    prompts = {locale: _prompt_path(prompt_category, locale, mode) for locale in LOCALES}
    manifest = _yaml(root, _MANIFEST)
    manifest_intents = {
        str(block["intent"])
        for block in surfaces.mapping_entries(manifest.get("routes"))
        if "intent" in block
    }
    compliance = _yaml(root, _REGISTRY).get("prompt_path_compliance")
    checks = {
        "enums": enum_name in enums,
        "INTENT_CATEGORY_MAP": enum_name in cat,
        "INTENT_TO_CATEGORY": enum_name in rcat,
        "INTENT_TO_MODE": enum_name in rmode,
        "INTENT_PROFILES": enum_name in prof,
        "ROUTE_CONFIGS": enum_name in cfg,
        "prompt-surface-manifest.yaml": enum_name in manifest_intents,
        "prompt_path_compliance": isinstance(compliance, dict) and key in compliance,
        "prompt template": any((root / path).exists() for path in prompts.values()),
    }
    declared = [label for label, present in checks.items() if present]
    if declared:
        print(
            f"scaffold_feature: refusing to write — intent {enum_name} already "
            f"declared in: {', '.join(declared)}",
            file=sys.stderr,
        )
        raise SystemExit(EXISTING_ID_EXIT)

    profile, call = prof[sibling][1], cfg[sibling][1]
    if not isinstance(profile, ast.Call) or len(profile.args) < 2 or not isinstance(call, ast.Call):
        fail(f"sibling '{sibling}' has no usable INTENT_PROFILES/ROUTE_CONFIGS entry")
    output = surfaces.string_value(profile.args[0])
    tier = surfaces.string_value(profile.args[1])
    if output is None or tier is None:
        fail(f"INTENT_PROFILES entry for sibling '{sibling}' has no usable profile")
    summary = f"{slug.replace('_', ' ').capitalize()} intent in the {category} category."
    arguments = [f'"{prompt_category}"', f'"{mode}"']
    arguments.extend(
        f"{field}={value}"
        for field in ("required_variables", "optional_variables")
        if (value := _keyword(call, field, source[_ROUTE_TABLE]))
    )
    route = _call(f"LLMIntent.{enum_name}: PromptRouteConfig", arguments)
    manifest_block = _manifest_block(
        source[_MANIFEST].splitlines(),
        sibling,
        enum_name,
        prompt_category,
        mode,
        prompts["en"].as_posix(),
    )
    writes = {
        _ENUMS: _insert_before(
            source[_ENUMS],
            _ENUM_ANCHOR,
            "    # Scaffolded intent (scripts/scaffold_feature.py).\n"
            f'    {enum_name} = "{slug}"\n    """{summary}"""\n\n',
            _ENUMS.as_posix(),
        ),
        _CATEGORIES: _insert_after(
            source[_CATEGORIES],
            cat[sibling][0],
            f"    LLMIntent.{enum_name}: IntentCategory.{member},\n",
        ),
        _PROFILES: _insert_after(
            source[_PROFILES],
            prof[sibling][0],
            _call(
                f"LLMIntent.{enum_name}: IntentProfile",
                [f'"{output}"', f'"{tier}"', f'"{summary}"'],
            ),
        ),
        _ROUTE_TABLE: _insert_after(source[_ROUTE_TABLE], cfg[sibling][0], route),
        # Insert the later dict first so the earlier insertion cannot shift its line.
        _ROUTE_INTENTS: _insert_after(
            _insert_after(
                source[_ROUTE_INTENTS],
                rmode[sibling][0],
                f'    LLMIntent.{enum_name}: "{mode}",\n',
            ),
            rcat[sibling][0],
            f'    LLMIntent.{enum_name}: "{prompt_category}",\n',
        ),
        _MANIFEST: _insert_manifest(source[_MANIFEST], sibling, manifest_block),
        _REGISTRY: _insert_registry(source[_REGISTRY], f"{prompt_category}/{sibling_mode}", key),
    }
    template = _prompt_source(root, prompt_category, sibling_mode)
    sibling_prompt = _prompt_path(prompt_category, "en", sibling_mode).as_posix()
    writes.update(
        {
            path: _prompt_text(
                template=template,
                sibling=sibling_prompt,
                slug=slug,
                category=prompt_category,
                mode=mode,
                locale=locale,
            )
            for locale, path in prompts.items()
        }
    )
    return writes
