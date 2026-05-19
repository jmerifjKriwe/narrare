"""Test that all contract modules import cleanly and their Protocol definitions are valid."""

from __future__ import annotations


class TestContractsImportCleanly:
    """Contract files define Protocols — they must be importable and valid at runtime."""

    def test_auth_contracts_import(self) -> None:
        from narrare.auth.contracts import AuthRepositoryProtocol, AuthServiceProtocol

        assert hasattr(AuthRepositoryProtocol, "get_by_email")
        assert hasattr(AuthServiceProtocol, "register")

    def test_novels_contracts_import(self) -> None:
        from narrare.novels.contracts import NovelRepositoryProtocol, NovelServiceProtocol

        assert hasattr(NovelRepositoryProtocol, "get_by_id")
        assert hasattr(NovelServiceProtocol, "create")

    def test_chapters_contracts_import(self) -> None:
        from narrare.chapters.contracts import ChapterRepositoryProtocol, ChapterServiceProtocol

        assert hasattr(ChapterRepositoryProtocol, "get_by_id")
        assert hasattr(ChapterServiceProtocol, "create")

    def test_volumes_contracts_import(self) -> None:
        from narrare.volumes.contracts import VolumeRepositoryProtocol

        assert hasattr(VolumeRepositoryProtocol, "get_by_id")

    def test_setup_contracts_import(self) -> None:
        from narrare.setup.contracts import (
            DemoLoaderProtocol,
            ProviderServiceProtocol,
            SetupServiceProtocol,
        )

        assert hasattr(SetupServiceProtocol, "complete")
        assert hasattr(ProviderServiceProtocol, "list_models")
        assert hasattr(DemoLoaderProtocol, "load")

    def test_kb_contracts_import(self) -> None:
        from narrare.kb.contracts import (
            KBRepositoryProtocol,
            KBServiceProtocol,
            RelationshipRepositoryProtocol,
            RelationshipServiceProtocol,
        )

        assert hasattr(KBRepositoryProtocol, "create")
        assert hasattr(KBServiceProtocol, "create")
        assert hasattr(RelationshipRepositoryProtocol, "create")
        assert hasattr(RelationshipServiceProtocol, "create")
