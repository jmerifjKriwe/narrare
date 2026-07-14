"""Per-invocation render controls for KBContextEnvelope renderers.

Extracted as its own module (RULE-04, RULE-06) so the
:class:`~narrare_core.context._kb_envelope.RenderedKBContext` envelope types
stay focused on accounting while render *controls* live separately.

The default (``annotate_provenance=False``) preserves current behaviour
byte-for-byte — provenance annotation is strictly opt-in.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RenderOptions:
    """Per-invocation render controls for KBContextEnvelope renderers.

    Attributes:
        annotate_provenance: When ``True``, the renderer appends a
            provenance bracket to entries that are uncertain or unverified
            (low confidence, pending review, stale freshness), and moves
            the rendered :class:`ProvenanceField` literals from
            ``omitted_fields`` to ``preserved_fields`` (RULE-22). When
            ``False`` (default) the renderer output is byte-for-byte
            identical to the pre-annotation behaviour.
    """

    annotate_provenance: bool = False
