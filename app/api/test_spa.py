"""The built web app, served by the API: deep links work, misses stay misses.

One process serves the product: FastAPI answers /api, the built SPA answers
every other path. The five failures this pins, each of which reaches the user:

* a deep link (``/novels/<id>``) returns 404 because no file has that name;
* a missing bundle returns the shell with 200, so the browser reports a syntax
  error instead of a missing file;
* an unknown ``/api`` path returns HTML, so the client parses a page as JSON;
* the shell is cached, so the next release keeps loading the old bundle;
* the third-party notices 404, so the app serves bundled code whose licenses
  demand an accompanying notice.
"""

from typing import TYPE_CHECKING

from httpx import ASGITransport, AsyncClient

from app.api.main import create_app

if TYPE_CHECKING:
    from pathlib import Path

SHELL = "<!doctype html><title>Narrare</title>"
ASSET = "console.log('narrare')"


def _dist(root: Path) -> Path:
    (root / "assets").mkdir()
    (root / "index.html").write_text(SHELL, encoding="utf-8")
    (root / "assets" / "app-abc123.js").write_text(ASSET, encoding="utf-8")
    return root


def _client(dist: Path) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=create_app(dist=dist)), base_url="http://test")


async def test_a_deep_link_returns_the_shell_uncached(tmp_path: Path) -> None:
    async with _client(_dist(tmp_path)) as client:
        response = await client.get("/novels/6f1c1c1e-0000-4000-8000-000000000000")

    assert response.status_code == 200
    assert response.text == SHELL
    assert response.headers["cache-control"] == "no-store"


async def test_a_hashed_asset_is_served_as_immutable(tmp_path: Path) -> None:
    async with _client(_dist(tmp_path)) as client:
        response = await client.get("/assets/app-abc123.js")

    assert response.status_code == 200
    assert response.text == ASSET
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


async def test_the_third_party_notices_are_served_uncached(tmp_path: Path) -> None:
    # The minifier strips license comments, so this file is the only place the
    # bundled libraries' license texts reach the recipient of the app. It has a
    # suffix, so without a route of its own the catch-all would 404 it.
    dist = _dist(tmp_path)
    (dist / "THIRD-PARTY-NOTICES.txt").write_text("react@19.3.0 MIT", encoding="utf-8")

    async with _client(dist) as client:
        response = await client.get("/THIRD-PARTY-NOTICES.txt")

    assert response.status_code == 200
    assert response.text == "react@19.3.0 MIT"
    assert response.headers["cache-control"] == "no-store"


async def test_without_notices_the_path_stays_a_404(tmp_path: Path) -> None:
    # A build that predates the notices generator must not answer with the
    # shell: a browser following the URL would parse HTML as plain text.
    async with _client(_dist(tmp_path)) as client:
        response = await client.get("/THIRD-PARTY-NOTICES.txt")

    assert response.status_code == 404
    assert response.text != SHELL


async def test_a_missing_asset_is_a_404_not_the_shell(tmp_path: Path) -> None:
    async with _client(_dist(tmp_path)) as client:
        response = await client.get("/assets/missing.js")

    assert response.status_code == 404
    assert response.text != SHELL


async def test_an_encoded_traversal_out_of_assets_is_a_404(tmp_path: Path) -> None:
    # The asset route takes the request path, which arrives from the client.
    # A dot segment is percent-encoded here: an HTTP client normalizes a
    # literal `..` before the request leaves, so only the encoded form arrives
    # at the handler with the dots intact — and it must stay a 404.
    dist = _dist(tmp_path)
    (dist / "secret.txt").write_text("SECRET", encoding="utf-8")

    async with _client(dist) as client:
        for path in (
            "/assets/%2e%2e%2fsecret.txt",
            "/assets/..%2fsecret.txt",
            "/assets/sub/%2e%2e/%2e%2e/secret.txt",
        ):
            response = await client.get(path)

            assert response.status_code == 404, path
            assert "SECRET" not in response.text, path


async def test_a_symlink_out_of_assets_is_a_404(tmp_path: Path) -> None:
    # A link inside the build directory that points out of it is not a file of
    # the app: resolving the request path must not serve its target.
    dist = _dist(tmp_path)
    (dist / "secret.txt").write_text("SECRET", encoding="utf-8")
    (dist / "assets" / "escape.js").symlink_to(dist / "secret.txt")

    async with _client(dist) as client:
        response = await client.get("/assets/escape.js")

    assert response.status_code == 404
    assert "SECRET" not in response.text


async def test_a_missing_root_file_is_not_the_shell(tmp_path: Path) -> None:
    # Files from public/ land at the root, not under /assets. The catch-all must
    # not answer them: a browser asking for a favicon and receiving HTML is a
    # console error, and a manifest receiving HTML breaks installation.
    async with _client(_dist(tmp_path)) as client:
        response = await client.get("/favicon.ico")

    assert response.status_code == 404
    assert response.text != SHELL


async def test_an_unknown_api_path_stays_json(tmp_path: Path) -> None:
    async with _client(_dist(tmp_path)) as client:
        response = await client.get("/api/gibtsnicht")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


async def test_the_shell_does_not_reach_the_openapi_document(tmp_path: Path) -> None:
    # The committed document feeds the typed client: a catch-all in it would
    # rewrite every path in web/lib/api/schema.d.ts on the next `just generate`.
    app = create_app(dist=_dist(tmp_path))

    assert "/{full_path}" not in app.openapi()["paths"]


async def test_without_a_build_the_api_serves_no_html(tmp_path: Path) -> None:
    # Development: Vite serves the app on :3100 and proxies /api here. The API
    # answering HTML would hide a broken Vite process behind a working page.
    async with _client(tmp_path / "kein-build") as client:
        response = await client.get("/")

    assert response.status_code == 404
