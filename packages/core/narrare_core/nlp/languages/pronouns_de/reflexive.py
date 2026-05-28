"""
German reflexive pronouns.

Accusative and dative forms for each person/number (mich/mir, dich/dir,
sich, uns, euch).
"""

from __future__ import annotations

REFLEXIVE: dict[str, dict[str, str | int | bool | None]] = {
    "mich_refl": {
        "person": 1,
        "number": "singular",
        "case": "accusative",
        "gender": None,
        "reflexive": True,
        "possessive": False,
        "type": "reflexive",
    },
    "mir_refl": {
        "person": 1,
        "number": "singular",
        "case": "dative",
        "gender": None,
        "reflexive": True,
        "possessive": False,
        "type": "reflexive",
    },
    "dich_refl": {
        "person": 2,
        "number": "singular",
        "case": "accusative",
        "gender": None,
        "reflexive": True,
        "possessive": False,
        "type": "reflexive",
    },
    "dir_refl": {
        "person": 2,
        "number": "singular",
        "case": "dative",
        "gender": None,
        "reflexive": True,
        "possessive": False,
        "type": "reflexive",
    },
    "sich": {
        "person": 3,
        "number": "singular",
        "case": "accusative",
        "gender": None,
        "reflexive": True,
        "possessive": False,
        "type": "reflexive",
    },
    "sich_dat": {
        "person": 3,
        "number": "singular",
        "case": "dative",
        "gender": None,
        "reflexive": True,
        "possessive": False,
        "type": "reflexive",
    },
    "uns_refl": {
        "person": 1,
        "number": "plural",
        "case": "accusative",
        "gender": None,
        "reflexive": True,
        "possessive": False,
        "type": "reflexive",
    },
    "uns_refl_dat": {
        "person": 1,
        "number": "plural",
        "case": "dative",
        "gender": None,
        "reflexive": True,
        "possessive": False,
        "type": "reflexive",
    },
    "euch_refl": {
        "person": 2,
        "number": "plural",
        "case": "accusative",
        "gender": None,
        "reflexive": True,
        "possessive": False,
        "type": "reflexive",
    },
    "euch_refl_dat": {
        "person": 2,
        "number": "plural",
        "case": "dative",
        "gender": None,
        "reflexive": True,
        "possessive": False,
        "type": "reflexive",
    },
}
