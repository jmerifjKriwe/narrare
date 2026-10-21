"""Agent-name doc-drift validator.

Prevents the recurring structural pattern where documentation references
subagent names that do not match the real definitions in
``.opencode/agents/*.md`` (review-04 AUFG-04-15
root cause: invented ``subagent_type`` values cause silent routing
failures when a coordinator follows stale docs).

Approach:
    1. Derive the real subagent names from the **file names** of every
       ``.opencode/agents/*.md`` file. OpenCode derives the agent id from
       the file path, *not* from a frontmatter field — there is no
       ``name:`` key in the v2 agent schema. A file named
       ``NarrareBuilder.md`` registers as exactly
       ``NarrareBuilder``. Files with ``mode: primary`` are excluded
       because they are not ``subagent_type`` values.
    2. Scan ``AGENTS.md`` and ``docs/**/*.md`` for:
       a. ``subagent_type="..."`` — any value not in the real set is flagged.
       b. Backtick-wrapped `` `narrare-<word>` `` identifiers — kebab-case
          narrare identifiers are never valid ``subagent_type`` values
          (real names are PascalCase like ``NarrareBuilder``).
    3. Report findings as critical.

Exclusions:
    - Package-install context (``pip install narrare-core``, extras like
      ``narrare-core[memory]``) — ``narrare-core`` is a real pip package name.
    - Directory-path context (``narrare-dev/``, ``agents/subagents/``).
    - Negation context ("does not exist", "NIEMALS", "never use",
      "erfundene") — explanatory text telling readers a name does NOT exist.
    - Historical/archived directories (same as just_command_checks).
    - Superseded/deprecated ADRs.

See: docs/_shared/CONSTRAINTS.md §8 (SSOT hierarchy).
     review-04-dx-tooling.md AUFG-04-15.
"""

from __future__ import annotations

import re
from pathlib import Path

from doc_drift import safe_relative
from doc_drift.adr_checks import DocDriftFinding

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AGENTS_DIR = REPO_ROOT / ".opencode" / "agents"
_DOCS_DIR = REPO_ROOT / "docs"
_AGENTS_MD = REPO_ROOT / "AGENTS.md"

# Human-readable location of the agent definitions, for finding messages.
_AGENTS_DIR_DISPLAY = ".opencode/agents/"

# ── Real subagent name extraction ───────────────────────────────

# Frontmatter ``mode:`` field, used to exclude primary agents (the
# coordinator) — only ``mode: subagent`` agents are valid ``subagent_type``
# values.
_FRONTMATTER_MODE_RE = re.compile(r"^mode:\s*(\S+)", re.MULTILINE)


def get_real_subagent_names(agents_dir: Path | None = None) -> frozenset[str]:
    """Extract real subagent names from agent definition file names.

    OpenCode derives the agent id from the file path (relative to the agent
    directory, minus the ``.md`` suffix) — it does **not** read a frontmatter
    ``name:`` field, which no longer exists in the v2 agent schema. This
    function mirrors that resolution so the check validates names the
    runtime can actually resolve.

    Files declaring ``mode: primary`` are skipped: they are primary agents,
    not dispatchable ``subagent_type`` values.

    *agents_dir* defaults to ``.opencode/agents/``.
    """
    effective_dir = agents_dir or _AGENTS_DIR
    names: set[str] = set()
    if not effective_dir.is_dir():
        return frozenset()
    for md_file in sorted(effective_dir.rglob("*.md")):
        name = md_file.relative_to(effective_dir).with_suffix("").as_posix()
        # Skip example/template placeholders like "[Feature Name]".
        if not name or name.startswith("["):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
        except OSError:
            continue
        frontmatter = _extract_frontmatter(content)
        mode_match = _FRONTMATTER_MODE_RE.search(frontmatter) if frontmatter else None
        if mode_match and mode_match.group(1).strip() == "primary":
            continue
        names.add(name)
    return frozenset(names)


def _extract_frontmatter(content: str) -> str | None:
    """Return the YAML frontmatter block (between ``---`` delimiters).

    Returns ``None`` if no frontmatter block is found.
    """
    lines = content.splitlines()
    if not lines or not lines[0].strip().startswith("---"):
        return None
    # Find the closing ``---``.
    for i in range(1, len(lines)):
        if lines[i].strip().startswith("---"):
            return "\n".join(lines[1:i])
    return None


# ── Doc scanning ────────────────────────────────────────────────

# Known fake agent names that have appeared in docs. These are the kebab-case
# identifiers that were used as invented ``subagent_type`` values before the
# real definitions were synchronized. Using a targeted set avoids false
# positives on legitimate identifiers like ``narrare-api`` (OTel service name)
# or ``narrare-dev`` (directory).
_KNOWN_FAKE_AGENT_NAMES: frozenset[str] = frozenset(
    {
        "narrare-architecture",
        "narrare-implementation",
        "narrare-testing",
        "narrare-ui",
        "narrare-deployment",
        "narrare-documentation",
        "narrare-core",
        "narrare-backend",
        "narrare-frontend",
        "narrare-platform",
    }
)

# Built-in OpenCode subagent types that are NOT narrare specialists but ARE
# valid ``subagent_type`` values. ``general`` is the general-purpose agent
# used for last-resort delegation.
_BUILTIN_SUBAGENT_TYPES: frozenset[str] = frozenset({"general"})

# Placeholder values for ``subagent_type="..."`` in template/example text.
_PLACEHOLDER_RE = re.compile(r"^(?:\.\.\.|<[^>]+>|\{[^}]+\})$")

# Pattern for ``subagent_type="<value>"`` or ``subagent_type='<value>'``.
_SUBAGENT_TYPE_RE = re.compile(r'subagent_type\s*=\s*["\']([^"\']+)["\']')

# Pattern for backtick-wrapped `` `narrare-<word>` `` identifiers.
# The word must start with a lowercase letter (kebab-case).
_BACKTICK_NARRARE_RE = re.compile(r"`(narrare-[a-z][a-z0-9-]*)`")

# Lines that reference narrare as a package/directory, not an agent.
# ``pip install narrare-core``, ``narrare-core[memory]``, ``narrare-dev/``.
_PACKAGE_CONTEXT_RE = re.compile(
    r"pip\s+install"
    r"|narrare-[a-z]+\[",  # extras syntax: narrare-core[memory]
    re.IGNORECASE,
)

# Negation indicators — when present on the same line as a narrare-* reference,
# the reference is explanatory (telling readers the name does NOT exist).
_NEGATION_RE = re.compile(
    r"(?i)"
    r"(?:[Nn]o\s+`narrare"  # "No `narrare-foo`"
    r"|not\s+`narrare"  # "not `narrare-foo`"
    r"|does\s+not\s+exist"  # "narrare-foo does not exist"
    r"|doesn.t\s+exist"
    r"|\bNIEMALS\b"  # German: "never"
    r"|\bnever\s+use"  # "never use narrare-foo"
    r"|\bnever\s+invent"  # "never invent narrare-foo"
    r"|\berfundene\b"  # German: "invented/fake"
    r"|\bfake\b"  # "fake name"
    r"|\binvented\b"  # "invented name"
    r"|\bnon-existent\b"  # "non-existent name"
    r"|\bwrong\b"  # "wrong name"
    r"|zu\s+verwenden"  # German context
    r")"
)

# Directories excluded from scanning (historical/archived content).
_EXCLUDED_DIRS: tuple[str, ...] = (
    "superpowers/plans",  # Historical session plans
    "archive",  # Archived docs
)

# Superseded/deprecated ADR status markers.
_SUPERSEDED_MARKER_RE = re.compile(
    r"\*\*Status:\*\*\s*\S+\s+(?:Superseded|Deprecated)",
)


def _is_excluded_dir(rel_to_docs: Path) -> bool:
    """Check if a path (relative to docs/) falls under an excluded directory."""
    parts = rel_to_docs.parts
    for excluded in _EXCLUDED_DIRS:
        excluded_parts = tuple(excluded.split("/"))
        if parts[: len(excluded_parts)] == excluded_parts:
            return True
    return False


def _is_superseded_adr(filepath: Path) -> bool:
    """Check if an ADR file has a Superseded or Deprecated status."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except OSError:
        return False
    header = "\n".join(content.splitlines()[:20])
    return bool(_SUPERSEDED_MARKER_RE.search(header))


def _scan_file(
    filepath: Path,
    real_names: frozenset[str],
) -> list[DocDriftFinding]:
    """Scan a single file for fake/invalid subagent name references.

    Returns a list of findings (deduplicated per invalid name per file).
    """
    try:
        content = filepath.read_text(encoding="utf-8")
    except OSError:
        return []

    findings: list[DocDriftFinding] = []
    seen_invalid: set[str] = set()

    # Combined allowed set: real specialists + built-in OpenCode subagents.
    allowed_types = real_names | _BUILTIN_SUBAGENT_TYPES

    for line_num, line in enumerate(content.splitlines(), start=1):
        # Skip negation-context lines (explanatory text).
        if _NEGATION_RE.search(line):
            continue
        # Skip package-install context lines.
        if _PACKAGE_CONTEXT_RE.search(line):
            continue

        # Check subagent_type="..." references.
        for m in _SUBAGENT_TYPE_RE.finditer(line):
            name = m.group(1)
            # Skip placeholders (``...``, ``<name>``, ``{var}``).
            if _PLACEHOLDER_RE.match(name):
                continue
            if name not in allowed_types and name not in seen_invalid:
                seen_invalid.add(name)
                findings.append(
                    DocDriftFinding(
                        severity="critical",
                        file=safe_relative(filepath),
                        message=(
                            f"[AGENT-NAME-DRIFT] Line {line_num}: "
                            f'subagent_type="{name}" is not a real subagent '
                            f"definition. Real names: "
                            f"{', '.join(sorted(real_names))}. "
                            f"Fix the reference to match a real subagent "
                            f"definition in {_AGENTS_DIR_DISPLAY}."
                        ),
                    )
                )

        # Check backtick-wrapped `narrare-<word>` references.
        # Only flag known fake agent names (targeted, avoids false positives
        # on legitimate identifiers like ``narrare-api`` service names).
        for m in _BACKTICK_NARRARE_RE.finditer(line):
            name = m.group(1)
            if name in _KNOWN_FAKE_AGENT_NAMES and name not in seen_invalid:
                seen_invalid.add(name)
                findings.append(
                    DocDriftFinding(
                        severity="critical",
                        file=safe_relative(filepath),
                        message=(
                            f"[AGENT-NAME-DRIFT] Line {line_num}: references "
                            f"`{name}`, which is a kebab-case identifier. "
                            f"Real subagent names are PascalCase (e.g. "
                            f"NarrareBuilder) defined in "
                            f"{_AGENTS_DIR_DISPLAY}. "
                            f"Replace with the correct subagent_type value."
                        ),
                    )
                )

    return findings


# ── Public API ──────────────────────────────────────────────────


def check_agent_name_drift(
    docs_dir: Path | None = None,
) -> list[DocDriftFinding]:
    """Run the agent-name doc-drift check.

    Scans ``AGENTS.md`` and all ``*.md`` files under *docs_dir*
    (default: ``docs/``) for references to subagent names that do not
    match the real definitions in ``.opencode/agents/*.md``.

    Returns an empty list when every scanned file is clean. Critical
    findings fail CI via ``check_doc_drift.py``.
    """
    effective_docs = docs_dir or _DOCS_DIR
    real_names = get_real_subagent_names()

    if not real_names:
        return [
            DocDriftFinding(
                severity="warning",
                file=str(_AGENTS_DIR),
                message=(
                    "[AGENT-NAME-DRIFT] Could not extract real subagent "
                    f"names from {_AGENTS_DIR_DISPLAY} "
                    "— skipping check."
                ),
            )
        ]

    findings: list[DocDriftFinding] = []
    scan_targets: list[Path] = []

    # Always scan AGENTS.md (root-level, outside docs/).
    if _AGENTS_MD.is_file():
        scan_targets.append(_AGENTS_MD)

    # Scan all *.md under docs/.
    for md_file in sorted(effective_docs.rglob("*.md")):
        rel_to_docs = md_file.relative_to(effective_docs)
        if _is_excluded_dir(rel_to_docs):
            continue
        if _is_superseded_adr(md_file):
            continue
        scan_targets.append(md_file)

    for target in scan_targets:
        findings.extend(_scan_file(target, real_names))

    return findings
