"""The interchange engine's format half: the archive, its tree, in and out.

D9 (WP3 design): two capabilities need this (setup's demo load, writing's
HTTP surface), so it lives in the kernel. Tasks 3-5 import from here:

    ArchiveError, NovelArchive, ChapterFile, EntityFile, RelationEdge,
    parse_archive, serialize_archive          (this package, via format.py)
    ArchiveTree, open_directory, open_zip, write_directory, zip_bytes  (tree.py)
"""

from app.kernel.interchange.format import (
    METADATA_NAME,
    ArchiveError,
    ChapterFile,
    EntityFile,
    NovelArchive,
    RelationEdge,
    parse_archive,
    serialize_archive,
)
from app.kernel.interchange.tree import (
    ArchiveTree,
    open_directory,
    open_zip,
    write_directory,
    zip_bytes,
)

__all__ = [
    "METADATA_NAME",
    "ArchiveError",
    "ArchiveTree",
    "ChapterFile",
    "EntityFile",
    "NovelArchive",
    "RelationEdge",
    "open_directory",
    "open_zip",
    "parse_archive",
    "serialize_archive",
    "write_directory",
    "zip_bytes",
]
