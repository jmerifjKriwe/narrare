"""The canonical screenshot manifest and its overview renderer.

``SHOTS`` is the manifest for every master frame in ``assets/screenshots/``: its
stable name, title, caption, group and theme. The capture script writes the
PNGs from this list, and ``docs/screenshots/README.md`` is ``render_index``'s
output, so the collection and its index cannot drift apart.

``README_SHOTS`` is the curated subset the README embeds, in display order. It
is derived from the ``readme`` flag rather than maintained as a second list, so
the page and the collection cannot disagree about which frames it shows.

The ``01``-``19`` generation was audited against the live product before this
manifest became authoritative. Names whose surface and pixels survived kept
their place under a new number when the pixels changed; the dead surfaces
(the retired chat dock, the global knowledge page, the design gallery, the
structure view and the shortcuts page) are gone, and nothing was overwritten
under an old URL.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

_GROUP_ORDER: tuple[str, ...] = (
    "Writing",
    "Knowledge",
    "Planning",
    "Settings",
    "Assistant",
)
_NAME = re.compile(r"\d{2}-[a-z0-9-]+")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_MARKDOWN = re.compile(r"([\\`*_\[\]<>#])")
_LINK_ROOT = "../../assets/screenshots"
STAND_IN_DISCLOSURE = (
    "Some frames use deterministic stand-ins at the model boundary: the dossiers frame "
    "shows extraction output from the fake extraction provider, the knowledge-dock frame "
    "shows a finding from the fake consistency provider, the AI-rules frame (29) shows "
    "the fake provider card, both interview frames (33 and 34) show stand-in replies, and "
    "the continuation frame uses the chat stand-in."
)
README_STAND_IN_DISCLOSURE = (
    "Some frames use deterministic stand-ins at the model boundary: the dossiers frame "
    "shows extraction output from the fake extraction provider, the knowledge-dock frame "
    "shows a finding from the fake consistency provider, the AI-rules frame shows the "
    "fake provider card, both interview frames show stand-in replies, and the continuation "
    "frame uses the chat stand-in."
)


def _escape_markdown(text: str) -> str:
    """Keep authored Markdown punctuation literal in a heading or link label."""
    return _MARKDOWN.sub(lambda match: f"\\{match.group(0)}", text)


@dataclass(frozen=True)
class Shot:
    """One master frame and the words that describe it."""

    name: str
    title: str
    caption: str
    group: str
    theme: Literal["light", "dark"]
    readme: bool = False

    @property
    def filename(self) -> str:
        """The master file's name in ``assets/screenshots/``."""
        return f"{self.name}.png"


SHOTS: tuple[Shot, ...] = (
    Shot(
        "20-workspace-rebuilt",
        "The rebuilt writing workspace",
        "The scene-centric workspace with the explorer, editor and docks together",
        "Writing",
        "light",
        readme=True,
    ),
    Shot(
        "21-workspace-rebuilt-dark",
        "The rebuilt writing workspace in dark",
        "The same workspace in the reader's stored dark theme",
        "Writing",
        "dark",
        readme=True,
    ),
    Shot(
        "22-zen",
        "Zen mode",
        "The prose alone, with the explorer and docks out of the way",
        "Writing",
        "light",
        readme=True,
    ),
    Shot(
        "23-zen-dark",
        "Zen mode in dark",
        "The same uninterrupted prose in the reader's stored dark theme",
        "Writing",
        "dark",
    ),
    Shot(
        "24-welcome-setup",
        "The welcome and setup screen",
        "The first-run welcome: start a new work or choose a demo",
        "Settings",
        "light",
    ),
    Shot(
        "25-dossiers",
        "Dossiers",
        "The novel's knowledge organized as dossiers with a character's dossier open",
        "Knowledge",
        "light",
        readme=True,
    ),
    Shot(
        "26-sources",
        "Sources",
        "The empty sources archive and its upload door",
        "Knowledge",
        "light",
    ),
    Shot(
        "27-causality",
        "Causality",
        "The planned chain of cause and effect behind the story",
        "Planning",
        "light",
        readme=True,
    ),
    Shot(
        "28-settings-hub",
        "The settings hub",
        "Language, appearance and the author profile",
        "Settings",
        "light",
        readme=True,
    ),
    Shot(
        "29-ai-rules",
        "AI rules",
        "The configured provider card and the create-provider form",
        "Settings",
        "light",
    ),
    Shot(
        "30-prompts",
        "Prompts",
        "The prompt catalog beside the selected prompt's editor and template",
        "Settings",
        "light",
        readme=True,
    ),
    Shot(
        "31-entity-create",
        "Create an entity",
        "The manual entity dialog beside the lore graph",
        "Assistant",
        "light",
    ),
    Shot(
        "32-entity-create-dark",
        "Create an entity in dark",
        "The same dialog in the reader's stored dark theme",
        "Assistant",
        "dark",
    ),
    Shot(
        "33-entity-interview",
        "The entity interview",
        "An answered interview and the proposal it built",
        "Assistant",
        "light",
        readme=True,
    ),
    Shot(
        "34-entity-interview-dark",
        "The entity interview in dark",
        "The same conversation and proposal in the reader's stored dark theme",
        "Assistant",
        "dark",
    ),
    Shot(
        "35-workspace-continuation",
        "The workspace with a continuation",
        "A chapter open in the scene editor and a grey continuation offered below the "
        "prose, with its Tab accept pill",
        "Writing",
        "light",
    ),
    Shot(
        "36-knowledge-dock",
        "The knowledge dock",
        "A consistency finding and the novel's entities beside the prose",
        "Knowledge",
        "light",
    ),
    Shot(
        "37-shelf",
        "The bookshelf",
        "Three novels with the latest-edited one offered for resuming",
        "Writing",
        "light",
    ),
    Shot(
        "38-shelf-dark",
        "The bookshelf in dark",
        "The same shelf in the reader's stored dark theme",
        "Writing",
        "dark",
    ),
    Shot(
        "39-graph",
        "The lore graph",
        "The novel's canon as three named entities and two relations, with the "
        "selected node's dossier",
        "Knowledge",
        "light",
    ),
    Shot(
        "40-graph-dark",
        "The lore graph in dark",
        "The same canon, canvas and dossier in the reader's stored dark theme",
        "Knowledge",
        "dark",
    ),
    Shot(
        "41-timeline",
        "The timeline",
        "The placed events in chronological order, with unordered drafts at the end",
        "Planning",
        "light",
    ),
    Shot(
        "42-timeline-dark",
        "The timeline in dark",
        "The same events and labels in the reader's stored dark theme",
        "Planning",
        "dark",
    ),
    Shot(
        "43-storyboard",
        "The storyboard",
        "Chapters as cards in their structure's columns with their scene counts and statuses",
        "Planning",
        "light",
    ),
    Shot(
        "44-storyboard-dark",
        "The storyboard in dark",
        "The same columns, cards and statuses in the reader's stored dark theme",
        "Planning",
        "dark",
    ),
)

README_SHOTS: tuple[Shot, ...] = tuple(shot for shot in SHOTS if shot.readme)


def validate_shots(shots: Sequence[Shot]) -> None:
    """Reject a manifest the capture and index cannot honour."""
    seen: set[str] = set()
    for shot in shots:
        if not _NAME.fullmatch(shot.name):
            raise ValueError(
                f"shot name {shot.name!r} must match two digits, a dash and lowercase words"
            )
        if shot.name in seen:
            raise ValueError(f"duplicate shot name {shot.name!r}")
        seen.add(shot.name)
        if shot.theme not in {"light", "dark"}:
            raise ValueError(f"shot {shot.name!r} has unknown theme {shot.theme!r}")
        if shot.group not in _GROUP_ORDER:
            raise ValueError(f"shot {shot.name!r} has unknown group {shot.group!r}")
        if _CONTROL.search(shot.title) or _CONTROL.search(shot.caption):
            raise ValueError(f"shot {shot.name!r} text must not contain control characters")
        if not shot.title.strip() or not shot.caption.strip():
            raise ValueError(f"shot {shot.name!r} needs a title and a caption")


def render_index(shots: Sequence[Shot]) -> str:
    """Render the browsable collection index for ``docs/screenshots/README.md``."""
    validate_shots(shots)
    lines = [
        "# Screenshot collection",
        "",
        "These frames are captured from the running Narrare application. Dark frames "
        "show the reader's stored theme, not the operating system's.",
        "",
        STAND_IN_DISCLOSURE,
        "",
    ]
    for group in _GROUP_ORDER:
        members = [shot for shot in shots if shot.group == group]
        if not members:
            continue
        lines.extend((f"## {group}", ""))
        for shot in members:
            title = _escape_markdown(shot.title)
            caption = _escape_markdown(shot.caption)
            lines.extend(
                (
                    f"### {title}",
                    "",
                    f"![{caption}]({_LINK_ROOT}/{shot.filename})",
                    "",
                    caption,
                    "",
                )
            )
    return "\n".join(lines).rstrip() + "\n"
