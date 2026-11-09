"""Small, resilient client for the CKAN Action API (stdlib only)."""
from __future__ import annotations

import json
import logging
import math
import random
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

LOG = logging.getLogger(__name__)
_MAX_TIMEOUT = 600.0
_MAX_RETRIES = 10
_MAX_BACKOFF = 300.0
_MAX_RESPONSE_BYTES = 64 * 1024 * 1024


def _is_finite_number(value: Any) -> bool:
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError):
        return False


class CKANError(RuntimeError):
    """Raised for transport errors or unsuccessful CKAN Action API responses."""


class CKANClient:
    def __init__(self, base_url: str, *, timeout: float = 30.0, retries: int = 4,
                 backoff: float = 0.8, user_agent: str = "BrasilEleitoralDataLab/0.1 (+https://github.com/nrdataanalysis-1908/brasil-eleitoral-datalab)") -> None:
        if not isinstance(base_url, str) or not base_url or base_url != base_url.strip():
            raise ValueError("base_url must be a non-empty absolute HTTP(S) URL")
        parsed = urlparse(base_url)
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError("base_url contains an invalid port") from exc
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or any(character.isspace() for character in base_url)
        ):
            raise ValueError("base_url must be an absolute HTTP(S) URL without credentials, query or fragment")
        if (
            isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not _is_finite_number(timeout) or timeout <= 0 or timeout > _MAX_TIMEOUT
        ):
            raise ValueError(f"timeout must be finite, positive and <= {_MAX_TIMEOUT:g} seconds")
        if (
            isinstance(retries, bool) or not isinstance(retries, int)
            or retries < 0 or retries > _MAX_RETRIES
        ):
            raise ValueError(f"retries must be an integer between 0 and {_MAX_RETRIES}")
        if (
            isinstance(backoff, bool) or not isinstance(backoff, (int, float))
            or not _is_finite_number(backoff) or backoff < 0 or backoff > _MAX_BACKOFF
        ):
            raise ValueError(f"backoff must be finite, non-negative and <= {_MAX_BACKOFF:g} seconds")
        if (
            not isinstance(user_agent, str) or not user_agent.strip()
            or any(ord(character) < 0x20 or ord(character) == 0x7F for character in user_agent)
        ):
            raise ValueError("user_agent must be non-empty and contain no control characters")

        self.base_url = base_url.rstrip("/")
        self.timeout, self.retries, self.backoff, self.user_agent = timeout, retries, backoff, user_agent

    def action(self, name: str, **params: Any) -> Any:
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("CKAN action name must contain only letters, digits, underscores or hyphens")
        url = f"{self.base_url}/api/3/action/{name}?{urlencode(params, doseq=True)}"
        request = Request(url, headers={"Accept": "application/json", "User-Agent": self.user_agent})
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    body = response.read(_MAX_RESPONSE_BYTES + 1)
                    if len(body) > _MAX_RESPONSE_BYTES:
                        raise CKANError(
                            f"CKAN response exceeds the {_MAX_RESPONSE_BYTES}-byte safety limit"
                        )
                    payload = json.loads(body.decode("utf-8"))
                if not isinstance(payload, dict) or payload.get("success") is not True:
                    detail = payload.get("error", payload) if isinstance(payload, dict) else payload
                    raise CKANError(f"CKAN action {name!r} returned success=false: {detail}")
                return payload.get("result")
            except HTTPError as exc:
                last_error = exc
                if exc.code not in {408, 425, 429, 500, 502, 503, 504} or attempt >= self.retries:
                    break
            except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
            delay = self.backoff * (2 ** attempt) + random.uniform(0, self.backoff / 4)
            LOG.warning("CKAN request failed (%s); retry %d/%d in %.2fs", last_error, attempt + 1, self.retries, delay)
            time.sleep(delay)
        raise CKANError(f"CKAN action {name!r} failed after {self.retries + 1} attempts: {last_error}") from last_error

    def search_page(self, *, start: int, rows: int) -> dict[str, Any]:
        if isinstance(start, bool) or not isinstance(start, int) or start < 0:
            raise ValueError("start must be a non-negative integer")
        if isinstance(rows, bool) or not isinstance(rows, int) or not 1 <= rows <= 1000:
            raise ValueError("rows must be an integer between 1 and 1000")
        result = self.action("package_search", q="*:*", start=start, rows=rows, include_private=False)
        if not isinstance(result, dict) or not isinstance(result.get("results"), list):
            raise CKANError("Unexpected package_search response shape")
        count = result.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise CKANError("Unexpected package_search count")
        return result
