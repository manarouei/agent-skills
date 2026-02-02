import requests
import base64
import email
import logging
import time
import zlib
import re
from urllib.parse import urlencode
from email.header import decode_header, make_header
from email.message import Message
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Optional, Any

from models import NodeExecutionData
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)


class GmailNode(BaseNode):
    """
    Gmail node for managing email operations
    """

    type = "gmail"
    version = 2

    description = {
        "displayName": "Gmail",
        "name": "gmail",
        "icon": "file:gmail.svg",
        "group": ["transform"],
        "description": "Consume the Gmail API",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True,
    }

    properties = {
        "parameters": [
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Resource",
                "options": [
                    {"name": "Message", "value": "message"},
                    {"name": "Label", "value": "label"},
                    {"name": "Draft", "value": "draft"},
                    {"name": "Thread", "value": "thread"},
                ],
                "default": "message",
                "description": "The resource to operate on",
            },
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Get Many", "value": "getAll"},
                    {"name": "Get", "value": "get"},
                    {"name": "Send", "value": "send"},
                    {"name": "Reply", "value": "reply"},
                    {"name": "Delete", "value": "delete"},
                    {"name": "Mark as Read", "value": "markAsRead"},
                    {"name": "Mark as Unread", "value": "markAsUnread"},
                    {"name": "Add Labels", "value": "addLabels"},
                    {"name": "Remove Labels", "value": "removeLabels"},
                ],
                "default": "getAll",
                "display_options": {"show": {"resource": ["message"]}},
            },
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Create", "value": "create"},
                    {"name": "Get", "value": "get"},
                    {"name": "Get Many", "value": "getAll"},
                    {"name": "Delete", "value": "delete"},
                ],
                "default": "getAll",
                "display_options": {"show": {"resource": ["draft"]}},
            },
            {
                "name": "draftId",
                "type": NodeParameterType.STRING,
                "display_name": "Draft ID",
                "default": "",
                "required": False,
                "description": "ID of the draft",
                "display_options": {"show": {"resource": ["draft"], "operation": ["get", "delete"]}},
            },
            # Common message params
            {
                "name": "messageId",
                "type": NodeParameterType.STRING,
                "display_name": "Message ID",
                "default": "",
                "required": False,
                "description": "ID of the message",
                "display_options": {"show": {"resource": ["message"], "operation": ["get", "reply", "delete", "markAsRead", "markAsUnread", "addLabels", "removeLabels"]}},
            },
            {
                "name": "returnAll",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Return All",
                "default": False,
                "description": "Whether to return all results",
                "display_options": {"show": {"resource": ["message", "draft"], "operation": ["getAll"]}},
            },
            {
                "name": "limit",
                "type": NodeParameterType.NUMBER,
                "display_name": "Limit",
                "default": 10,
                "description": "Max number of results",
                "display_options": {"show": {"resource": ["message", "draft"], "operation": ["getAll"], "returnAll": [False]}},
            },
            {
                "name": "query",
                "type": NodeParameterType.STRING,
                "display_name": "Query",
                "default": "",
                "description": "Gmail search query (e.g., is:unread, from:user@example.com)",
                "display_options": {"show": {"resource": ["message"], "operation": ["getAll"]}},
            },
            {
                "name": "includeSpamTrash",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Include Spam and Trash",
                "default": False,
                "description": "Include messages from spam and trash",
                "display_options": {"show": {"resource": ["message"], "operation": ["getAll"]}},
            },
            {
                "name": "simple",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Simplify",
                "default": True,
                "description": "Return simplified output (metadata) when true, parse raw MIME when false",
                "display_options": {"show": {"resource": ["message", "draft"], "operation": ["get", "getAll"]}},
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "default": {},
                "options": [
                    {
                        "name": "dataPropertyAttachmentsPrefixName",
                        "type": NodeParameterType.STRING,
                        "display_name": "Binary Property Prefix",
                        "default": "attachment_",
                        "description": "Prefix for binary attachment properties when simple=false",
                    }
                ],
                "display_options": {"show": {"resource": ["message", "draft"], "operation": ["get", "getAll"]}},
            },
            # Send/reply
            {
                "name": "to",
                "type": NodeParameterType.STRING,
                "display_name": "To",
                "default": "",
                "display_options": {"show": {"resource": ["message", "draft"], "operation": ["send", "create"]}},
            },
            {
                "name": "cc",
                "type": NodeParameterType.STRING,
                "display_name": "CC",
                "default": "",
                "display_options": {"show": {"resource": ["message", "draft"], "operation": ["send", "create"]}},
            },
            {
                "name": "bcc",
                "type": NodeParameterType.STRING,
                "display_name": "BCC",
                "default": "",
                "display_options": {"show": {"resource": ["message", "draft"], "operation": ["send", "create"]}},
            },
            {
                "name": "subject",
                "type": NodeParameterType.STRING,
                "display_name": "Subject",
                "default": "",
                "display_options": {"show": {"resource": ["message", "draft"], "operation": ["send", "reply", "create"]}},
            },
            {
                "name": "message",
                "type": NodeParameterType.STRING,
                "display_name": "Message",
                "default": "",
                "display_options": {"show": {"resource": ["message", "draft"], "operation": ["send", "reply", "create"]}},
            },
            {
                "name": "format",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Format",
                "options": [{"name": "HTML", "value": "html"}, {"name": "Text", "value": "text"}],
                "default": "html",
                "display_options": {"show": {"resource": ["message", "draft"], "operation": ["send", "reply", "create"]}},
            },
            {
                "name": "attachmentsBinaryProperties",
                "type": NodeParameterType.STRING,
                "display_name": "Attachments (Binary Properties)",
                "default": "",
                "description": "Comma-separated list of binary property names to add as attachments (e.g. 'attachment,attachment_1')",
                "display_options": {"show": {"resource": ["message", "draft"], "operation": ["send", "create"]}},
            },
        ],
        "credentials": [{"name": "gmailOAuth2", "required": True}],
    }

    icon = "gmail.svg"
    color = "#D44638"

    # ---------------- OAuth helpers ----------------
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
        """Refresh OAuth2 access token with proper invalid_grant handling"""
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

        response = requests.post(data["accessTokenUrl"], data=urlencode(token_data), headers=headers)
        
        if response.status_code != 200:
            try:
                err = response.json()
            except Exception:
                err = {"error": response.text}
            
            error_code = err.get("error", "")
            # Handle invalid_grant - user needs to reconnect
            if error_code == "invalid_grant":
                raise ValueError(f"OAuth token invalid (invalid_grant). User must reconnect their Gmail account.")
            
            raise Exception(f"Token refresh failed: {response.status_code} {err}")

        new_token_data = response.json()
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

    # ---------------- Execute ----------------
    def execute(self) -> List[List[NodeExecutionData]]:
        try:
            items = self.get_input_data() 
            # Handle empty input data case
            if not items:
                return [[]]

            out: List[NodeExecutionData] = []
            for i, _ in enumerate(items):
                try:
                    resource = self.get_node_parameter("resource", i, "message")
                    operation = self.get_node_parameter("operation", i, "getAll")

                    if resource == "message":
                        out.extend(self._exec_message(i, operation))
                    elif resource == "draft":
                        out.extend(self._exec_draft(i, operation))
                    else:
                        raise ValueError(f"Unsupported resource '{resource}'")

                except Exception as e:
                    out.append(
                        NodeExecutionData(
                            json_data={"error": str(e), "resource": resource, "operation": operation, "item_index": i},
                            binary_data=None,
                        )
                    )

            return [out]
        except Exception as e:
            return [[NodeExecutionData(json_data={"error": f"Gmail node error: {str(e)}"}, binary_data=None)]]

    # ---------------- Message ops ----------------
    def _exec_message(self, i: int, operation: str) -> List[NodeExecutionData]:
        access_token = self._get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        base = "https://gmail.googleapis.com/gmail/v1"

        if operation == "send":
            return self._send_message(i)

        if operation == "reply":
            return self._reply_message(i)

        if operation == "delete":
            msg_id = self.get_node_parameter("messageId", i, "")
            if not msg_id:
                raise ValueError("messageId is required")
            url = f"{base}/users/me/messages/{msg_id}"
            r = requests.delete(url, headers=headers, timeout=30)
            if r.status_code not in (200, 204):
                raise ValueError(f"Delete failed: {r.text}")
            return [NodeExecutionData(json_data={"success": True}, binary_data=None)]

        if operation in ("markAsRead", "markAsUnread", "addLabels", "removeLabels"):
            msg_id = self.get_node_parameter("messageId", i, "")
            if not msg_id:
                raise ValueError("messageId is required")
            body: Dict[str, Any] = {}
            if operation == "markAsRead":
                body = {"removeLabelIds": ["UNREAD"]}
            elif operation == "markAsUnread":
                body = {"addLabelIds": ["UNREAD"]}
            elif operation == "addLabels":
                labels = self.get_node_parameter("labelIds", i, []) or []
                body = {"addLabelIds": labels}
            elif operation == "removeLabels":
                labels = self.get_node_parameter("labelIds", i, []) or []
                body = {"removeLabelIds": labels}
            url = f"{base}/users/me/messages/{msg_id}/modify"
            r = requests.post(url, headers=headers, json=body, timeout=30)
            if r.status_code != 200:
                raise ValueError(f"Modify failed: {r.text}")
            return [NodeExecutionData(json_data={"success": True}, binary_data=None)]

        simple = bool(self.get_node_parameter("simple", i, True))
        options = self.get_node_parameter("options", i, {}) or {}
        attach_prefix = options.get("dataPropertyAttachmentsPrefixName", "attachment_") or "attachment_"

        if operation == "get":
            msg_id = self.get_node_parameter("messageId", i, "")
            if not msg_id:
                raise ValueError("messageId is required")

            if simple:
                # Use full to have payload.parts available
                qs = {"format": "full"}
                r = requests.get(f"{base}/users/me/messages/{msg_id}", headers=headers, params=qs, timeout=30)
                if r.status_code != 200:
                    raise ValueError(f"Get failed: {r.text}")
                simplified = self._simplify_output(r.json())
                return [NodeExecutionData(json_data=simplified, binary_data=None)]
            else:
                # raw mode + parse MIME and build parts
                qs = {"format": "raw"}
                r = requests.get(f"{base}/users/me/messages/{msg_id}", headers=headers, params=qs, timeout=30)
                if r.status_code != 200:
                    raise ValueError(f"Get failed: {r.text}")
                node_item = self._parse_raw_email(r.json(), attach_prefix)
                return [node_item]

        if operation == "getAll":
            return_all = bool(self.get_node_parameter("returnAll", i, False))
            limit = None if return_all else int(self.get_node_parameter("limit", i, 10))
            query = self.get_node_parameter("query", i, "")
            include_spam_trash = bool(self.get_node_parameter("includeSpamTrash", i, False))

            params: Dict[str, Any] = {}
            if query:
                params["q"] = query
            if include_spam_trash:
                params["includeSpamTrash"] = "true"
            if not return_all and limit:
                params["maxResults"] = min(limit, 500)

            messages: List[Dict[str, Any]] = []
            page_token: Optional[str] = None
            while True:
                if page_token:
                    params["pageToken"] = page_token
                r = requests.get(f"{base}/users/me/messages", headers=headers, params=params, timeout=30)
                if r.status_code != 200:
                    raise ValueError(f"List failed: {r.text}")
                data = r.json() or {}
                messages.extend(data.get("messages", []) or [])
                page_token = data.get("nextPageToken")
                if not return_all or not page_token:
                    break
                if limit and len(messages) >= limit:
                    break

            if not messages:
                return []

            # Cap list to limit if needed
            if limit:
                messages = messages[:limit]

            results: List[NodeExecutionData] = []
            if simple:
                # Use full so simplified output can embed raw.payload.parts directly
                qs = {"format": "full"}
                for m in messages:
                    r = requests.get(f"{base}/users/me/messages/{m['id']}", headers=headers, params=qs, timeout=30)
                    if r.status_code != 200:
                        logger.warning(f"Get full failed for {m['id']}: {r.text}")
                        continue
                    simplified = self._simplify_output(r.json())
                    results.append(NodeExecutionData(json_data=simplified, binary_data=None))
            else:
                qs = {"format": "raw"}
                for m in messages:
                    r = requests.get(f"{base}/users/me/messages/{m['id']}", headers=headers, params=qs, timeout=30)
                    if r.status_code != 200:
                        logger.warning(f"Get raw failed for {m['id']}: {r.text}")
                        continue
                    node_item = self._parse_raw_email(r.json(), attach_prefix)
                    results.append(node_item)

            return results

        raise ValueError(f"Unsupported operation '{operation}'")

    def _send_message(self, i: int) -> List[NodeExecutionData]:
        access_token = self._get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        base = "https://gmail.googleapis.com/gmail/v1"

        to = self.get_node_parameter("to", i, "")
        subject = self.get_node_parameter("subject", i, "")
        body = self.get_node_parameter("message", i, "")
        cc = self.get_node_parameter("cc", i, "")
        bcc = self.get_node_parameter("bcc", i, "")
        fmt = self.get_node_parameter("format", i, "html")
        attachments_props = self._parse_csv(self.get_node_parameter("attachmentsBinaryProperties", i, ""))

        if not to or not subject or not body:
            raise ValueError("To, subject, and message are required")

        # Build message
        has_attachments = bool(attachments_props)
        if has_attachments:
            root = MIMEMultipart("mixed")
            if fmt == "html":
                alt = MIMEMultipart("alternative")
                alt.attach(MIMEText(body, "html"))
                root.attach(alt)
            else:
                root.attach(MIMEText(body, "plain"))
            msg = root
        else:
            if fmt == "html":
                msg = MIMEMultipart("alternative")
                msg.attach(MIMEText(body, "html"))
            else:
                msg = MIMEText(body, "plain")

        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc

        # Attach binary files from current item
        if has_attachments:
            input_items = self.get_input_data() or []
            current = input_items[i] if 0 <= i < len(input_items) else None
            bin_map: Dict[str, Any] = getattr(current, "binary_data", None) if current else None
            if not bin_map:
                logger.warning("Send with attachments requested but input item has no binary_data")
            else:
                for prop in attachments_props:
                    entry = bin_map.get(prop)
                    if not entry or not isinstance(entry, dict):
                        logger.warning(f"Binary property '{prop}' not found on input item")
                        continue
                    payload = self._binary_entry_to_bytes(entry)
                    if not payload:
                        logger.warning(f"Binary property '{prop}' has no payload")
                        continue
                    file_name = entry.get("fileName") or prop
                    mime_type = entry.get("mimeType") or "application/octet-stream"
                    maintype, _, subtype = mime_type.partition("/")
                    try:
                        part = MIMEBase(maintype, subtype or "octet-stream")
                    except Exception:
                        part = MIMEBase("application", "octet-stream")
                    part.set_payload(payload)
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", "attachment", filename=file_name)
                    msg.attach(part)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        r = requests.post(f"{base}/users/me/messages/send", headers=headers, json={"raw": raw}, timeout=30)
        if r.status_code != 200:
            raise ValueError(f"Send failed: {r.text}")
        data = r.json()
        return [NodeExecutionData(json_data={"id": data.get("id"), "threadId": data.get("threadId"), "status": "sent", "to": to, "subject": subject}, binary_data=None)]
    
    def _reply_message(self, i: int) -> List[NodeExecutionData]:
        access_token = self._get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        base = "https://gmail.googleapis.com/gmail/v1"

        msg_id = self.get_node_parameter("messageId", i, "")
        subject = self.get_node_parameter("subject", i, "")
        body = self.get_node_parameter("message", i, "")
        fmt = self.get_node_parameter("format", i, "html")
        if not msg_id or not subject or not body:
            raise ValueError("messageId, subject, and message are required")

        # fetch original
        r = requests.get(f"{base}/users/me/messages/{msg_id}", headers=headers, timeout=30)
        if r.status_code != 200:
            raise ValueError(f"Original message fetch failed: {r.text}")
        orig = r.json()
        thread_id = orig.get("threadId")
        headers_list = (orig.get("payload") or {}).get("headers", []) or []
        from_header = ""
        for h in headers_list:
            if (h.get("name") or "").lower() == "from":
                from_header = h.get("value") or ""
                break

        msg_obj: MIMEMultipart | MIMEText
        if fmt == "html":
            msg_obj = MIMEMultipart("alternative")
            msg_obj.attach(MIMEText(body, "html"))
        else:
            msg_obj = MIMEText(body, "plain")
        msg_obj["To"] = from_header
        msg_obj["Subject"] = f"Re: {subject}" if not subject.lower().startswith("re:") else subject
        msg_obj["In-Reply-To"] = msg_id
        msg_obj["References"] = msg_id

        raw = base64.urlsafe_b64encode(msg_obj.as_bytes()).decode()
        payload = {"raw": raw, "threadId": thread_id}
        send = requests.post(f"{base}/users/me/messages/send", headers=headers, json=payload, timeout=30)
        if send.status_code != 200:
            raise ValueError(f"Reply failed: {send.text}")
        data = send.json()
        return [NodeExecutionData(json_data={"id": data.get("id"), "threadId": data.get("threadId"), "status": "sent", "replyTo": msg_id, "to": from_header}, binary_data=None)]

    def _simplify_output(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        payload = msg.get("payload") or {}
        headers = payload.get("headers") or []
        hmap: Dict[str, str] = {}
        for h in headers:
            name = (h.get("name") or "").lower()
            if name in ("from", "to", "cc", "bcc", "subject", "date", "message-id"):
                hmap[name] = h.get("value") or ""

        body_text = ""
        # Prefer text/plain from parts if present
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
            # Include full response (has payload.parts) under raw
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
        """
        - Decode message.raw (base64url) to RFC822
        - Walk MIME parts, collect text/html and attachments
        - Return NodeExecutionData with json (headers, body, etc.) and binary (attachments)
        - Also attach a Gmail-like 'raw' object with payload.parts rebuilt from MIME
        """
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

            # Inline content
            if ctype == "text/plain" and not text_body:
                try:
                    text_body = (part.get_payload(decode=True) or b"").decode(part.get_content_charset() or "utf-8", errors="replace")
                except Exception:
                    text_body = ""
            elif ctype == "text/html" and not html_body:
                try:
                    html_body = (part.get_payload(decode=True) or b"").decode(part.get_content_charset() or "utf-8", errors="replace")
                except Exception:
                    html_body = ""

        # Prefer text, else html
        body = text_body or html_body

        # Build Gmail-like raw object with payload.parts (from MIME)
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
        """
        Build an object similar to Gmail's 'full' response but from a raw MIME message.
        """
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
        for name, value in list(part_or_msg.items()):
            try:
                decoded = str(make_header(decode_header(re.sub(r"\r?\n[ \t]+", " ", value).strip()))) if value else ""
            except Exception:
                decoded = value or ""
            out.append({"name": name, "value": decoded})
        return out

    def _b64_to_urlsafe(self, data: bytes) -> str:
        s = base64.urlsafe_b64encode(data).decode()
        return s.rstrip("=")

    def _estimate_message_size(self, msg: Message) -> int:
        try:
            return len(msg.as_bytes())
        except Exception:
            return 0


    def _simplify_draft_output(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        msg = draft.get("message") or {}
        simplified = self._simplify_output(msg)
        simplified["draftId"] = draft.get("id")
        return simplified

    # ---------------- Draft ops ----------------
    def _exec_draft(self, i: int, operation: str) -> List[NodeExecutionData]:
        access_token = self._get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        base = "https://gmail.googleapis.com/gmail/v1"

        if operation == "create":
            return self._create_draft(i)

        if operation == "delete":
            draft_id = self.get_node_parameter("draftId", i, "")
            if not draft_id:
                raise ValueError("draftId is required")
            url = f"{base}/users/me/drafts/{draft_id}"
            r = requests.delete(url, headers=headers, timeout=30)
            if r.status_code not in (200, 204):
                raise ValueError(f"Delete draft failed: {r.text}")
            return [NodeExecutionData(json_data={"success": True}, binary_data=None)]

        simple = bool(self.get_node_parameter("simple", i, True))
        options = self.get_node_parameter("options", i, {}) or {}
        attach_prefix = options.get("dataPropertyAttachmentsPrefixName", "attachment_") or "attachment_"

        if operation == "get":
            draft_id = self.get_node_parameter("draftId", i, "")
            if not draft_id:
                raise ValueError("draftId is required")

            fmt = "full" if simple else "raw"
            r = requests.get(f"{base}/users/me/drafts/{draft_id}", headers=headers, params={"format": fmt}, timeout=30)
            if r.status_code != 200:
                raise ValueError(f"Get draft failed: {r.text}")
            draft = r.json() or {}

            if simple:
                simplified = self._simplify_draft_output(draft)
                return [NodeExecutionData(json_data=simplified, binary_data=None)]
            else:
                msg_obj = draft.get("message") or {}
                node_item = self._parse_raw_email(msg_obj, attach_prefix)
                jd = getattr(node_item, "json_data", {}) or {}
                jd["draftId"] = draft.get("id")
                return [NodeExecutionData(json_data=jd, binary_data=getattr(node_item, "binary_data", None))]

        if operation == "getAll":
            return_all = bool(self.get_node_parameter("returnAll", i, False))
            limit = None if return_all else int(self.get_node_parameter("limit", i, 10))

            params: Dict[str, Any] = {}
            if not return_all and limit:
                params["maxResults"] = min(limit, 500)

            drafts: List[Dict[str, Any]] = []
            page_token: Optional[str] = None
            while True:
                if page_token:
                    params["pageToken"] = page_token
                r = requests.get(f"{base}/users/me/drafts", headers=headers, params=params, timeout=30)
                if r.status_code != 200:
                    raise ValueError(f"List drafts failed: {r.text}")
                data = r.json() or {}
                drafts.extend(data.get("drafts", []) or [])
                page_token = data.get("nextPageToken")
                if not return_all or not page_token:
                    break
                if limit and len(drafts) >= limit:
                    break

            if not drafts:
                return []

            if limit:
                drafts = drafts[:limit]

            results: List[NodeExecutionData] = []
            if simple:
                for d in drafts:
                    did = d.get("id")
                    if not did:
                        continue
                    r = requests.get(f"{base}/users/me/drafts/{did}", headers=headers, params={"format": "full"}, timeout=30)
                    if r.status_code != 200:
                        logger.warning(f"Get draft full failed for {did}: {r.text}")
                        continue
                    simplified = self._simplify_draft_output(r.json() or {})
                    results.append(NodeExecutionData(json_data=simplified, binary_data=None))
            else:
                for d in drafts:
                    did = d.get("id")
                    if not did:
                        continue
                    r = requests.get(f"{base}/users/me/drafts/{did}", headers=headers, params={"format": "raw"}, timeout=30)
                    if r.status_code != 200:
                        logger.warning(f"Get draft raw failed for {did}: {r.text}")
                        continue
                    draft = r.json() or {}
                    node_item = self._parse_raw_email((draft.get("message") or {}), attach_prefix)
                    jd = getattr(node_item, "json_data", {}) or {}
                    jd["draftId"] = draft.get("id")
                    results.append(NodeExecutionData(json_data=jd, binary_data=getattr(node_item, "binary_data", None)))

            return results

        raise ValueError(f"Unsupported draft operation '{operation}'")
    



    def _create_draft(self, i: int) -> List[NodeExecutionData]:
        access_token = self._get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        base = "https://gmail.googleapis.com/gmail/v1"

        to = self.get_node_parameter("to", i, "")
        subject = self.get_node_parameter("subject", i, "")
        body = self.get_node_parameter("message", i, "")
        cc = self.get_node_parameter("cc", i, "")
        bcc = self.get_node_parameter("bcc", i, "")
        fmt = self.get_node_parameter("format", i, "html")
        attachments_props = self._parse_csv(self.get_node_parameter("attachmentsBinaryProperties", i, ""))

        has_attachments = bool(attachments_props)
        if has_attachments:
            root = MIMEMultipart("mixed")
            if fmt == "html":
                alt = MIMEMultipart("alternative")
                alt.attach(MIMEText(body or "", "html"))
                root.attach(alt)
            else:
                root.attach(MIMEText(body or "", "plain"))
            msg = root
        else:
            if fmt == "html":
                msg = MIMEMultipart("alternative")
                msg.attach(MIMEText(body or "", "html"))
            else:
                msg = MIMEText(body or "", "plain")

        if to:
            msg["To"] = to
        if subject:
            msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc

        if has_attachments:
            input_items = self.get_input_data() or []
            current = input_items[i] if 0 <= i < len(input_items) else None
            bin_map: Dict[str, Any] = getattr(current, "binary_data", None) if current else None
            if not bin_map:
                logger.warning("Draft create with attachments requested but input item has no binary_data")
            else:
                for prop in attachments_props:
                    entry = bin_map.get(prop)
                    if not entry or not isinstance(entry, dict):
                        logger.warning(f"Binary property '{prop}' not found on input item")
                        continue
                    payload = self._binary_entry_to_bytes(entry)
                    if not payload:
                        logger.warning(f"Binary property '{prop}' has no payload")
                        continue
                    file_name = entry.get("fileName") or prop
                    mime_type = entry.get("mimeType") or "application/octet-stream"
                    maintype, _, subtype = mime_type.partition("/")
                    try:
                        part = MIMEBase(maintype, subtype or "octet-stream")
                    except Exception:
                        part = MIMEBase("application", "octet-stream")
                    part.set_payload(payload)
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", "attachment", filename=file_name)
                    msg.attach(part)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        payload = {"message": {"raw": raw}}
        r = requests.post(f"{base}/users/me/drafts", headers=headers, json=payload, timeout=30)
        if r.status_code != 200:
            raise ValueError(f"Create draft failed: {r.text}")
        data = r.json() or {}
        return [
            NodeExecutionData(
                json_data={
                    "id": data.get("id"),
                    "status": "draft_created",
                    "to": to,
                    "subject": subject,
                    "message": body,
                    "threadId": ((data.get("message") or {}).get("threadId")),
                },
                binary_data=None,
            )
        ]


