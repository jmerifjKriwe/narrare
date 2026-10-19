"""N11: roster-gated speaker attribution.

The action-beat heuristic attributes quotes to the last capitalized token
of the preceding clause — sentence-initial prose words ("In order to…")
become MEDIUM-confidence "speakers". The roster gate demotes any speaker
not in the novel's KB character roster to None (ADR-055 Decision 3: the
agent resolves unattributed quotes inline). Empty roster → no-op (no SSOT
to gate against — KB-less novels keep the parser's hint behavior).
"""

from __future__ import annotations

from narrare_core.analysis.dialogue_parser import (
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    DialogueParser,
    filter_speaker_names,
    restrict_speakers_to_roster,
)

# Deterministic N11 repro: "Elara" is the only roster character; the
# sentence-initial words before quotes attract garbage attributions.
_N11_TEXT = (
    'Elara pressed her palm against the gate. "Open it," she said.\n\n'
    'In order to be ready, she counted the bells. "Two strikes. The gate, then."\n\n'
    'About an hour later, the guard sighed. "Nobody crosses after dark."'
)


class TestRestrictSpeakersToRoster:
    def test_garbage_action_beat_names_are_demoted(self) -> None:
        utterances = DialogueParser().parse(_N11_TEXT)
        speakers = {u.speaker for u in utterances if u.speaker}
        # The audit's garbage class is present pre-fix (In/Order/About…).
        assert speakers - {"Elara"}, f"repro stale: got {speakers}"

        gated = restrict_speakers_to_roster(utterances, {"Elara"})

        assert {u.speaker for u in gated if u.speaker} == {"Elara"}
        demoted = [u for u in gated if u.speaker is None]
        assert demoted, "garbage attributions must survive as None (agent handoff)"
        assert all(u.confidence == CONFIDENCE_LOW for u in demoted)
        # Demoted utterances keep their MEDIUM attribution provenance lost —
        # the confidence must be LOW (agent handoff), not the original band.
        assert CONFIDENCE_LOW < CONFIDENCE_MEDIUM

    def test_roster_names_pass_through_at_original_confidence(self) -> None:
        utterances = DialogueParser().parse(_N11_TEXT)
        gated = restrict_speakers_to_roster(utterances, {"Elara"})
        kept = [u for u in gated if u.speaker == "Elara"]
        assert kept, "the roster name must survive the gate"
        assert all(u.confidence == CONFIDENCE_MEDIUM for u in kept)

    def test_matching_is_case_insensitive(self) -> None:
        utterances = DialogueParser().parse('Elara said, "We leave at dawn."')
        gated = restrict_speakers_to_roster(utterances, {"elara"})
        # Case-insensitive match keeps the parser's original name form.
        assert gated[0].speaker == "Elara"

    def test_empty_roster_is_a_no_op(self) -> None:
        utterances = DialogueParser().parse(_N11_TEXT)
        gated = restrict_speakers_to_roster(utterances, set())
        assert [(u.speaker, u.confidence) for u in gated] == [
            (u.speaker, u.confidence) for u in utterances
        ]

    def test_inputs_are_not_mutated(self) -> None:
        utterances = DialogueParser().parse(_N11_TEXT)
        before = [(u.speaker, u.confidence) for u in utterances]
        restrict_speakers_to_roster(utterances, {"Elara"})
        assert [(u.speaker, u.confidence) for u in utterances] == before


class TestFilterSpeakerNames:
    def test_name_sets_are_filtered_case_insensitively(self) -> None:
        assert filter_speaker_names({"Elara", "Order", "About"}, {"elara"}) == {"Elara"}

    def test_empty_roster_keeps_names(self) -> None:
        assert filter_speaker_names({"Elara", "Order"}, set()) == {"Elara", "Order"}
