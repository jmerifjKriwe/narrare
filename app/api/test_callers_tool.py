"""The `just callers` recipe is a dev tool, but its argument grammar decides which
symbol an agent ends up asking about. `path:line` once resolved to `async` instead
of the method name and answered about nothing; `find_symbol` is the other half,
where a wrong pick silently answers for a different function of the same file.
The LSP transport tests use a small subprocess to exercise responses and EOF
without starting Pyright.
"""

import ast
import json
import os
import shutil
import subprocess  # nosec B404 - controlled just invocation, no shell
import sys
import time
from pathlib import Path
from typing import cast

import pytest

from scripts.callers import (
    ROOT,
    CallSite,
    IncomingCall,
    LanguageServer,
    collect_calls,
    find_symbol,
    main,
    parse_target,
    position_for,
    symbol_on_line,
)


def test_find_symbol_skips_decorators_and_matches_the_definition() -> None:
    source = [
        "from __future__ import annotations",
        "",
        "",
        "@property",
        "    async def ordered(self, *args: object) -> list[str]:",
        "        return []",
    ]
    assert find_symbol(source, "ordered") == 4


def test_find_symbol_names_what_the_file_does_declare() -> None:
    source = ["class ProfileRepository:", "    async def ordered(self) -> None: ..."]
    with pytest.raises(LookupError) as error:
        find_symbol(source, "gibtsnicht")
    assert "ProfileRepository" in str(error.value)
    assert "ordered" in str(error.value)


def test_position_lands_inside_the_name_not_on_async() -> None:
    source = ["    async def ordered(self) -> None: ..."]
    assert position_for(source, 0, "ordered")["character"] == source[0].index("ordered")


def test_line_target_picks_the_declared_name() -> None:
    path, symbol, line = parse_target([f"{ROOT}/app/kernel/llm/profiles.py:26"])
    assert (path, symbol, line) == (ROOT / "app/kernel/llm/profiles.py", "", 26)


def test_a_line_target_resolves_to_the_declared_name_not_to_async() -> None:
    assert symbol_on_line(["    async def ordered(self) -> None: ..."], 0) == "ordered"
    assert symbol_on_line(["class ProfileRepository:"], 0) == "ProfileRepository"
    assert symbol_on_line(["    # the line above the definition"], 0) == ""


def test_symbol_target_needs_no_line() -> None:
    path, symbol, line = parse_target(["app/kernel/llm/profiles.py", "ordered"])
    assert (path, symbol, line) == (ROOT / "app/kernel/llm/profiles.py", "ordered", None)


def test_a_target_without_a_symbol_or_a_line_is_refused() -> None:
    with pytest.raises(ValueError, match="symbol name or an explicit path:line"):
        parse_target(["app/kernel/llm/profiles.py"])


def test_a_missing_file_is_named() -> None:
    with pytest.raises(FileNotFoundError, match=r"gibtsnicht\.py"):
        parse_target(["gibtsnicht.py", "ordered"])


@pytest.mark.parametrize("target", ["app/kernel/llm/profiles.py", "app/kernel/llm/profiles.py:26"])
def test_surplus_arguments_are_refused_before_starting_pyright(
    target: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([target, "ordered", "typo"]) == 2
    assert "usage: callers" in capsys.readouterr().err


def test_a_line_target_still_accepts_an_explicit_symbol() -> None:
    path, symbol, line = parse_target(["app/kernel/llm/profiles.py:26", "ordered"])
    assert (path, symbol, line) == (ROOT / "app/kernel/llm/profiles.py", "ordered", 26)


@pytest.mark.parametrize("explicit_symbol", [False, True])
def test_line_queries_report_the_async_methods_actual_callers(
    explicit_symbol: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exercise line conversion and cursor placement against the real Pyright server."""
    path = ROOT / "app/kernel/llm/profiles.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    line = next(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "ordered"
    )
    args = [f"{path}:{line}"]
    if explicit_symbol:
        args.append("ordered")
    assert main(args) == 0
    output = capsys.readouterr().out
    assert f"ordered — app/kernel/llm/profiles.py:{line} (method)" in output
    assert "app/capabilities/settings/profiles_service.py:" in output


@pytest.mark.parametrize(
    ("line", "message"), [(1, "no declaration"), (3, "list index out of range")]
)
def test_line_queries_reject_non_declarations_and_lines_past_eof(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], line: int, message: str
) -> None:
    """Invalid source positions return a CLI error instead of a traceback."""
    path = tmp_path / "empty.py"
    path.write_text("# no declaration on this line\n", encoding="utf-8")
    assert main([f"{path}:{line}"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "error:" in output.err
    assert message in output.err


@pytest.mark.parametrize(
    "args",
    [
        ["folder with spaces/profiles.py", "ordered"],
        ["folder with spaces/profiles.py:26"],
        ["folder/$HOME/[ab]*'profile.py", "ordered"],
        [],
    ],
)
def test_callers_recipe_preserves_argument_boundaries(tmp_path: Path, args: list[str]) -> None:
    """Forward literal CLI arguments through just without shell expansion."""
    just = shutil.which("just")
    assert just is not None, "The repository task runner just is required"
    uv = tmp_path / "uv"
    uv.write_text(
        f"#!{sys.executable}\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    uv.chmod(0o755)
    result = subprocess.run(  # noqa: S603  # nosec - fixed command, synthetic arguments
        [just, "--justfile", str(ROOT / "justfile"), "callers", *args],
        env={**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}"},
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == ["run", "python", "-m", "scripts.callers", *args]


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        (b"", None),
        (b"Content-Length: 10\r\n\r\n{}", None),
        (
            b'Content-Length: 20\r\n\r\n{"method":"message"}'
            b'Content-Length: 24\r\n\r\n{"id":99,"result":false}'
            b'Content-Length: 22\r\n\r\n{"id":1,"result":true}',
            True,
        ),
    ],
    ids=["eof-before-header", "eof-mid-body", "response-before-eof"],
)
def test_server_output_end_fails_fast_without_losing_responses(
    output: bytes, expected: bool | None
) -> None:
    program = (
        "import sys\n"
        "stream = sys.stdin.buffer\n"
        "length = int(stream.readline().split(b':', 1)[1])\n"
        "stream.readline()\n"
        "stream.read(length)\n"
        f"sys.stdout.buffer.write({output!r})\n"
        "sys.stdout.buffer.flush()\n"
    )
    server = LanguageServer([sys.executable, "-c", program], cwd=ROOT)
    try:
        if expected is None:
            with pytest.raises(RuntimeError, match="closed its output before answering initialize"):
                server.request("initialize", {}, timeout=2)
        else:
            assert server.request("initialize", {}, timeout=2) is expected
    finally:
        server.close()


def test_call_sites_are_deduped_and_graded() -> None:
    uri = f"file://{ROOT}/app/capabilities/settings/profiles_service.py"
    test_uri = f"file://{ROOT}/app/kernel/tests/test_llm_profiles.py"
    result = cast(
        "list[IncomingCall]",
        [
            {
                "from": {"uri": uri, "name": "list"},
                "fromRanges": [{"start": {"line": 112, "character": 28}}],
            },
            # pyright sends the same site once per record it builds.
            {
                "from": {"uri": uri, "name": "list"},
                "fromRanges": [{"start": {"line": 112, "character": 28}}],
            },
            {
                "from": {"uri": test_uri, "name": "test_ordered"},
                "fromRanges": [{"start": {"line": 133, "character": 4}}],
            },
        ],
    )
    assert collect_calls(result) == [
        CallSite("app/capabilities/settings/profiles_service.py", 113, "list"),
        CallSite("app/kernel/tests/test_llm_profiles.py", 134, "test_ordered"),
    ]
    assert [site.is_test for site in collect_calls(result)] == [False, True]


def test_a_caller_outside_the_repository_keeps_its_absolute_path() -> None:
    result = cast(
        "list[IncomingCall]",
        [
            {
                "from": {"uri": "file:///elsewhere/mod.py", "name": "caller"},
                "fromRanges": [{"start": {"line": 6, "character": 0}}],
            }
        ],
    )
    assert collect_calls(result)[0].path == "/elsewhere/mod.py"
    assert collect_calls(result)[0].line == 7
    assert not Path(collect_calls(result)[0].path).is_relative_to(ROOT)


@pytest.mark.parametrize("base", [ROOT, Path("/elsewhere")])
def test_caller_uris_decode_spaces_and_reserved_characters(base: Path) -> None:
    """Decode a file URI exactly once, preserving literal plus and percent signs."""
    path = base / "folder with spaces" / "café #+%20.py"
    result: list[IncomingCall] = [
        {
            "from": {"uri": path.as_uri(), "name": "caller"},
            "fromRanges": [{"start": {"line": 6, "character": 0}}],
        }
    ]
    expected = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    assert collect_calls(result) == [CallSite(expected, 7, "caller")]


def test_a_record_without_a_range_falls_back_to_the_callers_own_selection() -> None:
    without_selection = cast(
        "list[IncomingCall]",
        [{"from": {"uri": "file:///x.py", "name": "caller"}, "fromRanges": []}],
    )
    assert collect_calls(without_selection) == []

    with_selection = cast(
        "list[IncomingCall]",
        [
            {
                "from": {
                    "uri": "file:///x.py",
                    "name": "caller",
                    "selectionRange": {"start": {"line": 3, "character": 4}},
                }
            }
        ],
    )
    assert collect_calls(with_selection) == [CallSite("/x.py", 4, "caller")]


def test_the_surplus_argument_is_named() -> None:
    with pytest.raises(ValueError, match="typo"):
        parse_target(["app/kernel/llm/profiles.py", "ordered", "typo"])


def test_no_call_records_means_no_callers() -> None:
    """Pyright answers null for a file outside its workspace; that is zero callers."""
    assert collect_calls([]) == []
    assert collect_calls(None) == []


def test_a_server_that_exits_silently_names_its_exit_code() -> None:
    server = LanguageServer(["/bin/true"], ROOT)
    try:
        started = time.monotonic()
        with pytest.raises(RuntimeError, match="closed its output before answering") as error:
            server.request("initialize", {}, timeout=30)
        assert time.monotonic() - started < 5
        assert "exit code" in str(error.value)
        with pytest.raises(RuntimeError, match="closed its output before answering"):
            server.notify("large-notification", {"text": "x" * 65536})
    finally:
        server.close()
