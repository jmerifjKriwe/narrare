"""Thin httpx API client for the benchmark runner — auth, REST, SSE lines.

Implements the verified auth flow (``benchmark/docs/api-surface.md`` §2):
``POST /auth/register`` and ``POST /auth/login`` return the token pair in
the response body (the ``narrare_refresh`` httpOnly cookie is not needed —
refresh works via the JSON body), every subsequent call injects
``Authorization: Bearer <access_token>``, and a 401 triggers exactly ONE
token refresh (``POST /auth/refresh`` with ``{"refresh_token": ...}``)
followed by one retry of the original call; a failing refresh propagates
its ``ApiError`` and a second 401 raises instead of looping.

Error typing follows the map's §1 conventions: domain errors carry
``{"detail": <str>, "code": <str>}``, FastAPI validation errors carry a
list detail (rendered into ``ApiError.detail``), unhandled 500s carry a
string detail without code, and non-JSON bodies fall back to raw text.
Status 429 is treated as the signal itself (map OPEN-4) — the body is
parsed best-effort only.

This client speaks only generic ``request``/``stream`` — endpoint-specific
helpers belong to the capability drivers (plan Tasks 7+), never here.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, cast

import httpx

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from contextlib import AbstractContextManager
    from types import TracebackType

_API_PREFIX = "/api/v1"
_UNAUTHORIZED: Final[int] = 401
"""HTTP status triggering the single refresh+retry (map §2/§6 auth contract)."""


class ApiError(RuntimeError):
    """Non-2xx API response with the parsed error body (map §1 shapes)."""

    def __init__(
        self,
        *,
        status: int,
        detail: str,
        code: str | None,
        body: object,
    ) -> None:
        label = f" [{code}]" if code is not None else ""
        super().__init__(f"HTTP {status}{label}: {detail}")
        self.status = status
        self.detail = detail
        self.code = code
        self.body = body


@dataclass(frozen=True)
class TokenPair:
    """Mirrors ``TokenResponse`` (map §2) — access + refresh from the body."""

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


def _render_list_detail(items: list[object]) -> str:
    """Render FastAPI's 422 ``detail`` list into one compact string."""
    parts: list[str] = []
    for item in items:
        if isinstance(item, dict):
            entry = cast("dict[str, object]", item)
            msg = entry.get("msg")
            parts.append(msg if isinstance(msg, str) else json.dumps(item))
        else:
            parts.append(json.dumps(item))
    return "; ".join(parts)


def parse_error_body(raw: bytes) -> tuple[str, str | None, object]:
    """Parse an error body per map §1 into ``(detail, code, raw_body)``.

    Handles the domain shape ``{"detail": str, "code": str}``, FastAPI's
    422 list detail, JSON bodies without ``detail``, and non-JSON text.
    """
    text = raw.decode("utf-8", errors="replace")
    try:
        parsed: object = json.loads(text)
    except json.JSONDecodeError:
        return (text if text else "<empty body>"), None, text
    if not isinstance(parsed, dict):
        return json.dumps(parsed), None, parsed
    body = cast("dict[str, object]", parsed)
    detail = body.get("detail")
    code = body.get("code")
    if isinstance(detail, str):
        return detail, (code if isinstance(code, str) else None), body
    if isinstance(detail, list):
        return _render_list_detail(cast("list[object]", detail)), None, body
    return json.dumps(body), None, body


@dataclass(frozen=True)
class _RequestArgs:
    """Typed keyword passthrough shared by ``request`` and ``stream``."""

    json: object | None = None
    params: Mapping[str, str] | None = None
    headers: Mapping[str, str] | None = None


class BenchmarkClient:
    """Synchronous httpx client for the production REST/SSE surface.

    Constructed with a concrete ``base_url`` and ``timeout_seconds`` (the
    caller wires these from ``ApiConfig``; ``base_url=None`` derivation is
    the stack manager's concern). ``transport`` is the test seam —
    production passes nothing and uses the real HTTP transport.
    """

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        *,
        tokens: TokenPair | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """``tokens`` seeds an already-authenticated session (DI seam).

        Production wires no tokens (provisioning logs in through this
        client); callers that hold tokens from an earlier step — and tests
        that pin post-authentication call sequences — inject them here.
        """
        self._http = httpx.Client(base_url=base_url, timeout=timeout_seconds, transport=transport)
        self._tokens = tokens

    # -- lifecycle ------------------------------------------------------------

    def close(self) -> None:
        """Release the underlying connection pool."""
        self._http.close()

    def __enter__(self) -> BenchmarkClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def http_timeout(self) -> httpx.Timeout:
        """Effective httpx timeout — for diagnostics and tests."""
        return self._http.timeout

    # -- auth flow (map §2) -----------------------------------------------------

    def register(self, email: str, password: str, display_name: str = "") -> TokenPair:
        """``POST /auth/register`` → 201 ``TokenResponse`` (map §2.1)."""
        return self._token_call(
            "POST",
            f"{_API_PREFIX}/auth/register",
            payload={"email": email, "password": password, "display_name": display_name},
        )

    def login(self, email: str, password: str) -> TokenPair:
        """``POST /auth/login`` → 200 ``TokenResponse`` (map §2.2)."""
        return self._token_call(
            "POST",
            f"{_API_PREFIX}/auth/login",
            payload={"email": email, "password": password},
        )

    def refresh(self) -> TokenPair:
        """``POST /auth/refresh`` with the stored refresh token (map §2.3).

        The httpOnly cookie variant is intentionally unused — the runner
        speaks server-to-server and keeps tokens in memory.
        """
        if self._tokens is None:
            raise ApiError(
                status=0,
                detail="refresh requested but no tokens held (login/register first)",
                code=None,
                body=None,
            )
        return self._token_call(
            "POST",
            f"{_API_PREFIX}/auth/refresh",
            payload={"refresh_token": self._tokens.refresh_token},
        )

    # -- generic REST / SSE (drivers build endpoint helpers on these) ----------

    def request(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        """Authenticated generic request; returns the 2xx response.

        Non-2xx raises ``ApiError``. A 401 triggers exactly one refresh +
        retry; the retried 401 (or a failed refresh) raises instead of
        looping.
        """
        args = _RequestArgs(json=json, params=params, headers=headers)
        response = self._send(method, path, args, bearer=self._bearer(), raise_on_error=False)
        if response.status_code == _UNAUTHORIZED and self._tokens is not None:
            self.refresh()  # failed refresh raises and replaces the original 401
            response = self._send(method, path, args, bearer=self._bearer())
        return self._checked(response)

    @contextlib.contextmanager
    def stream(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Iterator[Iterator[str]]:
        """Authenticated generic SSE stream — yields the line iterator.

        Use as ``with client.stream(...) as lines:``. Pre-stream failures
        (auth 401, rate 429, validation 422) raise ``ApiError`` at
        ``__enter__`` time (map §6); a 401 refreshes and reopens exactly
        once. Consume ``lines`` inside the ``with`` block.
        """
        args = _RequestArgs(json=json, params=params, headers=headers)
        with contextlib.ExitStack() as stack:
            response = stack.enter_context(self._open_stream(method, path, args))
            if response.status_code == _UNAUTHORIZED and self._tokens is not None:
                stack.close()  # close the stale 401 attempt before refreshing
                self.refresh()
                response = stack.enter_context(self._open_stream(method, path, args))
            if response.status_code >= 400:
                response.read()  # must read inside the stream context
                detail, code, body = parse_error_body(response.content)
                raise ApiError(status=response.status_code, detail=detail, code=code, body=body)
            yield response.iter_lines()

    # -- internals ---------------------------------------------------------------

    def _open_stream(
        self, method: str, path: str, args: _RequestArgs
    ) -> AbstractContextManager[httpx.Response]:
        return self._http.stream(
            method,
            path,
            json=args.json,
            params=args.params,
            headers=self._auth_headers(args.headers, self._bearer()),
        )

    def _bearer(self) -> str | None:
        return self._tokens.access_token if self._tokens is not None else None

    def _auth_headers(self, extra: Mapping[str, str] | None, bearer: str | None) -> dict[str, str]:
        merged = dict(extra) if extra else {}
        if bearer is not None:
            merged["Authorization"] = f"Bearer {bearer}"
        return merged

    def _send(
        self,
        method: str,
        path: str,
        args: _RequestArgs,
        *,
        bearer: str | None,
        raise_on_error: bool = True,
    ) -> httpx.Response:
        response = self._http.request(
            method,
            path,
            json=args.json,
            params=args.params,
            headers=self._auth_headers(args.headers, bearer),
        )
        if raise_on_error:
            return self._checked(response)
        return response

    @staticmethod
    def _checked(response: httpx.Response) -> httpx.Response:
        """Return the response if 2xx, else raise ``ApiError`` from its body."""
        if response.status_code >= 400:
            detail, code, body = parse_error_body(response.content)
            raise ApiError(status=response.status_code, detail=detail, code=code, body=body)
        return response

    def _token_call(self, method: str, path: str, *, payload: object) -> TokenPair:
        # Auth endpoints take no Authorization header (map §2: Auth: none).
        response = self._send(method, path, _RequestArgs(json=payload), bearer=None)
        return self._token_pair(response)

    def _token_pair(self, response: httpx.Response) -> TokenPair:
        payload: object = response.json()
        if not isinstance(payload, dict):
            raise ApiError(
                status=response.status_code,
                detail="token response is not a JSON object",
                code=None,
                body=payload,
            )
        body = cast("dict[str, object]", payload)
        access = body.get("access_token")
        refresh = body.get("refresh_token")
        if not isinstance(access, str) or not isinstance(refresh, str):
            raise ApiError(
                status=response.status_code,
                detail="token response missing access_token/refresh_token strings",
                code=None,
                body=body,
            )
        token_type = body.get("token_type")
        expires_in = body.get("expires_in")
        tokens = TokenPair(
            access_token=access,
            refresh_token=refresh,
            token_type=token_type if isinstance(token_type, str) else "bearer",
            expires_in=expires_in if isinstance(expires_in, int) else 0,
        )
        self._tokens = tokens
        return tokens
