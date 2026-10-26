"""Polite HTTP: robots.txt, rate limit, honest User-Agent, retries, request budget."""
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

from . import user_agent
from .models import RawResponse


class RobotsDisallowed(Exception):
    pass


class BudgetExceeded(Exception):
    pass


class Fetcher:
    def __init__(self, min_interval=1.1, max_requests=150, retries=3, timeout=30):
        self.min_interval = min_interval  # seconds between requests to the same host
        self.user_agent = user_agent()
        self.max_requests = max_requests  # hard stop, so a bug can never hammer a site
        self.retries = retries
        self.timeout = timeout
        self.request_count = 0
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser] = {}
        self._session = requests.Session()
        self._session.headers["User-Agent"] = self.user_agent

    def get(self, url: str) -> RawResponse:
        if not self._allowed(url):
            raise RobotsDisallowed(f"robots.txt forbids fetching {url}")
        return self._request(url)

    def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            self._robots[host] = self._load_robots(host)
        return self._robots[host].can_fetch(self.user_agent, url)

    def _load_robots(self, host: str) -> RobotFileParser:
        parser = RobotFileParser()
        try:
            response = self._request(f"{host}/robots.txt", allow_error=True)
        except requests.RequestException:
            parser.disallow_all = True  # cannot read the rules, so do not guess
            return parser
        if response.status >= 500:
            parser.disallow_all = True
        elif response.status >= 400:
            parser.allow_all = True  # no robots.txt means no restrictions
        else:
            parser.parse(response.content.decode("utf-8", "replace").splitlines())
        return parser

    def _request(self, url: str, allow_error=False) -> RawResponse:
        host = urlsplit(url).netloc
        last_error: Exception | None = None
        for attempt in range(self.retries):
            if self.request_count >= self.max_requests:
                raise BudgetExceeded(f"request budget of {self.max_requests} used up")
            wait = self._last_hit.get(host, 0) + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_hit[host] = time.monotonic()
            self.request_count += 1
            try:
                r = self._session.get(url, timeout=self.timeout)
            except requests.RequestException as error:
                last_error = error
                time.sleep(2 ** attempt)
                continue
            if r.status_code >= 500 and attempt < self.retries - 1:
                time.sleep(2 ** attempt)
                continue
            if r.status_code >= 400 and not allow_error:
                raise requests.HTTPError(f"{r.status_code} for {url}")
            return RawResponse(
                url=r.url, content=r.content, status=r.status_code,
                content_type=r.headers.get("Content-Type", ""),
                fetched_at=datetime.now(timezone.utc),
            )
        raise requests.RequestException(f"giving up on {url}: {last_error}")
