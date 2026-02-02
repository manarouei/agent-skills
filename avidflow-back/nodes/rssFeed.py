import logging
from typing import Any, Dict, List
from urllib.parse import urlparse

import requests
try:
    import feedparser
except ImportError:  # Lightweight fallback (very limited)
    feedparser = None

from .base import BaseNode, NodeParameterType
from models import NodeExecutionData

logger = logging.getLogger(__name__)


class RssFeedReadNode(BaseNode):
    """
    RssFeedRead node.
    Reads an RSS/Atom feed and outputs each item as a separate workflow item.
    """

    type = "rssFeedRead"
    version = 2

    description = {
        "displayName": "RSS Read",
        "name": "rssFeedRead",
        "icon": "fa:rss",
        "group": ["input"],
        "description": "Reads data from an RSS/Atom feed",
        "defaults": {
            "name": "RSS Read",
            "color": "#b02020",
        },
        "inputs": [
            {"name": "main", "type": "main", "required": False},
        ],
        "outputs": [
            {"name": "main", "type": "main", "required": True},
        ],
    }

    properties = {
        "parameters": [
            {
                "name": "url",
                "type": NodeParameterType.STRING,
                "display_name": "URL",
                "default": "",
                "required": True,
                "description": "URL of the RSS/Atom feed",
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "placeholder": "Add option",
                "default": {},
                "options": [
                    {
                        "name": "ignoreSSL",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Ignore SSL Issues (Insecure)",
                        "default": False,
                        "description": "Whether to ignore SSL/TLS certificate issues",
                    },
                    {
                        "name": "userAgent",
                        "type": NodeParameterType.STRING,
                        "display_name": "User Agent",
                        "default": "python-rss/1.0",
                        "description": "Custom user-agent header",
                    },
                ],
            },
        ],
    }

    icon = "fa:rss"
    color = "orange-red"

    def execute(self) -> List[List[NodeExecutionData]]:
        out: List[NodeExecutionData] = []

        input_items = self.get_input_data()
        items_length = len(input_items) if input_items else 1

        for item_index in range(items_length):
            try:
                url = self.get_node_parameter("url", item_index, "")
                if not url:
                    raise ValueError("The parameter 'URL' must be set")

                if not self._validate_url(url):
                    raise ValueError(f"Invalid URL: {url}")

                options = self.get_node_parameter("options", item_index, {}) or {}
                ignore_ssl = bool(options.get("ignoreSSL", False))
                user_agent = (options.get("userAgent") or "python-rss/1.0").strip()

                feed_items = self._fetch_feed(
                    url=url,
                    ignore_ssl=ignore_ssl,
                    user_agent=user_agent,
                )


                for entry in feed_items:
                    out.append(NodeExecutionData(json_data=entry, binary_data=None))

            except Exception as e:
                out.append(
                    NodeExecutionData(
                        json_data={"error": str(e), "url": self.get_node_parameter("url", item_index, "")},
                        binary_data=None,
                    )
                )

        return [out]

    # ---------------- Helpers ----------------

    def _validate_url(self, url: str) -> bool:
        try:
            p = urlparse(url)
            return p.scheme in ("http", "https") and bool(p.netloc)
        except Exception:
            return False

    def _fetch_feed(
        self,
        url: str,
        ignore_ssl: bool,
        user_agent: str,
    ) -> List[Dict[str, Any]]:
        headers = {
            "User-Agent": user_agent,
            "Accept": "application/rss+xml, application/rdf+xml;q=0.8, application/atom+xml;q=0.6, application/xml;q=0.4, text/xml;q=0.4"
        }

        resp = requests.get(url, headers=headers, timeout=30, verify=not ignore_ssl)
        if resp.status_code != 200:
            raise ValueError(f"Feed request failed ({resp.status_code}): {resp.text[:200]}")

        content = resp.content

        # Prefer feedparser if available (robust)
        if feedparser:
            parsed = feedparser.parse(content)
            if getattr(parsed, "bozo", False):  # malformed feed flag
                logger.warning(f"RSS Read - BOZO feed (trying anyway): {parsed.bozo_exception}")
            items = []
            for entry in parsed.entries:
                normalized = {}
                for k, v in entry.items():
                    try:
                        # feedparser returns some objects (e.g., time structs); convert to string
                        normalized[str(k)] = v if isinstance(v, (str, int, float, bool, dict, list)) else str(v)
                    except Exception:
                        pass
                items.append(normalized)
            return items
        # Minimal naive XML fallback (very limited)
        # Return raw XML as single item
        return [{"rawXml": content.decode(errors="replace")}]