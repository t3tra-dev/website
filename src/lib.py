from urllib.parse import urlparse

import asgi
from fastapi import FastAPI
from jinja2 import DictLoader, Environment, TemplateNotFound, select_autoescape
from js import URL as JSURL, Request as JSRequest  # type: ignore
from workers import Response, WorkerEntrypoint


class Default(WorkerEntrypoint):
    async def fetch(self, request: JSRequest):
        path = urlparse(request.url).path
        if path.startswith("/templates/"):
            return Response("Not Found", status=404)
        if path.startswith("/static/"):
            return await self.env.ASSETS.fetch(request)
        app.state.worker_env = self.env

        return await asgi.fetch(app, request, self.env)


app = FastAPI(debug=True)

_TEMPLATE_STRINGS: dict[str, str] = {}
_jinja = Environment(
    loader=DictLoader(_TEMPLATE_STRINGS),
    autoescape=select_autoescape(["html", "xml"]),
)


async def _load_template_from_assets(template_name: str) -> None:
    if template_name in _TEMPLATE_STRINGS:
        return

    worker_env = getattr(app.state, "worker_env", None)
    if worker_env is None:
        raise RuntimeError("worker_env is not set; ensure requests go through Default.fetch")

    url = JSURL.new("http://local")
    url.pathname = f"/templates/{template_name}"
    asset_request = JSRequest.new(url.href)
    asset_response = await worker_env.ASSETS.fetch(asset_request)

    status = int(asset_response.status)
    if status >= 400:
        raise TemplateNotFound(template_name)

    _TEMPLATE_STRINGS[template_name] = await asset_response.text()


async def render_template(template_name: str, context: dict = {}) -> str:
    if context is None:
        context = {}

    for _ in range(10):
        try:
            return _jinja.get_template(template_name).render(**context)
        except TemplateNotFound as exc:
            missing = getattr(exc, "name", None) or (exc.args[0] if exc.args else None)
            if not missing:
                raise
            await _load_template_from_assets(str(missing))

    raise RuntimeError("Too many missing templates while rendering")


_favicon_cache: bytes | None = None


async def load_favicon() -> bytes:
    global _favicon_cache

    if _favicon_cache is not None:
        return _favicon_cache

    worker_env = getattr(app.state, "worker_env", None)
    if worker_env is None:
        raise RuntimeError("worker_env is not set; ensure requests go through Default.fetch")

    url = JSURL.new("http://local")
    url.pathname = "/static/favicon.ico"
    asset_request = JSRequest.new(url.href)
    asset_response = await worker_env.ASSETS.fetch(asset_request)

    status = int(asset_response.status)
    if status >= 400:
        raise RuntimeError(f"Failed to load favicon.ico: status {status}")

    _favicon_cache = await asset_response.bytes()

    if _favicon_cache is None:
        raise RuntimeError("Failed to read favicon.ico content")

    return _favicon_cache
