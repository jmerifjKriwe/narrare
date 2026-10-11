"""Planning domain — storyboard, outlines, timeline management.

Public surface note (PLAN-001 T15, RULE-05): ``iter_scene_texts`` is the
ONE shared scene text scan (spec §7) — cross-domain consumers (KB
lifecycle, consistency ref-index) import it from here, never from the
private ``_helpers`` module.
"""

from narrare.planning._helpers import iter_scene_texts
from narrare.planning.models import ChapterOutline, TimelineEvent

__all__ = ["ChapterOutline", "TimelineEvent", "iter_scene_texts"]
