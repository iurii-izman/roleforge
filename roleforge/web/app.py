"""
FastAPI web operator console scaffold (TASK-094).

Stack: FastAPI + Jinja2 + HTMX.
Auth: Bearer token (TASK-095), single-user.
"""

from __future__ import annotations

# mypy: ignore-errors

import json
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from roleforge.runtime import connect_db, get_setting
from roleforge.web import queries
from roleforge.web.source_registry import list_feeds, list_monitors, toggle_feed, toggle_monitor
from roleforge.queue import apply_review_action
from roleforge.job_runs import log_job_finish, log_job_start
from roleforge.web.profile_editor import diff_top_level_keys, update_profile_config, validate_profile_config


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _bearer_token() -> str | None:
    token = get_setting("WEB_BEARER_TOKEN")
    return token.strip() if token else None


class BearerAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        # Health endpoint is always unauthenticated.
        if request.url.path == "/health":
            return await call_next(request)

        token = _bearer_token()
        if not token:
            # Dev-friendly: if no token configured, run unauthenticated.
            resp = await call_next(request)
            resp.headers["X-RoleForge-Auth"] = "disabled"
            return resp

        auth = request.headers.get("authorization") or ""
        if not auth.lower().startswith("bearer "):
            return PlainTextResponse("Unauthorized", status_code=401)
        provided = auth.split(" ", 1)[1].strip()
        if provided != token:
            return PlainTextResponse("Unauthorized", status_code=401)
        return await call_next(request)


def create_app() -> FastAPI:
    app = FastAPI(title="RoleForge Operator Console", version="0.1")
    app.add_middleware(BearerAuthMiddleware)

    @app.get("/health", response_class=PlainTextResponse)
    def health() -> str:
        return "ok"

    @app.get("/", response_class=RedirectResponse)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/analytics", status_code=302)

    @app.get("/analytics", response_class=HTMLResponse)
    def analytics(request: Request) -> HTMLResponse:
        conn = connect_db()
        try:
            score_bands = queries.score_distribution(conn)
            per_profile = queries.match_counts_by_profile(conn, days=14)
            sources = queries.source_counts(conn, days=30)
            funnel = queries.application_funnel(conn, days=90)
            recent_runs = queries.recent_job_runs(conn, limit=10)
        finally:
            conn.close()
        return templates.TemplateResponse(
            "analytics.html",
            {
                "request": request,
                "page_title": "Analytics",
                "score_bands": score_bands,
                "per_profile": per_profile,
                "sources": sources,
                "funnel": funnel,
                "recent_runs": recent_runs,
            },
        )

    @app.get("/system-health", response_class=HTMLResponse)
    def system_health(request: Request) -> HTMLResponse:
        conn = connect_db()
        try:
            grouped = queries.job_status_by_type(conn, per_type=5)
        finally:
            conn.close()
        return templates.TemplateResponse(
            "system_health.html",
            {
                "request": request,
                "page_title": "System health",
                "job_runs_by_type": grouped,
            },
        )

    @app.get("/sources", response_class=HTMLResponse)
    def sources(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            "sources.html",
            {
                "request": request,
                "page_title": "Sources",
                "feeds": list_feeds(),
                "monitors": list_monitors(),
                "feed_intake_enabled": (get_setting("FEED_INTAKE_ENABLED") or "").strip().lower() in ("1", "true", "yes"),
                "monitor_intake_enabled": (get_setting("MONITOR_INTAKE_ENABLED") or "").strip().lower() in ("1", "true", "yes"),
            },
        )

    @app.get("/queue-browser", response_class=HTMLResponse)
    def queue_browser(request: Request) -> HTMLResponse:
        profile_id = request.query_params.get("profile_id") or None
        state = request.query_params.get("state") or None
        conn = connect_db()
        try:
            profiles = queries.list_profiles(conn)
            items = queries.queue_browser_items(conn, profile_id=profile_id, state=state, limit=200)
        finally:
            conn.close()
        return templates.TemplateResponse(
            "queue_browser.html",
            {
                "request": request,
                "page_title": "Queue browser",
                "profiles": profiles,
                "selected_profile_id": profile_id or "",
                "selected_state": state or "",
                "items": items,
            },
        )

    @app.get("/profiles", response_class=HTMLResponse)
    def profiles(request: Request) -> HTMLResponse:
        conn = connect_db()
        try:
            profiles_list = queries.list_profiles(conn)
        finally:
            conn.close()
        return templates.TemplateResponse(
            "profiles.html",
            {"request": request, "page_title": "Profiles", "profiles": profiles_list},
        )

    @app.get("/profiles/{profile_id}", response_class=HTMLResponse)
    def profile_detail(request: Request, profile_id: str) -> HTMLResponse:
        conn = connect_db()
        try:
            p = queries.get_profile(conn, profile_id)
        finally:
            conn.close()
        if not p:
            return templates.TemplateResponse(
                "profile_detail.html",
                {"request": request, "page_title": "Profiles", "not_found": True},
                status_code=404,
            )
        return templates.TemplateResponse(
            "profile_detail.html",
            {"request": request, "page_title": "Profiles", "profile": p, "config_json": json.dumps(p["config"], indent=2, default=str)},
        )

    @app.post("/profiles/{profile_id}", response_class=HTMLResponse)
    async def profile_update(request: Request, profile_id: str) -> HTMLResponse:
        form = await request.form()
        raw = str(form.get("config_json") or "")
        vr = validate_profile_config(raw)
        if not vr.ok or vr.config is None:
            conn = connect_db()
            try:
                p = queries.get_profile(conn, profile_id)
            finally:
                conn.close()
            return templates.TemplateResponse(
                "profile_detail.html",
                {
                    "request": request,
                    "page_title": "Profiles",
                    "profile": p,
                    "config_json": raw,
                    "error": vr.message,
                },
                status_code=400,
            )

        conn = connect_db()
        run_id = log_job_start(conn, "web_profile_edit")
        try:
            existing = queries.get_profile(conn, profile_id)
            if not existing:
                log_job_finish(conn, run_id, "failure", {"profile_id": profile_id, "message": "profile not found"})
                return PlainTextResponse("Not found", status_code=404)
            old_cfg = existing["config"] if isinstance(existing["config"], dict) else {}
            changed = diff_top_level_keys(old_cfg, vr.config)
            if old_cfg == vr.config:
                summary = {
                    "profile_id": profile_id,
                    "status": "noop",
                    "changed_keys": [],
                    "bytes": len(raw.encode("utf-8")),
                }
                log_job_finish(conn, run_id, "success", summary)
            else:
                update_profile_config(conn, profile_id=profile_id, new_config=vr.config)
                summary = {
                    "profile_id": profile_id,
                    "status": "updated",
                    "changed_keys": changed,
                    "bytes": len(raw.encode("utf-8")),
                }
                log_job_finish(conn, run_id, "success", summary)
        except Exception as exc:
            log_job_finish(conn, run_id, "failure", {"profile_id": profile_id, "message": str(exc)})
            raise
        finally:
            conn.close()

        # Re-render detail view after update.
        conn = connect_db()
        try:
            p = queries.get_profile(conn, profile_id)
        finally:
            conn.close()
        return templates.TemplateResponse(
            "profile_detail.html",
            {
                "request": request,
                "page_title": "Profiles",
                "profile": p,
                "config_json": json.dumps((p or {}).get("config") or {}, indent=2, default=str),
                "success": True,
            },
        )

    @app.post("/queue-browser/bulk-action", response_class=RedirectResponse)
    async def queue_bulk_action(request: Request) -> RedirectResponse:
        form = await request.form()
        action = (form.get("action") or "").strip()
        selected = form.getlist("profile_match_id")
        profile_id = (form.get("profile_id") or "").strip()
        state = (form.get("state") or "").strip()
        if action and selected:
            conn = connect_db()
            try:
                for pm_id in selected:
                    apply_review_action(conn, pm_id, action)
            finally:
                conn.close()
        query = []
        if profile_id:
            query.append(f"profile_id={profile_id}")
        if state:
            query.append(f"state={state}")
        qs = ("?" + "&".join(query)) if query else ""
        return RedirectResponse(url="/queue-browser" + qs, status_code=303)

    @app.post("/sources/feeds/{feed_id}/toggle", response_class=HTMLResponse)
    def toggle_feed_enabled(request: Request, feed_id: str) -> HTMLResponse:
        enabled = (request.query_params.get("enabled") or "").lower() in ("1", "true", "yes", "on")
        toggle_feed(feed_id, enabled=enabled)
        feeds = list_feeds()
        # Return only the feeds table fragment (HTMX swap).
        return templates.TemplateResponse(
            "partials/feeds_table.html",
            {"request": request, "feeds": feeds},
        )

    @app.post("/sources/monitors/{monitor_id}/toggle", response_class=HTMLResponse)
    def toggle_monitor_enabled(request: Request, monitor_id: str) -> HTMLResponse:
        enabled = (request.query_params.get("enabled") or "").lower() in ("1", "true", "yes", "on")
        toggle_monitor(monitor_id, enabled=enabled)
        monitors = list_monitors()
        return templates.TemplateResponse(
            "partials/monitors_table.html",
            {"request": request, "monitors": monitors},
        )

    @app.get("/healthz", response_class=RedirectResponse)
    def legacy_healthz() -> RedirectResponse:
        # Small convenience alias; keep /health canonical.
        return RedirectResponse(url="/health", status_code=302)

    return app


app = create_app()

