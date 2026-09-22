from __future__ import annotations

import json
import time
from typing import Any, Iterator

import httpx

from .config import Settings
from .errors import ApiError

GRAPH = "https://graph.facebook.com"

# Error codes Meta documents as transient / rate-limit related.
RETRYABLE_CODES = {1, 2, 4, 17, 32, 613, 80000, 80001, 80003, 80004, 80014}


class MetaClient:
    """Thin HTTPS client for the Marketing API.

    - Adds the access token to every request.
    - Raises ApiError with Meta's own message, code and fbtrace_id.
    - Retries transient errors and rate limits with backoff.
    - Follows cursor pagination in iter_pages / get_all.
    """

    def __init__(self, settings: Settings, timeout: float = 60.0, max_retries: int = 4,
                 transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.base = f"{GRAPH}/{settings.api_version}"
        self.max_retries = max_retries
        self._http = httpx.Client(timeout=timeout, transport=transport)

    # -- low level ---------------------------------------------------------

    def _url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.base}/{path.lstrip('/')}"

    @staticmethod
    def _encode(params: dict[str, Any] | None) -> dict[str, str]:
        out: dict[str, str] = {}
        for k, v in (params or {}).items():
            if v is None:
                continue
            if isinstance(v, (dict, list)):
                out[k] = json.dumps(v, separators=(",", ":"))
            elif isinstance(v, bool):
                out[k] = "true" if v else "false"
            else:
                out[k] = str(v)
        return out

    def request(self, method: str, path: str, params: dict[str, Any] | None = None,
                data: dict[str, Any] | None = None, files: dict[str, Any] | None = None) -> Any:
        url = self._url(path)
        q = self._encode(params)
        q["access_token"] = self.settings.access_token
        body = self._encode(data) if data else None
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self._http.request(method, url, params=q, data=body, files=files)
            except httpx.TransportError as e:
                if attempt > self.max_retries:
                    raise ApiError(0, None, None, f"network error: {e}") from e
                time.sleep(min(2 ** attempt, 30))
                continue

            try:
                payload = resp.json()
            except ValueError:
                payload = {"raw": resp.text}

            if resp.status_code < 400 and "error" not in payload:
                return payload

            err = payload.get("error", {}) if isinstance(payload, dict) else {}
            api_err = ApiError(
                status=resp.status_code,
                code=err.get("code"),
                subcode=err.get("error_subcode"),
                message=err.get("message") or str(payload)[:500],
                user_msg=err.get("error_user_msg"),
                trace=err.get("fbtrace_id"),
            )
            retryable = api_err.code in RETRYABLE_CODES or resp.status_code in (429, 500, 502, 503)
            if retryable and attempt <= self.max_retries:
                time.sleep(min(2 ** attempt * 2, 60))
                continue
            raise api_err

    def get(self, path: str, **params: Any) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, **data: Any) -> Any:
        return self.request("POST", path, data=data)

    def delete(self, path: str, **params: Any) -> Any:
        return self.request("DELETE", path, params=params)

    # -- pagination --------------------------------------------------------

    def iter_pages(self, path: str, **params: Any) -> Iterator[dict[str, Any]]:
        page = self.get(path, **params)
        while True:
            for item in page.get("data", []):
                yield item
            nxt = (page.get("paging") or {}).get("next")
            if not nxt:
                return
            # "next" already carries access_token and params.
            page = self.request("GET", nxt)

    def get_all(self, path: str, limit: int | None = None, **params: Any) -> list[dict[str, Any]]:
        """Collect up to `limit` items across pages. Page size is capped at 100 by the API."""
        params.setdefault("limit", min(limit or 100, 100))
        out: list[dict[str, Any]] = []
        for item in self.iter_pages(path, **params):
            out.append(item)
            if limit and len(out) >= limit:
                break
        return out
