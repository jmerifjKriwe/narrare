"""The canonical screenshot manifest and its overview renderer.

``SHOTS`` is the manifest for every master frame in ``assets/screenshots/``: its
stable name, title, caption, group and theme. The capture script is intended to
write the PNGs from this list, and ``docs/screenshots/README.md`` is intended to
be ``render_index``'s output, so the collection and its index cannot drift apart.

``README_SHOTS`` is the curated subset the README is intended to embed, in
display order. It is derived from the ``readme`` flag rather than maintained as
a second list.
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
        "01-workspace-continuation",
        "The workspace with a continuation",
        "A chapter open in the editor and a grey continuation waiting at the caret",
        "Writing",
        "light",
    ),
    Shot(
        "02-chat-sources",
        "Chat with its sources",
        "A question, a streamed answer and the two note passages it was drawn from",
        "Assistant",
        "light",
    ),
    Shot(
        "03-knowledge-dock",
        "The knowledge dock",
        "The whole-book check, a consistency finding and the novel's entities",
        "Knowledge",
        "light",
    ),
    Shot(
        "04-knowledge-search",
        "Knowledge search",
        "Two uploaded notes and a search whose results quote the matching passages",
        "Knowledge",
        "light",
    ),
    Shot(
        "05-shelf",
        "The bookshelf",
        "Three novels with the last one offered for resuming",
        "Writing",
        "light",
    ),
    Shot(
        "06-shelf-dark",
        "The bookshelf in dark",
        "The same shelf in the reader's stored dark theme",
        "Writing",
        "dark",
    ),
    Shot(
        "07-workspace-dark",
        "The workspace in dark",
        "The prose surface in the reader's stored dark theme",
        "Writing",
        "dark",
    ),
    Shot(
        "08-design",
        "The design gallery",
        "Every primitive, token pair and dock specimen on one page",
        "Settings",
        "light",
    ),
    Shot(
        "09-design-dark",
        "The design gallery in dark",
        "The same gallery in the reader's stored dark theme",
        "Settings",
        "dark",
    ),
    Shot(
        "10-graph",
        "The lore graph",
        "The novel's entities as named nodes with the selected node's glance",
        "Knowledge",
        "light",
    ),
    Shot(
        "11-graph-dark",
        "The lore graph in dark",
        "The same canvas in the reader's stored dark theme",
        "Knowledge",
        "dark",
    ),
    Shot(
        "12-timeline",
        "The timeline",
        "The novel's events in the writer's order, dated and unordered alike",
        "Planning",
        "light",
    ),
    Shot(
        "13-timeline-dark",
        "The timeline in dark",
        "The same rows and garnish in the reader's stored dark theme",
        "Planning",
        "dark",
    ),
    Shot(
        "14-storyboard",
        "The storyboard",
        "Chapters as cards in their structure's columns, each with its sync badge",
        "Planning",
        "light",
    ),
    Shot(
        "15-storyboard-dark",
        "The storyboard in dark",
        "The same columns, cards and badges in the reader's stored dark theme",
        "Planning",
        "dark",
    ),
    Shot(
        "16-structure",
        "The structure view",
        "The story as one proportion bar, a band per stage with its chapters",
        "Planning",
        "light",
    ),
    Shot(
        "17-structure-dark",
        "The structure view in dark",
        "The same bands and marks in the reader's stored dark theme",
        "Planning",
        "dark",
    ),
    Shot(
        "18-shortcuts",
        "Keyboard shortcuts",
        "Every binding grouped by scope, each with the platform's own keycap",
        "Settings",
        "light",
    ),
    Shot(
        "19-shortcuts-dark",
        "Keyboard shortcuts in dark",
        "The same rows and keycaps in the reader's stored dark theme",
        "Settings",
        "dark",
    ),
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
        "The prose alone, with every dock and chrome out of the way",
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
        "The first-run door: name the novel, choose a demo or start empty",
        "Settings",
        "light",
    ),
    Shot(
        "25-dossiers",
        "Dossiers",
        "The novel's knowledge organized as dossiers",
        "Knowledge",
        "light",
        readme=True,
    ),
    Shot(
        "26-sources",
        "Sources",
        "The documents the novel's knowledge was drawn from",
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
        "Providers, models, assignments and the rest of the configuration in one place",
        "Settings",
        "light",
        readme=True,
    ),
    Shot(
        "29-ai-rules",
        "AI rules",
        "The house rules every AI task follows",
        "Settings",
        "light",
    ),
    Shot(
        "30-prompts",
        "Prompts",
        "The prompt library's cards with preview and live test",
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
