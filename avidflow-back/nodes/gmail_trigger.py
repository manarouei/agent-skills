import base64
import email
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from email.header import decode_header, make_header
from email.message import Message

from models import NodeExecutionData
from .base import NodeParameterType
from .schedule import ScheduleNode

logger = logging.getLogger(__name__)



class GmailTriggerNode(ScheduleNode):
    """
    Gmail Trigger node (polling) analogous to n8n GmailTrigger.
    - Filters: includeSpamTrash, includeDrafts, labelIds, q, readStatus, sender
    - Simple mode: fetch metadata, then simplify
    - Raw mode: fetch raw, parse MIME, optionally include attachments into binary
    - Duplicate control using lastTimeChecked and possibleDuplicates (per workflow+node)
    """

    type = "gmailTrigger"
    version = 2

    description = {
        "displayName": "Gmail Trigger",
        "name": "gmailTrigger",
        "icon": "file:gmail.svg",
        "group": ["trigger", "schedule"],
        "description": "Fetches emails from Gmail and starts the workflow on specified polling intervals.",
        "defaults": {"name": "Gmail Trigger"},
        "inputs": [],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "polling": True,
    }

    properties = {
        "parameters": ScheduleNode.schedule_parameters() + [
            {
                "name": "simple",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Simplify",
                "default": True,
                "description": "Whether to return a simplified version of the response instead of the raw data",
            },
            {
                "name": "filters",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Filters",
                "placeholder": "Add Filter",
                "default": {},
                "options": [
                    {
                        "name": "includeSpamTrash",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Include Spam and Trash",
                        "default": False,
                        "description": "Whether to include messages from SPAM and TRASH in the results",
                    },
                    {
                        "name": "includeDrafts",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Include Drafts",
                        "default": False,
                        "description": "Whether to include email drafts in the results",
                    },
                    {
                        "name": "labelIds",
                        "type": NodeParameterType.STRING,
                        "display_name": "Label Names or IDs",
                        "default": "",
                        "description": "Comma-separated list of label IDs for filtering emails",
                    },
                    {
                        "name": "q",
                        "type": NodeParameterType.STRING,
                        "display_name": "Search",
                        "default": "",
                        "placeholder": "has:attachment",
                        "description": "Only return messages matching the specified query",
                    },
                    {
                        "name": "readStatus",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Read Status",
                        "default": "unread",
                        "options": [
                            {"name": "Unread and read emails", "value": "both"},
                            {"name": "Unread emails only", "value": "unread"},
                            {"name": "Read emails only", "value": "read"},
                        ],
                        "description": "Filter emails by whether they have been read or not",
                    },
                    {
                        "name": "sender",
                        "type": NodeParameterType.STRING,
                        "display_name": "Sender",
                        "default": "",
                        "description": "Sender name or email to filter by",
                    },
                ],
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "placeholder": "Add option",
                "default": {},
                "display_options": {"hide": {"simple": [True]}},
                "options": [
                    {
                        "name": "dataPropertyAttachmentsPrefixName",
                        "type": NodeParameterType.STRING,
                        "display_name": "Attachment Prefix",
                        "default": "attachment_",
                        "description": "Prefix for binary properties when downloading attachments",
                    },
                    {
                        "name": "downloadAttachments",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Download Attachments",
                        "default": False,
                        "description": "Whether the email's attachments will be downloaded",
                    },
                ],
            },
        ],
        "credentials": [{"name": "gmailOAuth2", "required": True}],
    }

    icon = "gmail.svg"
    color = "#D44638"

    # ---------------- OAuth helpers (reused from Gmail node) ----------------
    @staticmethod
    def has_access_token(credentials_data: Dict[str, Any]) -> bool:
        if "data" in credentials_data:
            credentials_data = credentials_data["data"]
        oauth_token_data = credentials_data.get("oauthTokenData")
        return isinstance(oauth_token_data, dict) and "access_token" in oauth_token_data

    def get_credential_type(self):
        return self.properties["credentials"][0]["name"]

    def _is_token_expired(self, oauth_data: Dict[str, Any]) -> bool:
        if "expires_at" not in oauth_data:
            return False
        return time.time() > (oauth_data["expires_at"] - 30)

    def refresh_token(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        from urllib.parse import urlencode

        if not data.get("oauthTokenData") or not data["oauthTokenData"].get("refresh_token"):
            raise ValueError("No refresh token available")

        oauth_data = data["oauthTokenData"]
        token_data = {"grant_type": "refresh_token", "refresh_token": oauth_data["refresh_token"]}
        headers: Dict[str, str] = {}

        if data.get("authentication", "header") == "header":
            auth_header = base64.b64encode(f"{data['clientId']}:{data['clientSecret']}".encode()).decode()
            headers["Authorization"] = f"Basic {auth_header}"
        else:
            token_data.update({"client_id": data["clientId"], "client_secret": data["clientSecret"]})
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        r = requests.post(data["accessTokenUrl"], data=urlencode(token_data), headers=headers, timeout=30)
        if r.status_code != 200:
            try:
                err = r.json()
            except Exception:
                err = {"error": r.text}
            raise Exception(f"Token refresh failed: {r.status_code} {err}")

        new_token_data = r.json()
        updated = oauth_data.copy()
        updated["access_token"] = new_token_data["access_token"]
        if "expires_in" in new_token_data:
            updated["expires_at"] = time.time() + new_token_data["expires_in"]
        if "refresh_token" in new_token_data:
            updated["refresh_token"] = new_token_data["refresh_token"]
        for k, v in new_token_data.items():
            if k not in ("access_token", "expires_in", "refresh_token"):
                updated[k] = v

        data["oauthTokenData"] = updated
        self.update_credentials(self.get_credential_type(), data)
        return data

    def _get_access_token(self) -> str:
        creds = self.get_credentials("gmailOAuth2")
        if not creds or not self.has_access_token(creds):
            raise ValueError("Gmail OAuth2 credentials missing")
        oauth = creds.get("oauthTokenData", {})
        if self._is_token_expired(oauth):
            creds = self.refresh_token(creds) or creds
        return creds["oauthTokenData"]["access_token"]

    # ---------------- Trigger (poll) ----------------
    def trigger(self) -> List[List[NodeExecutionData]]:
        base = "https://gmail.googleapis.com/gmail/v1"
        headers = {"Authorization": f"Bearer {self._get_access_token()}"}

        simple = bool(self.get_node_parameter("simple", 0, True))
        filters = self.get_node_parameter("filters", 0, {}) or {}
        options = self.get_node_parameter("options", 0, {}) or {}

        include_spam_trash = bool(filters.get("includeSpamTrash", False))
        include_drafts = bool(filters.get("includeDrafts", False))
        label_ids = self._parse_csv(filters.get("labelIds", ""))
        sender = (filters.get("sender") or "").strip()
        search_q = (filters.get("q") or "").strip()
        read_status = (filters.get("readStatus") or "").lower()

        # Build list parameters
        qs: Dict[str, Any] = {}
        if include_spam_trash:
            qs["includeSpamTrash"] = True
        if label_ids and isinstance(label_ids, list):
            qs["labelIds"] = label_ids

        # Build Gmail search query (best-effort)
        q_parts: List[str] = []
        if search_q:
            q_parts.append(search_q)
        if sender:
            q_parts.append(f'from:{sender}')
        if read_status == "unread":
            q_parts.append("is:unread")
        elif read_status == "read":
            q_parts.append("-is:unread")

        now_sec = int(datetime.now(timezone.utc).timestamp())
        start_after = self._prev_schedule_fire_ts()
        if start_after:
            q_parts.append(f"after:{start_after}")

        if q_parts:
            qs["q"] = " ".join(q_parts)

        # List messages
        r = requests.get(f"{base}/users/me/messages", headers=headers, params=qs, timeout=30)
        if r.status_code != 200:
            raise ValueError(f"GmailTrigger list failed: {r.text}")

        data = r.json() or {}
        ids = data.get("messages", []) or []
        if not ids:
            return [[NodeExecutionData(json_data={'status': 'no_messages'})]]

        # Fetch details for each message
        fetch_qs: Dict[str, Any] = {}
        if simple:
            fetch_qs["format"] = "metadata"
            fetch_qs["metadataHeaders"] = ["From", "To", "Cc", "Bcc", "Subject"]
        else:
            fetch_qs["format"] = "raw"

        results: List[NodeExecutionData] = []

        attach_prefix = options.get("dataPropertyAttachmentsPrefixName", "attachment_") or "attachment_"
        for msg in ids:
            mid = msg.get("id")
            if not mid:
                continue
            rm = requests.get(f"{base}/users/me/messages/{mid}", headers=headers, params=fetch_qs, timeout=30)
            if rm.status_code != 200:
                logger.warning(f"GmailTrigger get failed for {mid}: {rm.text}")
                continue
            full = rm.json()

            # Skip drafts if requested
            if not include_drafts and isinstance(full.get("labelIds"), list) and "DRAFT" in full["labelIds"]:
                continue

            if simple:
                # Keep full Gmail 'Message' json; will simplify after
                results.append(NodeExecutionData(json_data=full, binary_data=None))
            else:
                # Parse raw, collect attachments into binary
                parsed = self._parse_raw_email(full, attach_prefix)
                if not options.get("downloadAttachments", False):
                    # Drop binary if not requested
                    parsed.binary_data = None
                results.append(parsed)

        if not results:
            return [[]]

        # Simplify if needed
        if simple:
            simplified_items: List[NodeExecutionData] = []
            for item in results:
                simplified_items.append(NodeExecutionData(json_data=self._simplify_output(item.json_data), binary_data=None))
            results = simplified_items

        # Duplicate filtering and state update
        emails_with_invalid_date: set[str] = set()

        def email_date_sec(email_json: Dict[str, Any]) -> int:
            # internalDate is ms since epoch
            if email_json.get("internalDate"):
                try:
                    return int(int(email_json["internalDate"]) / 1000)
                except Exception:
                    pass
            # fallback: headers date (RFC822)
            date_str = None
            if "date" in email_json:
                date_str = email_json.get("date")
            elif "headers" in email_json and isinstance(email_json["headers"], dict):
                date_str = email_json["headers"].get("date")

            if date_str:
                try:
                    return int(datetime.strptime(str(date_str), "%a, %d %b %Y %H:%M:%S %z").timestamp())
                except Exception:
                    pass

            # If cannot parse, mark invalid -> use startAfter
            if email_json.get("id"):
                emails_with_invalid_date.add(email_json["id"])
            return int(start_after or now_sec)

        last_email_date = 0
        for item in results:
            ts = email_date_sec(item.json_data or {})
            if ts > last_email_date:
                last_email_date = ts

        return [results]

    # ---------------- Simplify and raw parsing helpers (same as Gmail node) ----------------
    def _simplify_output(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        payload = msg.get("payload") or {}
        headers = payload.get("headers") or []
        hmap: Dict[str, str] = {}
        for h in headers:
            name = (h.get("name") or "").lower()
            if name in ("from", "to", "cc", "bcc", "subject", "date", "message-id"):
                hmap[name] = h.get("value") or ""

        body_text = ""
        # metadata mode won't contain parts; body likely empty, which matches n8n behavior
        if "parts" in payload and isinstance(payload["parts"], list):
            for p in payload["parts"]:
                if (p.get("mimeType") or "").lower() == "text/plain":
                    data = ((p.get("body") or {}).get("data")) or ""
                    if data:
                        try:
                            body_text = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                            break
                        except Exception:
                            pass
        if not body_text:
            data = ((payload.get("body") or {}).get("data")) or ""
            if data:
                try:
                    body_text = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                except Exception:
                    body_text = ""

        return {
            "id": msg.get("id"),
            "threadId": msg.get("threadId"),
            "snippet": msg.get("snippet", ""),
            "internalDate": msg.get("internalDate"),
            "labelIds": msg.get("labelIds", []),
            "from": hmap.get("from", ""),
            "to": hmap.get("to", ""),
            "cc": hmap.get("cc", ""),
            "subject": hmap.get("subject", ""),
            "date": hmap.get("date", ""),
            "messageId": hmap.get("message-id", ""),
            "body": body_text,
            "mimeType": (payload.get("mimeType") or ""),
            # Preserve Gmail payload under raw for parity
            "raw": {
                "id": msg.get("id"),
                "threadId": msg.get("threadId"),
                "labelIds": msg.get("labelIds", []),
                "snippet": msg.get("snippet", ""),
                "payload": payload,
                "sizeEstimate": msg.get("sizeEstimate"),
                "historyId": msg.get("historyId"),
                "internalDate": msg.get("internalDate"),
            },
        }

    def _parse_raw_email(self, raw_response: Dict[str, Any], prefix: str) -> NodeExecutionData:
        raw_b64url = raw_response.get("raw") or ""
        msg_id = raw_response.get("id")
        thread_id = raw_response.get("threadId")
        snippet = raw_response.get("snippet", "")
        label_ids = raw_response.get("labelIds", [])

        if not raw_b64url:
            simplified = self._simplify_output(raw_response)
            return NodeExecutionData(json_data=simplified, binary_data=None)

        # Decode base64url to bytes
        raw_b64 = raw_b64url.replace("-", "+").replace("_", "/")
        pad = len(raw_b64) % 4
        if pad:
            raw_b64 += "=" * (4 - pad)
        try:
            raw_bytes = base64.b64decode(raw_b64)
        except Exception as e:
            logger.warning(f"Failed to decode raw email: {e}")
            simplified = self._simplify_output(raw_response)
            return NodeExecutionData(json_data=simplified, binary_data=None)

        msg: Message = email.message_from_bytes(raw_bytes)

        headers_map: Dict[str, str] = {}
        for key in ("From", "To", "Cc", "Bcc", "Subject", "Date", "Message-ID"):
            val = msg.get(key, "")
            try:
                if key.lower() == "subject":
                    decoded = str(make_header(decode_header(val))) if val else ""
                    headers_map[key.lower()] = decoded
                else:
                    headers_map[key.lower()] = val or ""
            except Exception:
                headers_map[key.lower()] = val or ""

        text_body = ""
        html_body = ""
        binary: Dict[str, Any] = {}
        attach_index = 0

        for part in msg.walk():
            ctype = part.get_content_type() or "application/octet-stream"
            disp = (part.get("Content-Disposition") or "").lower()
            filename = part.get_filename()
            if filename:
                try:
                    filename = str(make_header(decode_header(filename)))
                except Exception:
                    pass

            if filename or "attachment" in disp:
                payload = part.get_payload(decode=True) or b""
                if not payload:
                    continue
                b64 = base64.b64encode(payload).decode()
                key = f"{prefix}{attach_index}"
                ext = ""
                if filename and "." in filename:
                    ext = filename.rsplit(".", 1)[-1].lower()
                binary[key] = {
                    "data": self.compress_data(b64),
                    "mimeType": ctype,
                    "fileName": filename or f"attachment_{attach_index}",
                    "fileExtension": ext or "",
                    "size": len(payload),
                }
                attach_index += 1
                continue

            if ctype == "text/plain" and not text_body:
                try:
                    text_body = (part.get_payload(decode=True) or b"").decode(
                        part.get_content_charset() or "utf-8", errors="replace"
                    )
                except Exception:
                    text_body = ""
            elif ctype == "text/html" and not html_body:
                try:
                    html_body = (part.get_payload(decode=True) or b"").decode(
                        part.get_content_charset() or "utf-8", errors="replace"
                    )
                except Exception:
                    html_body = ""

        body = text_body or html_body

        raw_obj = self._build_raw_payload_object(raw_response, parsed_message=msg)

        json_out = {
            "id": msg_id,
            "threadId": thread_id,
            "snippet": snippet,
            "internalDate": raw_response.get("internalDate"),
            "labelIds": label_ids,
            "from": headers_map.get("from", ""),
            "to": headers_map.get("to", ""),
            "cc": headers_map.get("cc", ""),
            "subject": headers_map.get("subject", ""),
            "date": headers_map.get("date", ""),
            "messageId": headers_map.get("message-id", ""),
            "body": body,
            "mimeType": msg.get_content_type(),
            "raw": raw_obj,
        }

        return NodeExecutionData(json_data=json_out, binary_data=binary or None)

    def _build_raw_payload_object(self, raw_response: Dict[str, Any], parsed_message: Optional[Message] = None) -> Optional[Dict[str, Any]]:
        try:
            msg_id = raw_response.get("id")
            thread_id = raw_response.get("threadId")
            label_ids = raw_response.get("labelIds", [])
            snippet = raw_response.get("snippet")
            history_id = raw_response.get("historyId")
            internal_date = raw_response.get("internalDate")

            msg: Message
            if parsed_message is not None:
                msg = parsed_message
            else:
                raw_b64url = raw_response.get("raw") or ""
                if not raw_b64url:
                    return None
                raw_b64 = raw_b64url.replace("-", "+").replace("_", "/")
                pad = len(raw_b64) % 4
                if pad:
                    raw_b64 += "=" * (4 - pad)
                raw_bytes = base64.b64decode(raw_b64)
                msg = email.message_from_bytes(raw_bytes)

            payload = self._build_gmail_payload_from_mime(msg)
            return {
                "id": msg_id,
                "threadId": thread_id,
                "labelIds": label_ids,
                "snippet": snippet,
                "payload": payload,
                "sizeEstimate": self._estimate_message_size(msg),
                "historyId": history_id,
                "internalDate": internal_date,
            }
        except Exception as e:
            logger.warning(f"Failed to build raw payload object: {e}")
            return None

    def _build_gmail_payload_from_mime(self, msg: Message) -> Dict[str, Any]:
        return self._build_part_from_mime(msg, part_id="")

    def _build_part_from_mime(self, part: Message, part_id: str) -> Dict[str, Any]:
        mime_type = part.get_content_type() or "application/octet-stream"
        filename = part.get_filename()
        if filename:
            try:
                filename = str(make_header(decode_header(filename)))
            except Exception:
                pass

        node: Dict[str, Any] = {
            "partId": part_id,
            "mimeType": mime_type,
            "filename": filename or "",
            "headers": self._headers_list(part),
            "body": {"size": 0},
        }

        if part.is_multipart():
            children = []
            for idx, child in enumerate(part.get_payload() or []):
                child_id = str(idx) if part_id == "" else f"{part_id}.{idx}"
                children.append(self._build_part_from_mime(child, child_id))
            if children:
                node["parts"] = children
        else:
            payload = part.get_payload(decode=True) or b""
            node["body"]["size"] = len(payload)

        return node

    def _headers_list(self, part_or_msg: Message) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        import re
        for name, value in list(part_or_msg.items()):
            try:
                raw = value if isinstance(value, str) else str(value or "")
                raw = re.sub(r"\r?\n[ \t]+", " ", raw).strip()
                decoded = str(make_header(decode_header(raw))) if raw else ""
            except Exception:
                decoded = raw if "raw" in locals() else (value or "")
            out.append({"name": name, "value": decoded})
        return out

    def _estimate_message_size(self, msg: Message) -> int:
        try:
            return len(msg.as_bytes())
        except Exception:
            return 0
