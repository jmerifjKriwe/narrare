"""Atheris target for the interchange parser: one Markdown file, arbitrary bytes.

Run with a bounded budget: `just fuzz 60` (seconds). The target takes two
corpus directories from libFuzzer's positional arguments — the first is
written to, the second read-only — so `fuzz/corpus/` keeps the hand-written
seeds and `fuzz/workdir/` collects what the run grows. Crash reproducers land
in `fuzz/`, all three gitignored but for the seeds.

The upload path hands the parser an `ArchiveTree` built from untrusted bytes,
and the hand-written reader is the Markdown one: YAML frontmatter, the strict
field checks, slug assignment, the datetime and UUID readers. The target puts
the fuzzer's bytes at both Markdown kinds at once — one chapter file and one
entity file — so a single input reaches each reader's own rules, while
`metadata.json` stays fixed and valid so the parse always gets that far.

Both contracts come from `format.py`'s own docstring:

- a malformed file is refused as `ArchiveError` and nothing else; any other
  exception would reach the request as a server error instead of a 422;
- export is deterministic, so what was parsed survives a round trip: parsing
  the files `serialize_archive` wrote yields an archive whose export is
  byte-identical. Comparing the bytes, not the dataclasses, keeps the source
  path and the index's position out of it — transport, not content.
"""

# pyright: reportAttributeAccessIssue=false, reportUnknownMemberType=false
# atheris ships no type information. `instrument_imports` is the one member
# pyright cannot resolve; a stub for a dependency that is not part of the
# product would cost more than this file's three verified calls.

from __future__ import annotations

import sys

import atheris

with atheris.instrument_imports():
    from app.kernel.interchange.format import ArchiveError, parse_archive, serialize_archive
    from app.kernel.interchange.tree import ArchiveTree

_METADATA = b'{"title":"fuzz","chapters":[],"relations":[]}'
"""Valid and minimal: an invalid one would refuse before the Markdown reader runs."""


def fuzz_one_input(data: bytes) -> None:
    """Parse the bytes as a chapter and as an entity, then round-trip the result."""
    files = {
        "metadata.json": _METADATA,
        "chapters/01-fuzz.md": data,
        "kb/fuzz.md": data,
    }
    try:
        archive = parse_archive(ArchiveTree(files))
    except ArchiveError:
        return
    exported = serialize_archive(archive)
    again = serialize_archive(parse_archive(ArchiveTree(exported)))
    if again != exported:
        raise AssertionError(f"re-export differs: {exported!r} -> {again!r}")


def main() -> None:
    atheris.Setup(sys.argv, fuzz_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
