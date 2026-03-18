from __future__ import annotations

import asyncio
import unittest

# mypy: ignore-errors

from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response


class TestWebBearerAuthMiddleware(unittest.TestCase):
    def _make_request(self, path: str, *, authorization: str | None = None) -> Request:
        headers = []
        if authorization is not None:
            headers.append((b"authorization", authorization.encode("utf-8")))
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 1234),
            "server": ("127.0.0.1", 8000),
        }
        return Request(scope)

    def test_health_is_unauthenticated(self) -> None:
        from roleforge.web.app import BearerAuthMiddleware, create_app

        app = create_app()
        mw = BearerAuthMiddleware(app)

        async def call_next(_req: Request) -> Response:
            return PlainTextResponse("ok", status_code=200)

        req = self._make_request("/health")
        resp = asyncio.run(mw.dispatch(req, call_next))
        self.assertEqual(resp.status_code, 200)

    def test_unauthorized_when_token_set_and_header_missing(self) -> None:
        import os

        from roleforge.web.app import BearerAuthMiddleware, create_app

        os.environ["WEB_BEARER_TOKEN"] = "t1"
        try:
            app = create_app()
            mw = BearerAuthMiddleware(app)

            async def call_next(_req: Request) -> Response:
                return PlainTextResponse("ok", status_code=200)

            req = self._make_request("/analytics")
            resp = asyncio.run(mw.dispatch(req, call_next))
            self.assertEqual(resp.status_code, 401)
        finally:
            os.environ.pop("WEB_BEARER_TOKEN", None)

    def test_allows_when_token_set_and_header_matches(self) -> None:
        import os

        from roleforge.web.app import BearerAuthMiddleware, create_app

        os.environ["WEB_BEARER_TOKEN"] = "t2"
        try:
            app = create_app()
            mw = BearerAuthMiddleware(app)

            async def call_next(_req: Request) -> Response:
                return PlainTextResponse("ok", status_code=200)

            req = self._make_request("/analytics", authorization="Bearer t2")
            resp = asyncio.run(mw.dispatch(req, call_next))
            self.assertEqual(resp.status_code, 200)
        finally:
            os.environ.pop("WEB_BEARER_TOKEN", None)

