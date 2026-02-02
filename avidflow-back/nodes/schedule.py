import croniter
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, List, Any
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)

class ScheduleNode(BaseNode):
    """
    Schedule Trigger Node - Triggers workflow execution based on time intervals or cron expressions.
    Integrates with Celery scheduler for actual scheduling.
    """
    
    type = "schedule"
    version = 1
    
    description = {
        "displayName": "Schedule Trigger",
        "name": "scheduleTrigger",
        "group": ["trigger", "schedule"],
        "version": 1,
        "description": "Triggers the workflow on a given schedule",
        "defaults": {
            "name": "Schedule Trigger",
            "color": "#31C49F"
        },
        "inputs": [],  # No inputs for trigger nodes
        "outputs": [
            {"name": "main", "type": "main", "required": True}
        ],
        "icon": "fa:clock"
    }

    @staticmethod
    def schedule_parameters() -> List[Dict[str, Any]]:
        return [
            {"name": "rule", "type": NodeParameterType.OPTIONS, "display_name": "Trigger Interval",
             "options": [
                 {"name": "Every Minute", "value": "everyMinute"},
                 {"name": "Every Hour", "value": "everyHour"},
                 {"name": "Every Day", "value": "everyDay"},
                 {"name": "Every Week", "value": "everyWeek"},
                 {"name": "Every Month", "value": "everyMonth"},
                 {"name": "Custom (Cron)", "value": "custom"},
             ], "default": "everyDay", "required": True},
            {"name": "minutesCron", "type": NodeParameterType.STRING, "display_name": "Minute(s)", "default": "*",
             "displayOptions": {"show": {"rule": ["custom"]}}},
            {"name": "hoursCron", "type": NodeParameterType.STRING, "display_name": "Hour(s)", "default": "*",
             "displayOptions": {"show": {"rule": ["custom"]}}},
            {"name": "daysOfMonthCron", "type": NodeParameterType.STRING, "display_name": "Day(s) Of The Month", "default": "*",
             "displayOptions": {"show": {"rule": ["custom"]}}},
            {"name": "daysOfWeekCron", "type": NodeParameterType.STRING, "display_name": "Day(s) Of The Week", "default": "*",
             "displayOptions": {"show": {"rule": ["custom"]}}},
            {"name": "monthsOfYearCron", "type": NodeParameterType.STRING, "display_name": "Month(s) Of The Year", "default": "*",
             "displayOptions": {"show": {"rule": ["custom"]}}},
            {"name": "minute", "type": NodeParameterType.NUMBER, "display_name": "Minute", "default": 0, "min": 0, "max": 59,
             "displayOptions": {"show": {"rule": ["everyHour", "everyDay", "everyWeek", "everyMonth"]}}},
            {"name": "hour", "type": NodeParameterType.NUMBER, "display_name": "Hour", "default": 0, "min": 0, "max": 23,
             "displayOptions": {"show": {"rule": ["everyDay", "everyWeek", "everyMonth"]}}},
            {"name": "weekday", "type": NodeParameterType.OPTIONS, "display_name": "Weekday",
             "options": [
                 {"name": "Sunday", "value": 0}, {"name": "Monday", "value": 1}, {"name": "Tuesday", "value": 2},
                 {"name": "Wednesday", "value": 3}, {"name": "Thursday", "value": 4}, {"name": "Friday", "value": 5},
                 {"name": "Saturday", "value": 6},
             ], "default": 0, "displayOptions": {"show": {"rule": ["everyWeek"]}}},
            {"name": "dayOfMonth", "type": NodeParameterType.NUMBER, "display_name": "Day of Month", "default": 1, "min": 1, "max": 31,
             "displayOptions": {"show": {"rule": ["everyMonth"]}}},
            {"name": "timezone", "type": NodeParameterType.OPTIONS, "display_name": "Timezone", "default": "UTC",
             "options": [{"name": "UTC", "value": "UTC"}, {"name": "Asia/Tehran", "value": "Asia/Tehran"}]},
        ]
    
    properties = {
        "parameters": schedule_parameters()
    }
    
    icon = "fa:clock"
    color = "#31C49F"


    def trigger(self) -> List[List[NodeExecutionData]]:
        """
        Handle schedule trigger - creates timestamp data and calculates next run.
        This is called by the Celery scheduler service.
        Returns data in the same format as execute() method.
        """
        trigger_data = self.register_schedule()
        return [[NodeExecutionData(json_data=trigger_data)]]
    
    def _cron_field(self, value: Any, default: str = "*") -> str:
        """
        Normalize a cron field value to string:
        - None/"" -> default
        - list/tuple -> comma-joined
        - int/float -> int string
        - str -> stripped
        """
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return default
        if isinstance(value, (list, tuple)):
            return ",".join(str(int(v)) for v in value if v is not None and str(v) != "")
        if isinstance(value, (int, float)):
            return str(int(value))
        return str(value).strip()

    # ------------------------
    # Validation helpers
    # ------------------------
    def _validate_int_range(self, name: str, val: Any, lo: int, hi: int) -> int:
        try:
            ival = int(val)
        except Exception:
            raise ValueError(f"{name} must be an integer in [{lo}, {hi}]")
        if not (lo <= ival <= hi):
            raise ValueError(f"{name} must be in range [{lo}, {hi}]")
        return ival

    def _normalize_weekday(self, v: Any) -> int:
        """Accept 0..6 or 7 as Sunday; normalize 7 -> 0 and validate."""
        iv = self._validate_int_range("weekday", v, 0, 7)
        return 0 if iv == 7 else iv

    _STEP_RE = re.compile(r"^\*/(\d+)$")
    _RANGE_RE = re.compile(r"^(\d+)-(\d+)(?:/(\d+))?$")

    def _validate_cron_field_str(self, name: str, s: Any, lo: int, hi: int) -> str:
        """
        Validate a crontab field string allowing:
        - "*"
        - "*/step"
        - "start-end"
        - "start-end/step"
        - comma-separated combinations of numbers and ranges
        Returns the cleaned string or raises ValueError.
        """
        if s is None:
            return "*"
        if isinstance(s, (int, float)):
            s = str(int(s))
        s = str(s).strip()
        if s == "":
            return "*"
        if s == "*":
            return s

        parts = [p.strip() for p in s.split(",") if p.strip() != ""]
        normalized: list[str] = []
        for p in parts:
            # */step
            m = self._STEP_RE.match(p)
            if m:
                step = int(m.group(1))
                if step < 1:
                    raise ValueError(f"{name}: step must be >= 1")
                normalized.append(f"*/{step}")
                continue
            # start-end or start-end/step
            m = self._RANGE_RE.match(p)
            if m:
                start = int(m.group(1))
                end = int(m.group(2))
                step = int(m.group(3)) if m.group(3) else None
                if not (lo <= start <= hi and lo <= end <= hi and start <= end):
                    raise ValueError(f"{name}: range {start}-{end} out of bounds [{lo},{hi}]")
                if step is not None and step < 1:
                    raise ValueError(f"{name}: step in range must be >= 1")
                normalized.append(f"{start}-{end}" + (f"/{step}" if step else ""))
                continue
            # single number
            try:
                num = int(p)
            except Exception:
                raise ValueError(f"{name}: invalid token '{p}'")
            if not (lo <= num <= hi):
                raise ValueError(f"{name}: value {num} out of bounds [{lo},{hi}]")
            normalized.append(str(num))

        return ",".join(normalized) if normalized else "*"

    def _validate_final_cron(self, minute: str, hour: str, dom: str, moy: str, dow: str, tz: str) -> None:
        """Use croniter to sanity-check the combined expression."""
        expr = f"{minute} {hour} {dom} {moy} {dow}"
        try:
            now = datetime.now(ZoneInfo(tz) if tz else ZoneInfo("UTC"))
            croniter.croniter(expr, now)
        except Exception as e:
            raise ValueError(f"Invalid cron expression '{expr}': {e}")

    def register_schedule(self) -> Dict[str, Any]:
        """Build crontab fields: minute, hour, day_of_week, day_of_month, month_of_year"""
        rule = self.get_parameter("rule", 0, "everyDay")
        timezone = self.get_parameter("timezone", 0, "UTC") or "UTC"
        # Defaults: run every minute
        minute = "*"
        hour = "*"
        day_of_week = "*"
        day_of_month = "*"
        month_of_year = "*"
        if rule == "everyMinute":
            # * * * * *
            pass
        elif rule == "everyHour":
            # m * * * *
            m = self.get_parameter("minute", 0, 0)
            minute = str(self._validate_int_range("minute", m, 0, 59))
        elif rule == "everyDay":
            # m H * * *
            h = self.get_parameter("hour", 0, 0)
            m = self.get_parameter("minute", 0, 0)
            hour = str(self._validate_int_range("hour", h, 0, 23))
            minute = str(self._validate_int_range("minute", m, 0, 59))
        elif rule == "everyWeek":
            # m H * * DOW
            h = self.get_parameter("hour", 0, 0)
            m = self.get_parameter("minute", 0, 0)
            dow = self.get_parameter(" weekday", 0, 1)  # 0..6 (Sun=0)
            # Normalize Sunday 7 -> 0 and validate
            dow = self._normalize_weekday(dow)
            hour = str(self._validate_int_range("hour", h, 0, 23))
            minute = str(self._validate_int_range("minute", m, 0, 59))
            day_of_week = str(dow)
        elif rule == "everyMonth":
            # m H DOM * *
            dom = self.get_parameter("dayOfMonth", 0, 1)
            h = self.get_parameter("hour", 0, 0)
            m = self.get_parameter("minute", 0, 0)
            day_of_month = str(self._validate_int_range("day_of_month", dom, 1, 31))
            hour = str(self._validate_int_range("hour", h, 0, 23))
            minute = str(self._validate_int_range("minute", m, 0, 59))
        elif rule == "custom":
            # minutesCron hoursCron daysOfMonthCron MonthsOfYearCron daysOfWeekCron
            minutesCron = self.get_parameter("minutesCron", 0, "*")
            hoursCron = self.get_parameter("hoursCron", 0, "*")
            domCron = self.get_parameter("daysOfMonthCron", 0, "*")
            dowCron = self.get_parameter("daysOfWeekCron", 0, "*")
            moyCron = self.get_parameter("monthsOfYearCron", 0, "*")
            minute = self._validate_cron_field_str("minute", minutesCron, 0, 59)
            hour = self._validate_cron_field_str("hour", hoursCron, 0, 23)
            day_of_month = self._validate_cron_field_str("day_of_month", domCron, 1, 31)
            month_of_year = self._validate_cron_field_str("month_of_year", moyCron, 1, 12)
            # Accept 0 or 7 as Sunday in lists; normalize 7->0 in tokens
            dow_validated = self._validate_cron_field_str("day_of_week", dowCron, 0, 7)
            # Replace any standalone 7 with 0 while preserving ranges (7 only allowed as single token)
            # For simplicity: split commas and map '7' -> '0'
            day_of_week = ",".join("0" if t == "7" else t for t in dow_validated.split(","))
        result = {
            "minute": minute,
            "hour": hour,
            "day_of_week": day_of_week,
            "day_of_month": day_of_month,
            "month_of_year": month_of_year,
            "timezone": timezone,
        }
        # Final combined validation with croniter
        self._validate_final_cron(
            minute=result["minute"],
            hour=result["hour"],
            dom=result["day_of_month"],
            moy=result["month_of_year"],
            dow=result["day_of_week"],
            tz=timezone,
        )
        return result

    def _prev_schedule_fire_ts(self) -> int:
           """Compute previous scheduled run timestamp (UTC seconds) from register_schedule()."""
           cfg = self.register_schedule()
           tz = ZoneInfo(cfg.get("timezone") or "UTC")
           expr = f"{cfg['minute']} {cfg['hour']} {cfg['day_of_month']} {cfg['month_of_year']} {cfg['day_of_week']}"
           now_tz = datetime.now(tz)
           it = croniter.croniter(expr, now_tz)
           prev_dt = it.get_prev(datetime)  # tz-aware
           return int(prev_dt.timestamp())