from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Optional

import requests
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RequestConfig:
    """Configuration object for HTTP requests."""

    timeout_seconds: int = 20
    min_delay_seconds: float = 2.5
    max_delay_seconds: float = 6.0
    max_retries: int = 3
    backoff_factor: float = 1.5


class BaseScraper:
    """Reusable HTTP scraper base class with retries, headers and pacing."""

    def __init__(
        self,
        base_url: str,
        request_config: Optional[RequestConfig] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.request_config = request_config or RequestConfig()
        self.session = self._build_session()

    def _build_session(self) -> Session:
        """Create a requests session configured with retry strategy."""
        session = requests.Session()

        retry_strategy = Retry(
            total=self.request_config.max_retries,
            read=self.request_config.max_retries,
            connect=self.request_config.max_retries,
            backoff_factor=self.request_config.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9,it-IT;q=0.8,it;q=0.7",
                "Connection": "keep-alive",
            }
        )
        return session

    def _sleep_before_request(self) -> None:
        """Pause between requests to reduce the chance of being blocked."""
        delay_seconds = random.uniform(
            self.request_config.min_delay_seconds,
            self.request_config.max_delay_seconds,
        )
        LOGGER.info("Sleeping %.2f seconds before request.", delay_seconds)
        time.sleep(delay_seconds)

    def get(self, path: str = "") -> Response:
        """Execute a GET request against the base URL plus optional path."""
        self._sleep_before_request()
        url = f"{self.base_url}/{path.lstrip('/')}" if path else self.base_url
        LOGGER.info("Fetching URL: %s", url)

        response = self.session.get(
            url,
            timeout=self.request_config.timeout_seconds,
        )
        response.raise_for_status()
        return response