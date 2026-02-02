# ======================= Utilities & Normalization =======================
from __future__ import annotations
from typing import Callable, Dict, List, Optional, Any, Tuple, Union
import logging
from zoneinfo import ZoneInfo
from nodes import googleCalendar
import requests

logger = logging.getLogger(__name__)

_base_url = "https://www.googleapis.com/calendar/v3"
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
    # ======================= Utilities & Normalization =======================
# def _extract_text_content(doc_data: Dict[str, Any]) -> str:
#     """Extract plain text content from Google Docs document"""
#     try:
#         body = doc_data.get("body", {})
#         content = body.get("content", [])
        
#         text_parts = []
        
#         for element in content:
#             if "paragraph" in element:
#                 paragraph = element["paragraph"]
#                 paragraph_elements = paragraph.get("elements", [])
                
#                 for para_element in paragraph_elements:
#                     if "textRun" in para_element:
#                         text_run = para_element["textRun"]
#                         content_text = text_run.get("content", "")
#                         text_parts.append(content_text)
            
#             elif "table" in element:
#                 table = element["table"]
#                 table_rows = table.get("tableRows", [])
                
#                 for row in table_rows:
#                     table_cells = row.get("tableCells", [])
#                     for cell in table_cells:
#                         cell_content = cell.get("content", [])
#                         for cell_element in cell_content:
#                             if "paragraph" in cell_element:
#                                 paragraph = cell_element["paragraph"]
#                                 paragraph_elements = paragraph.get("elements", [])
                                
#                                 for para_element in paragraph_elements:
#                                     if "textRun" in para_element:
#                                         text_run = para_element["textRun"]
#                                         content_text = text_run.get("content", "")
#                                         text_parts.append(content_text)
#                     text_parts.append("\t")  # Tab between cells
#                 text_parts.append("\n")  # New line between rows
        
#         return "".join(text_parts)
        
#     except Exception as e:
#         logger.warning(f"Error extracting text content: {str(e)}")
#         return ""

def inside_window(ev: Dict[str, Any], time_min: Optional[datetime], time_max: Optional[datetime]) -> bool:
    if not ev.get("recurrence"):
        return True
    created = ev.get("created")
    if not created:
        return True
    if time_min and created < time_min:
        return False
    if time_max and created > time_max:
        return False
    return True





def timezone_convert(dt_str: str, target_tz: str, fallback_tz: str = "UTC") -> str:
    """
    Convert an ISO-8601 datetime string (e.g., 2025-10-11T09:39:16.749+03:30 or ...Z)
    into target_tz. Returns ISO-8601 string with offset.
    """
    # Normalize 'Z' to +00:00 so fromisoformat can parse it
    s = dt_str.replace('Z', '+00:00')
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(fallback_tz))
    dst = dt.astimezone(ZoneInfo(target_tz))
    # Keep milliseconds if present in input; else default
    # Comment out the timespec line if you want full microseconds.
    return dst.isoformat(timespec='milliseconds')

def _resolve_calendar_id(calendar_param: Any) -> str:
    if not calendar_param:
        raise ValueError("Calendar parameter not provided")
    if isinstance(calendar_param, dict):
        return calendar_param.get("value") or calendar_param.get("id") or "primary"
    return "primary"

# ---------- Time helpers ----------

def _has_utc_offset(iso_str: str) -> bool:
    """
    Returns True if iso_str contains an explicit UTC offset or 'Z' (e.g. 2025-10-13T09:00:00+03:30 or ...Z).
    """
    return any(x in iso_str for x in ["+", "-", "Z"]) and "T" in iso_str


def _coerce_date_only(s: str) -> str:
    """
    Extract YYYY-MM-DD from an ISO string safely.
    """
    if len(s) >= 10:
        return s[:10]
    # Fallback: try parsing, then format
    return date.fromisoformat(s).isoformat()

from datetime import datetime, date, time, timezone
import re

# def _maybe_replace_with_next_instance(
#     calendar_id: str,
#     event_data: Dict[str, Any],
#     headers: Dict[str, str],
#     return_next_instance: bool,
#     instances_extra_fields: Optional[str] = None,
# ) -> Dict[str, Any]:
#     """
#     If return_next_instance is True and the event is recurring, try to fetch the next instance
#     via the /instances endpoint. If an instance is found, return it, otherwise return the
#     original event_data.

#     :param calendar_id: resolved calendar id
#     :param event_data: event object returned from events.get
#     :param headers: request headers (contains Authorization)
#     :param return_next_instance: whether to try to replace with next instance
#     :param instances_extra_fields: additional fields to request from instances endpoint
#     :return: event object (instance if available, else original)
#     """
#     try:
#         if not return_next_instance or not event_data.get("recurrence"):
#             return event_data

#         instances_url = f"{googleCalendar._base_url}/calendars/{calendar_id}/events/{event_data.get('id')}/instances"

#         time_min = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
#         inst_params: Dict[str, Any] = {"timeMin": time_min, "maxResults": 1}

#         # Keep fields minimal but include start/end/attendees by default; allow caller to extend.
#         default_fields = "items(id,summary,start,end,attendees,htmlLink,status,organizer,recurringEventId)"
#         inst_params["fields"] = f"{default_fields}{(',' + instances_extra_fields) if instances_extra_fields else ''}"

#         inst_resp = requests.get(instances_url, headers=headers, params=inst_params, timeout=30)
#         if inst_resp.status_code == 200:
#             inst_json = inst_resp.json()
#             items = inst_json.get("items") or []
#             if len(items) > 0:
#                 return items[0]
#             else:
#                 logger.info("No upcoming instance returned; keeping original event object.")
#                 return event_data
#         else:
#             logger.warning(
#                 "Failed to fetch instances for next occurrence "
#                 f"({inst_resp.status_code}): {inst_resp.text}; keeping original event."
#             )
#             return event_data
#     except Exception as ex:
#         logger.exception(f"Error while fetching next instance: {ex}")
#         return event_data

# def _build_recurrence(additional: dict, time_zone: str = "UTC", all_day: bool = False):
#     """
#     Build Google Calendar 'recurrence' from:
#       - repeatFrecuency: daily|weekly|monthly|yearly
#       - repeatHowManyTimes: integer > 0  -> RRULE;COUNT=n
#       - repeatUntil: ISO-like date or datetime (e.g. '2025-10-15' or '2025-10-15 00:00:00')
#                      -> converted to UTC and formatted as YYYYMMDDTHHMMSSZ for RRULE;UNTIL=...
#     Rules:
#       - You can set either 'repeatHowManyTimes' or 'repeatUntil', not both.
#       - If none are set, we still return FREQ=... only.
#       - Returns a list like ["RRULE:FREQ=WEEKLY;COUNT=5"] or None if no frequency provided.
#     """
#     if not isinstance(additional, dict):
#         return None

#     # Accept the misspelled key as provided in your schema.
#     freq_key = (additional.get("repeatFrecuency") or "").strip().lower()
#     if not freq_key:
#         return None

#     freq_map = {
#         "daily": "DAILY",
#         "weekly": "WEEKLY",
#         "monthly": "MONTHLY",
#         "yearly": "YEARLY",
#     }
#     if freq_key not in freq_map:
#         raise ValueError("repeatFrecuency must be one of: daily, weekly, monthly, yearly")

#     count_raw = additional.get("repeatHowManyTimes")
#     until_raw = additional.get("repeatUntil")

#     if count_raw and until_raw:
#         # Exact error text you asked for:
#         raise ValueError("You can set either 'Repeat How Many Times' or 'Repeat Until' but not both")

#     rrule_parts = [f"FREQ={freq_map[freq_key]}"]

#     # COUNT handling
#     if count_raw is not None and str(count_raw).strip() != "":
#         try:
#             n = int(count_raw)
#             if n <= 0:
#                 raise ValueError
#         except Exception:
#             raise ValueError("repeatHowManyTimes must be a positive integer")
#         rrule_parts.append(f"COUNT={n}")

#     # UNTIL handling
#     elif until_raw:
#         until_utc = _normalize_until_to_utc(until_raw, time_zone, all_day)
#         rrule_parts.append(f"UNTIL={until_utc}")

#     # Build final RRULE
#     rrule = "RRULE:" + ";".join(rrule_parts)
#     return [rrule]


# def _normalize_until_to_utc(until_raw: str, tzinfo: str, all_day: bool) -> str:
#     """
#     Convert a user-friendly date/datetime (local in `time_zone`) to RFC5545 UNTIL format:
#       - YYYYMMDDTHHMMSSZ (UTC)
#     Accepts:
#       - 'YYYY-MM-DD'
#       - 'YYYY-MM-DD HH:MM'
#       - 'YYYY-MM-DD HH:MM:SS'
#       - ISO strings 'YYYY-MM-DDTHH:MM:SS'
#     For all-day events:
#       - If date-only is given, interpret at local 23:59:59 (inclusive style),
#         then convert to UTC so the series genuinely stops on that calendar day.
#       - If datetime is given, use it as-is (local) and convert to UTC.
#     For timed events:
#       - Use the provided datetime (or 00:00:00 if date-only); convert to UTC.
#     NOTE: This uses Python stdlib timezones when available; if you already carry
#     a robust tz helper in your project, swap it in here.
#     """
#     # Parse simple forms
#     s = until_raw.strip().replace("T", " ")
#     # Allow just date
#     m_date_only = re.fullmatch(r"\d{4}-\d{2}-\d{2}", s)
#     m_dt_hm     = re.fullmatch(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", s)
#     m_dt_hms    = re.fullmatch(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", s)


#     if m_date_only:
#         d = date.fromisoformat(s)
#         if all_day:
#             # End of that local calendar day (inclusive feel)
#             local_dt = datetime.combine(d, time(23, 59, 59), tzinfo=tzinfo)
#         else:
#             # Timed series: a date-only UNTIL usually means end at start of day
#             local_dt = datetime.combine(d, time(0, 0, 0), tzinfo=tzinfo)
#     elif m_dt_hm:
#         local_dt = datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=tzinfo)
#     elif m_dt_hms:
#         local_dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=tzinfo)
#     else:
#         # Last chance: try fromisoformat (handles 'YYYY-MM-DDTHH:MM:SS[.fff][+/-HH:MM]')
#         try:
#             parsed = datetime.fromisoformat(until_raw)
#             if parsed.tzinfo is None:
#                 parsed = parsed.replace(tzinfo=tzinfo)
#             local_dt = parsed
#         except Exception:
#             raise ValueError("repeatUntil must be an ISO date/datetime like '2025-10-15' or '2025-10-15 00:00:00'")

#     # Convert to UTC and format RFC5545
#     utc_dt = local_dt.astimezone(timezone.utc)
#     return utc_dt.strftime("%Y%m%dT%H%M%SZ")



# ---------- Builders ----------

# def _build_start_end(
#     start_raw: str,
#     end_raw: str,
#     time_zone: str,
#     all_day: bool,
# ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
#     """
#     Build Google Calendar start/end objects.

#     Normalization:
#     - All-day → date-only with exclusive end date.
#     - For timed events:
#       * If start/end carry an explicit offset (or 'Z'), omit timeZone (Google uses the offset).
#       * Otherwise include timeZone alongside naive local dateTime strings.
#     """
#     if all_day:
#         start_date = _coerce_date_only(start_raw)
#         if end_raw:
#             end_date = _coerce_date_only(end_raw)
#         else:
#             # fallback: +1 day
#             d = date.fromisoformat(start_date) + timedelta(days=1)
#             end_date = d.isoformat()

#         return {"date": start_date}, {"date": end_date}

#     # Timed event
#     start_has_offset = _has_utc_offset(start_raw)
#     end_has_offset = _has_utc_offset(end_raw)

#     # We prefer consistent handling; if either has offset, treat both as offset-based
#     if start_has_offset or end_has_offset:
#         return ({"dateTime": start_raw}, {"dateTime": end_raw})

#     # No offset → rely on provided time_zone
#     return (
#         {"dateTime": start_raw, "timeZone": time_zone},
#         {"dateTime": end_raw,   "timeZone": time_zone},
#     )


def _build_attendees(additional: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """
    Accepts a list of strings or objects and normalizes to attendee objects.
    Returns None if empty to keep payload tidy.
    """
    raw = additional.get("attendees", []) or []
    norm: List[Dict[str, Any]] = []
    for a in raw:
            email = a.strip()
            if email:
                norm.append({"email": email})
        
    return norm or None


# def _build_reminders(use_default_reminders: bool, additional: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     Supports default reminders or custom overrides if provided as:
#       additional["reminderOverrides"] = [{"method": "email"|"popup", "minutes": int}, ...]
#     """
#     overrides = additional.get("reminderOverrides") or []
#     if overrides:
#         # If custom overrides provided, force useDefault=False
#         return {"useDefault": False, "overrides": overrides}
#     return {"useDefault": bool(use_default_reminders)}

def _extract_attendees_and_mode(additional: Dict[str, Any]) -> Tuple[Optional[List[Dict[str, Any]]], str]:
    """
    Parse attendees from:
      - additional['attendeesUi'].values.{mode, attendees[]}
      - legacy additional['attendees'] (string | list[str] | list[dict])

    Returns (normalized_attendees_or_None, mode) where mode is 'add' or 'replace'.
    """
    attendees_list: List[Dict[str, Any]] = []
    mode = "replace"  # default for legacy behavior

    # New UI block
    attendees_ui = additional.get("attendeesUi") or {}
    vals = attendees_ui.get("values") if isinstance(attendees_ui, dict) else None
    if isinstance(vals, dict):
        mode = (vals.get("mode") or "add").strip().lower()
        raw_ui = vals.get("attendees") or []
        # Prepare 'additional.attendees' for the normalizer
        prepared: List[Union[str, Dict[str, Any]]] = []
        for a in raw_ui:
                prepared.append(a)
        if prepared:
            tmp = dict(additional)  # shallow copy to not mutate caller
            tmp["attendees"] = prepared
            attendees_list = _build_attendees(tmp) or []

    # Legacy attendees fallback (only if nothing came from the UI)
    if not attendees_list and "attendees" in additional:
        attendees_list = _build_attendees(additional) or []
        # legacy acts like replace (keep default)

    return (attendees_list or None, mode)


def _compute_attendees_patch(
    attendees_list: Optional[List[Dict[str, Any]]],
    mode: str,
    current_attendees_provider: Callable[[], List[Dict[str, Any]]],
) -> Optional[List[Dict[str, Any]]]:
    """
    Returns the final attendees list to put in the PATCH body, depending on mode:
      - 'add': fetch current attendees and append uniques
      - otherwise: replace with attendees_list
    If attendees_list is falsy, returns None (leave field untouched).
    """
    if not attendees_list:
        return None

    if str(mode).lower() == "add":
        cur_list = current_attendees_provider() or []
        existing = {str(a.get("email", "")).lower() for a in cur_list if a.get("email")}
        to_add = [a for a in attendees_list if str(a.get("email", "")).lower() not in existing]
        return (cur_list or []) + to_add

    # replace
    return attendees_list

