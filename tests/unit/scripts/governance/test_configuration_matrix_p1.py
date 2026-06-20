"""CR-08 P1 Configuration Adoption Matrix evidence tests."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from governance.configuration_matrix import load_matrix, parse_matrix  # noqa: E402

_MATRIX_PATH = (
    _PROJECT_ROOT / "docs" / "architecture" / "governance" / "configuration-adoption-matrix.yaml"
)
_P1_SETTING_IDS = {
    "token_profile_vocabulary",
    "token_settings_ui_api_parity",
    "model_limit_calibration",
    "model_suitability_policy",
}


def _evidence_file(evidence: str) -> Path:
    return _PROJECT_ROOT / evidence.split("::", 1)[0]


def test_cr08_p1_entries_are_adopted_with_concrete_evidence_paths() -> None:
    """P1 entries may move to adopted only with evidence files on disk."""

    data = load_matrix(_MATRIX_PATH)
    entries, _ = parse_matrix(data)
    by_id = {entry.setting_id: entry for entry in entries}

    for setting_id in sorted(_P1_SETTING_IDS):
        entry = by_id[setting_id]
        assert entry.phase == "P1"
        assert entry.lifecycle == "adopted"
        assert entry.enforcement_evidence, f"{setting_id} needs enforcement evidence"
        for evidence in entry.enforcement_evidence:
            path = _evidence_file(evidence)
            assert path.exists(), f"{setting_id} evidence path does not exist: {path}"
        assert entry.cross_layer_evidence, f"{setting_id} needs cross-layer evidence"
