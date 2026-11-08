"""The provider presets: one click from an empty list to a working endpoint.

The table is data, never a resolution path: nothing at call time reads it,
and every field it fills stays editable in the form. The pins here hold the
table to the catalog it fills from — every preset's vendor must be one the
catalog carries, or its model picker would offer a list that is always
empty — and to the ids the endpoint, the forms and the E2E name.
"""

from app.kernel.llm.catalog import load_catalog, vendor_models
from app.kernel.llm.presets import PRESETS, preset


def test_the_presets_name_only_known_vendors() -> None:
    """Verify every preset's vendor is one the catalog carries, ids in order.

    The order is the form's offering order: the big names first, the two
    OpenCode inferences together, the two Z.ai endpoints last — the Coding
    Plan one at the very end, because its note needs the reading eye.
    """
    known = {entry.split("/")[0] for entry in load_catalog()}
    assert {entry.vendor for entry in PRESETS} <= known
    assert [entry.id for entry in PRESETS] == [
        "openai",
        "anthropic",
        "xai",
        "google",
        "openrouter",
        "opencode",
        "opencode-go",
        "zai",
        "zai-coding-plan",
    ]


def test_an_unknown_vendor_has_no_models() -> None:
    """Verify a vendor the catalog does not carry fills no picker."""
    assert vendor_models("nope") == ()


def test_a_preset_is_found_by_its_id_and_none_otherwise() -> None:
    """Verify the lookup the create flow and the endpoint ride on."""
    assert preset("zai-coding-plan") is PRESETS[-1]
    assert preset("nobody") is None


def test_the_table_is_well_formed() -> None:
    """Verify unique ids, https endpoints, and a note only where it is owed.

    A preset is a suggestion the form fills verbatim, so an http endpoint
    would sail the stored key through the gate as cleartext the moment the
    user accepted the fill — the table must not carry one. The note key is
    the one prose string in the table; every other visible word is a vendor
    proper noun.
    """
    ids = [entry.id for entry in PRESETS]
    assert len(ids) == len(set(ids))
    for entry in PRESETS:
        assert entry.base_url.startswith("https://")
        if entry.models_url is not None:
            assert entry.models_url.startswith("https://")
        assert entry.note_key is None or entry.id == "zai-coding-plan"
