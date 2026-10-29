"""Writing logic. Routers delegate here; this module knows the unit of work."""

import zlib
from collections.abc import Sequence  # noqa: TC003
from pathlib import Path
from typing import Literal
from uuid import UUID  # noqa: TC003
from zipfile import BadZipFile

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.capabilities.writing.prompts import continuation_prompt
from app.capabilities.writing.repository import ChapterRepository, EntityRepository, NovelRepository
from app.capabilities.writing.schemas import ChapterUpdate, ExportDone
from app.kernel.auth import SetupRequiredError
from app.kernel.context import allocate
from app.kernel.contracts.models import Chapter, Entity, Novel, User
from app.kernel.interchange import (
    ArchiveError,
    ArchiveTree,
    open_directory,
    open_zip,
    write_directory,
    zip_bytes,
)
from app.kernel.interchange import engine as interchange_engine


class NotFoundError(Exception):
    """The row does not exist or belongs to another user; the two are one answer."""


class TargetNotEmptyError(Exception):
    """The export target exists and is non-empty; `path` names it."""

    def __init__(self, path: str) -> None:
        super().__init__(f"target not empty: {path}")
        self.path = path


class ArchiveTooLargeError(Exception):
    """The archive is larger than MAX_ARCHIVE_BYTES."""


class ArchiveInvalidError(Exception):
    """The archive is unreadable or malformed; `file` names the offender."""

    def __init__(self, file: str, reason: str) -> None:
        super().__init__(f"{file}: {reason}")
        self.file = file
        self.reason = reason


class FieldRefusedError(ValueError):
    """The request breaks a field contract; `fields` names them.

    The settings gate's pattern: the router turns each field into a 422
    loc entry, so the client learns exactly which input was refused.
    """

    def __init__(self, fields: tuple[str, ...], message: str) -> None:
        super().__init__(message)
        self.fields = fields


MAX_ARCHIVE_BYTES = 20_000_000
"""One archive, at most — read whole before it is parsed, so an unbounded
upload would hold the worker for no good novel (the knowledge cap's reason)."""

_ARCHIVE = "<archive>"
"""The whole archive, when no single file is at fault — the engine's own word."""


class WritingService:
    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.novels = NovelRepository(session, user_id)
        self.chapters = ChapterRepository(session, user_id)
        self.entities = EntityRepository(session, user_id)

    async def _require_user(self) -> None:
        """Writes belong to a user that setup created; without one there is
        nothing to own the row, and the foreign key would say so at the worst
        possible time. The guard says it in the response instead."""
        if await self.session.get(User, self.user_id) is None:
            raise SetupRequiredError

    async def create_novel(
        self, title: str, genre: str | None = None, blurb: str | None = None
    ) -> Novel:
        """Commit a novel with optional genre and blurb; return the created row.

        Raise SetupRequiredError if setup has not created the owning user.
        """
        await self._require_user()
        novel = await self.novels.create(title, genre=genre, blurb=blurb)
        await self.session.commit()
        return novel

    async def list_novels(self) -> Sequence[Novel]:
        return await self.novels.list()

    async def get_novel(self, novel_id: UUID) -> Novel:
        novel = await self.novels.get(novel_id)
        if novel is None:
            raise NotFoundError
        return novel

    async def create_chapter(self, novel_id: UUID, title: str) -> Chapter:
        await self._require_user()
        if await self.novels.get(novel_id) is None:
            raise NotFoundError
        chapter = await self.chapters.create(novel_id, title)
        await self.session.commit()
        return chapter

    async def list_chapters(self, novel_id: UUID) -> Sequence[Chapter]:
        if await self.novels.get(novel_id) is None:
            raise NotFoundError
        return await self.chapters.list_for_novel(novel_id)

    async def get_chapter(self, chapter_id: UUID) -> Chapter:
        chapter = await self.chapters.get(chapter_id)
        if chapter is None:
            raise NotFoundError
        return chapter

    async def continuation_prompt(
        self,
        chapter_id: UUID,
        *,
        context_window: int | None = None,
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        """The prompt for a continuation, or NotFoundError if the chapter is not ours.

        `allocate` runs before any gathering, so an impossible pair refuses
        before the database is touched. The three facts default to unset —
        the allocator's own not-yet-resolved fallbacks (D7); the router passes
        the resolved profile's values. Read-only: the streamed answer comes
        back to the editor, whose autosave writes it. The request that streams
        has no side effect of its own (D14).
        """
        budgets = allocate(
            context_window=context_window, max_output_tokens=max_output_tokens, model=model
        )
        chapter = await self.get_chapter(chapter_id)
        novel = await self.novels.get(chapter.novel_id)
        tail = chapter.body[-budgets.immediate_text :] if budgets.immediate_text > 0 else ""
        folded = tail.casefold()
        ranked: list[tuple[int, Entity]] = []
        for entity in await self.entities.list_for_novel(chapter.novel_id):
            positions = [
                index
                for index in (
                    folded.find(candidate.casefold())
                    for candidate in (entity.name, *entity.aliases)
                )
                if index >= 0
            ]
            if positions:
                ranked.append((min(positions), entity))
        ranked.sort(key=lambda pair: pair[0])
        chapters = await self.chapters.list_for_novel(chapter.novel_id)
        predecessors = [
            earlier for earlier in reversed(chapters) if earlier.position < chapter.position
        ]
        return continuation_prompt(
            budgets=budgets,
            novel_title=novel.title if novel else "",
            chapter_title=chapter.title,
            body=chapter.body,
            entities=[entity for _, entity in ranked],
            predecessors=predecessors,
            genre=novel.genre if novel else None,
            blurb=novel.blurb if novel else None,
        )

    async def update_chapter(self, chapter_id: UUID, changes: ChapterUpdate) -> Chapter:
        """Commit non-null edits and update the parent novel's timestamp.

        Return the chapter; raise NotFoundError if it is absent or another user's.
        """
        chapter = await self.get_chapter(chapter_id)
        chapter = await self.chapters.save(chapter, changes.model_dump(exclude_none=True))
        await self.session.commit()
        return chapter

    async def export_novel(
        self, novel_id: UUID, mode: Literal["path", "zip"], path: str | None
    ) -> ExportDone | tuple[str, bytes]:
        """Export one owned novel as a ZIP, or into a directory on disk.

        `zip` returns the title's slug and the deterministic ZIP bytes; `path`
        writes the archive to the target — refusing an existing non-empty
        target, the engine's answer to a thinner re-export — and returns the
        receipt. The kernel engine reads the rows and raises
        `NovelNotFoundError` for a missing or foreign novel, which becomes
        NotFoundError here; the transport's own failures are the caller's
        named fields.
        """
        try:
            slug, files = await interchange_engine.export_novel(
                self.session, self.user_id, novel_id
            )
        except interchange_engine.NovelNotFoundError:
            raise NotFoundError from None
        if mode == "zip":
            return slug, zip_bytes(files)
        if path is None or not path.strip():
            raise FieldRefusedError(("path",), "exporting to a path needs a target path")
        # A file is not a target: say so, rather than call it a non-empty
        # directory the caller could believe a retry's debris.
        if Path(path).is_file():
            raise FieldRefusedError(("path",), f"{path}: is a file")
        try:
            write_directory(Path(path), files)
        except ArchiveError:
            # write_directory's one refusal: the target exists and is non-empty.
            raise TargetNotEmptyError(path) from None
        except (OSError, ValueError) as error:
            # OSError is the filesystem's answer (an unreachable mount, a denied
            # permission); ValueError is `path` naming nothing (an empty file
            # name). Both are the request's fault and come back named.
            reason = error.strerror if isinstance(error, OSError) and error.strerror else str(error)
            raise FieldRefusedError(("path",), f"{path}: {reason}") from None
        tree = ArchiveTree(files)
        return ExportDone(
            # The directory actually written: a relative target is resolved so
            # the receipt names what the user can go and open.
            path=str(Path(path).resolve()),
            chapters=len(tree.chapter_names()),
            entities=len(tree.kb_names()),
        )

    async def import_novel(
        self, *, archive: bytes | None, path: str | None, novel_id: UUID | None
    ) -> interchange_engine.ImportReport:
        """Import one archive — upload bytes or a server-side directory — as a
        new novel when `novel_id` is None, merged into the owned novel otherwise.

        Exactly one source is required, named by field when the request breaks
        that; an oversized upload refuses before it is parsed; a malformed one
        refuses with the offending file named. A new-novel import writes rows
        a user must own, so without the setup-created user it refuses as
        `create_novel` does — before the engine's first insert turns the
        missing owner into a foreign-key error. The engine commits once at
        the end, so a refused or failing import writes nothing. A missing or
        foreign target novel is NotFoundError; the corpus-width guard
        (EmbeddingMismatchError) surfaces unchanged, the knowledge router's
        mapping applies to it.
        """
        if novel_id is None:
            await self._require_user()
        tree: ArchiveTree
        if path is not None and archive is not None:
            raise FieldRefusedError(("archive", "path"), "give archive or path, not both")
        if path is not None:
            source = Path(path)
            if not source.is_dir():
                raise FieldRefusedError(("path",), f"{path}: is not a directory")
            try:
                tree = open_directory(source)
            except OSError as error:
                raise FieldRefusedError(("path",), f"{path}: {error.strerror or error}") from None
            except ArchiveError as error:
                # The directory's files expand past the cap: refused by name,
                # before the read, like the ZIP transport's own refusal.
                raise ArchiveInvalidError(error.path, error.reason) from None
        elif archive is not None:
            if len(archive) > MAX_ARCHIVE_BYTES:
                raise ArchiveTooLargeError
            try:
                tree = open_zip(archive)
            except (BadZipFile, RuntimeError, NotImplementedError, zlib.error, EOFError) as error:
                # BadZipFile is the malformed container; RuntimeError is an
                # encrypted entry (password required), NotImplementedError an
                # unsupported compression method; zlib.error is a damaged or
                # truncated deflate stream and EOFError one that ends before
                # its marker. All are the archive's fault, never the server's.
                raise ArchiveInvalidError(_ARCHIVE, str(error)) from None
            except ArchiveError as error:
                # The entry claiming more than the uncompressed cap: named.
                raise ArchiveInvalidError(error.path, error.reason) from None
        else:
            raise FieldRefusedError(
                ("archive", "path"), "exactly one of archive or path is required"
            )
        try:
            return await interchange_engine.import_archive(
                self.session, self.user_id, tree, novel_id
            )
        except interchange_engine.NovelNotFoundError:
            raise NotFoundError from None
        except ArchiveError as error:
            raise ArchiveInvalidError(error.path, error.reason) from None
