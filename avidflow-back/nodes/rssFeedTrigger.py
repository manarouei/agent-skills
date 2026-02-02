import logging
import time
from typing import Any, Dict, List, Optional

import requests
from urllib.parse import urlparse

try:
    import feedparser  # pip install feedparser
except ImportError:
    feedparser = None

from .base import BaseNode, NodeParameterType
from .schedule import ScheduleNode
from models import NodeExecutionData

logger = logging.getLogger(__name__)


class RssFeedReadTriggerNode(ScheduleNode):
    """
    RSS Feed Trigger (polling).
    Emits new feed entries whose isoDate/published is newer than last check.
    """

    type = "rssFeedReadTrigger"
    version = 1

    description = {
        "displayName": "RSS Feed Trigger",
        "name": "rssFeedReadTrigger",
        "icon": "fa:rss",
        "iconColor": "orange-red",
        "group": ["trigger"],
        "version": 1,
        "description": "Starts a workflow when an RSS/Atom feed is updated",
        "defaults": {
            "name": "RSS Feed Trigger",
            "color": "#b02020",
        },
        "polling": True,
        "inputs": [],
        "outputs": [{"name": "main", "type": "main", "required": True}],
    }

    properties = {
        "parameters": ScheduleNode.schedule_parameters() + [
            {
                "name": "feedUrl",
                "type": NodeParameterType.STRING,
                "display_name": "Feed URL",
                "default": "",
                "required": True,
                "description": "URL of the RSS/Atom feed to poll",
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
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
                        "default": "python-rss-trigger/1.0",
                        "description": "Custom User-Agent header",
                    }
                ],
            },
        ],
    }

    icon = "fa:rss"
    color = "orange-red"

    # ------------- Trigger (poll) -------------
    def trigger(self) -> List[List[NodeExecutionData]]:
        feed_url = self.get_node_parameter("feedUrl", 0, "").strip()
        if not feed_url:
            raise ValueError("Feed URL must be set")
        if not self._valid_url(feed_url):
            raise ValueError(f"Invalid feed URL: {feed_url}")

        options = self.get_node_parameter("options", 0, {}) or {}
        ignore_ssl = bool(options.get("ignoreSSL", False))
        user_agent = (options.get("userAgent") or "python-rss/1.0").strip()

        now_iso = self._utc_iso()
        last_item_date = self._prev_schedule_fire_ts()

        # Determine reference timestamp
        ref_ts = last_item_date or self._parse_date_to_ts(now_iso)

        entries = self._fetch_feed(feed_url, ignore_ssl, user_agent)
        if not entries:
            return [[NodeExecutionData(json_data={"status": "No entries found"})]]

        new_items: List[Dict[str, Any]] = []
        newest_ts = ref_ts

        for e in entries:
            iso = (
                e.get("isoDate")
                or e.get("published")
                or e.get("updated")
                or e.get("date")
            )
            if not iso:
                continue
            ets = self._parse_date_to_ts(iso)
            if ets > ref_ts:
                new_items.append(e)
            if ets > newest_ts:
                newest_ts = ets

        if not new_items:
            return [[]]

        out = [NodeExecutionData(json_data=item) for item in new_items]
        return [out]

    # ------------- Helpers -------------
    def _valid_url(self, url: str) -> bool:
        try:
            p = urlparse(url)
            return p.scheme in ("http", "https") and bool(p.netloc)
        except Exception:
            return False

    def _fetch_feed(self, url: str, ignore_ssl: bool, user_agent: str) -> List[Dict[str, Any]]:
        headers = {
            "User-Agent": user_agent,
            "Accept": "application/rss+xml, application/rdf+xml;q=0.8, application/atom+xml;q=0.6, application/xml;q=0.4, text/xml;q=0.4",
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

    def _parse_date_to_ts(self, iso_str: str) -> int:
        if not iso_str:
            return 0
        try:
            from dateutil import parser as du
            return int(du.parse(iso_str).timestamp())
        except Exception:
            try:
                return int(time.mktime(time.strptime(iso_str, "%a, %d %b %Y %H:%M:%S %z")))
            except Exception:
                return 0

    def _to_iso(self, ts: int) -> str:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    def _utc_iso(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
