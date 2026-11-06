"""The Unraid template is a shipped artefact, so it is pinned like one.

Unraid's Community Applications templates are XML forms, and nothing checks them
at runtime: a renamed variable or an unmasked secret is discovered by a user
whose container cannot reach its database, or by whoever opens the template and
reads the password field. The names below are written out on purpose — they are
the published contract (`docs/user/install.md`), not an import of the code that
happens to agree with itself.
"""

from pathlib import Path
from xml.etree import ElementTree

TEMPLATE = Path(__file__).resolve().parents[3] / "deploy/unraid/narrare.xml"

VARIABLES = frozenset(
    {
        "NARRE_DB_HOST",
        "NARRE_DB_NAME",
        "NARRE_DB_USER",
        "NARRE_DB_PASSWORD",
        "NARRE_DB_PORT",
        "NARRE_DB_SSLMODE",
        "NARRE_SECRET_KEY",
    }
)


def _root() -> ElementTree.Element:
    # The template is a file in this repository, not untrusted input.
    return ElementTree.parse(TEMPLATE).getroot()  # noqa: S314


def _configs() -> dict[str, ElementTree.Element]:
    return {element.get("Target", ""): element for element in _root().iter("Config")}


def test_the_template_asks_for_every_variable_the_image_reads() -> None:
    missing = sorted(VARIABLES - set(_configs()))
    assert missing == [], f"the template does not ask for {missing}"


def test_the_database_port_defaults_to_the_image_default() -> None:
    assert _configs()["NARRE_DB_PORT"].get("Default") == "5432"


def test_secrets_are_masked() -> None:
    """The secret key and the database password are the two that must not show."""
    configs = _configs()
    for name in ("NARRE_SECRET_KEY", "NARRE_DB_PASSWORD"):
        assert configs[name].get("Mask") == "true", f"{name} is visible in the template"


def test_the_secret_key_is_required_and_explains_itself() -> None:
    """Without it the app refuses to store provider keys, so the field says how to make one."""
    secret = _configs()["NARRE_SECRET_KEY"]
    assert secret.get("Required") == "true"
    assert "Fernet.generate_key" in (secret.text or "") + (secret.get("Description") or "")


def test_backups_are_a_writable_mounted_path() -> None:
    backups = _configs()["/backups"]
    assert backups.get("Mode") == "rw"
    assert backups.get("Default", "").startswith("/mnt/user/")


def test_the_container_is_the_published_image_and_not_privileged() -> None:
    root = _root()
    assert root.findtext("Repository") == "ghcr.io/jmerifjKriwe/narrare:latest"
    assert root.findtext("Privileged") == "false"


def test_the_overview_names_the_prerequisite() -> None:
    """The one sentence read before installing: the database is not included."""
    overview = _root().findtext("Overview") or ""
    assert "CREATE EXTENSION vector" in overview
    assert "no database" in overview
