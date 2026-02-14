from datetime import datetime, timedelta, timezone

from fastapi import Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from js import URL as JSURL, Request as JSRequest  # type: ignore

from lib import Default, app, load_favicon, render_template

__all__ = ["app", "Default", "render_template"]

_quotes_cache: list[str] | None = None


async def _load_quotes() -> list[str]:
    global _quotes_cache

    if _quotes_cache is not None:
        return _quotes_cache

    worker_env = getattr(app.state, "worker_env", None)
    if worker_env is None:
        raise RuntimeError("worker_env is not set; ensure requests go through Default.fetch")

    url = JSURL.new("http://local")
    url.pathname = "/quotes.txt"
    asset_request = JSRequest.new(url.href)
    asset_response = await worker_env.ASSETS.fetch(asset_request)

    status = int(asset_response.status)
    if status >= 400:
        raise RuntimeError(f"Failed to load quotes.txt: status {status}")

    text = await asset_response.text()
    _quotes_cache = [line.strip() for line in text.splitlines() if line.strip()]

    return _quotes_cache


async def get_daily_quote() -> str:
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    date_str = now.strftime("%Y-%m-%d-a")
    date_hash = hash(date_str)

    quotes = await _load_quotes()

    if quotes:
        index = date_hash % len(quotes)
        return quotes[index]

    return "No quotes available."


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return HTMLResponse(await render_template("root/index.html", {"quote": await get_daily_quote()}))


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return HTMLResponse(await render_template("root/about.html"))


@app.get("/projects", response_class=HTMLResponse)
async def projects(request: Request):
    return HTMLResponse(await render_template("root/projects.html"))


@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    return HTMLResponse(await render_template("root/contact.html"))


@app.get("/wp-admin", response_class=RedirectResponse)
async def wp_admin_redirect(request: Request):
    return RedirectResponse("https://www.youtube.com/watch?v=dQw4w9WgXcQ")  # rickroll


@app.get("/favicon.ico")
async def favicon(request: Request):
    favicon_data = await load_favicon()
    return Response(content=favicon_data, media_type="image/x-icon")


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return HTMLResponse(await render_template("error/404.html"), status_code=404)
